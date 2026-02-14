"""Index building for cross-modal retrieval.

Re-implements the index building pipeline from vlm_quantization.
Encodes images and texts, stores hash codes + features + thumbnails.
"""

from __future__ import annotations

import base64
import io
import logging
from pathlib import Path
from typing import Any, Callable

import torch
from PIL import Image
from torch.utils.data import DataLoader, Dataset

logger = logging.getLogger(__name__)


class SimpleImageTextDataset(Dataset):
    """Simple dataset for index building from image paths + captions."""

    def __init__(
        self,
        image_paths: list[str],
        captions: list[str],
        image_size: int = 384,
        labels: list[int] | None = None,
    ) -> None:
        assert len(image_paths) == len(captions)
        self.image_paths = image_paths
        self.captions = captions
        self.image_size = image_size
        self.labels = labels or list(range(len(image_paths)))

    def __len__(self) -> int:
        return len(self.image_paths)

    def __getitem__(self, idx: int) -> dict[str, Any]:
        img = Image.open(self.image_paths[idx]).convert("RGB")
        img = img.resize((self.image_size, self.image_size))

        # Convert to tensor (CHW, float32, [0, 1]) without torchvision
        import numpy as np

        arr = np.array(img, dtype=np.float32) / 255.0  # (H, W, 3)
        pixel_values = torch.from_numpy(arr).permute(2, 0, 1)  # (3, H, W)

        # Simple tokenization: convert caption to character-level token IDs
        caption = self.captions[idx]
        token_ids = [ord(c) % 32000 for c in caption[:128]]
        # Pad to fixed length
        max_len = 128
        attention_mask = [1] * len(token_ids) + [0] * (max_len - len(token_ids))
        token_ids = token_ids + [0] * (max_len - len(token_ids))

        return {
            "pixel_values": pixel_values,
            "input_ids": torch.tensor(token_ids, dtype=torch.long),
            "attention_mask": torch.tensor(attention_mask, dtype=torch.long),
            "caption": caption,
            "image_path": self.image_paths[idx],
            "label": self.labels[idx],
        }


def image_to_thumbnail_b64(image_path: str, size: int = 64, quality: int = 60) -> str:
    """Convert an image file to a base64-encoded JPEG thumbnail.

    Args:
        image_path: Path to the source image.
        size: Thumbnail size (square).
        quality: JPEG quality (1-100).

    Returns:
        Base64-encoded JPEG string.
    """
    img = Image.open(image_path).convert("RGB")
    img.thumbnail((size, size))
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=quality)
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


def build_index(
    model: Any,
    image_paths: list[str],
    captions: list[str],
    output_path: str,
    labels: list[int] | None = None,
    batch_size: int = 32,
    image_size: int = 384,
    thumbnail_size: int = 64,
    device: str = "cpu",
    progress_callback: Callable[[int, int], None] | None = None,
) -> dict[str, Any]:
    """Build a search index from images and captions.

    Encodes all items through the model and saves:
    - image_codes: {bit_length: tensor} for each bit length
    - text_codes: {bit_length: tensor} for each bit length
    - image_features: backbone features for cosine search
    - text_features: backbone features for cosine search
    - thumbnails: base64-encoded JPEG thumbnails
    - captions: list of caption strings
    - labels: list of labels

    Args:
        model: CrossModalHashModel instance.
        image_paths: List of image file paths.
        captions: List of caption strings.
        output_path: Where to save the index .pt file.
        labels: Optional class labels for each item.
        batch_size: Encoding batch size.
        image_size: Image resize dimension.
        thumbnail_size: Thumbnail size for previews.
        device: Device for encoding.
        progress_callback: Called with (current, total) for progress tracking.

    Returns:
        Index data dict (same as what's saved to disk).
    """
    model.eval()
    model.to(device)

    dataset = SimpleImageTextDataset(
        image_paths=image_paths,
        captions=captions,
        image_size=image_size,
        labels=labels,
    )
    loader = DataLoader(dataset, batch_size=batch_size, shuffle=False)

    # Collect encodings
    all_image_codes: dict[int, list[torch.Tensor]] = {b: [] for b in model.bit_list}
    all_text_codes: dict[int, list[torch.Tensor]] = {b: [] for b in model.bit_list}
    all_image_features: list[torch.Tensor] = []
    all_text_features: list[torch.Tensor] = []
    all_labels: list[int] = []
    total = len(dataset)
    processed = 0

    for batch in loader:
        pixel_values = batch["pixel_values"].to(device)
        input_ids = batch["input_ids"].to(device)
        attention_mask = batch["attention_mask"].to(device)

        # Encode images (all bit lengths + features)
        img_codes_dict, img_features = model.encode_image_all_bits(
            pixel_values, binary=True, return_features=True
        )
        for bit, codes in img_codes_dict.items():
            all_image_codes[bit].append(codes.cpu())
        all_image_features.append(img_features.cpu())

        # Encode texts (all bit lengths + features)
        txt_codes_dict, txt_features = model.encode_text_all_bits(
            input_ids, attention_mask=attention_mask, binary=True, return_features=True
        )
        for bit, codes in txt_codes_dict.items():
            all_text_codes[bit].append(codes.cpu())
        all_text_features.append(txt_features.cpu())

        all_labels.extend(batch["label"].tolist())

        processed += len(pixel_values)
        if progress_callback:
            progress_callback(processed, total)

    # Concatenate
    image_codes = {b: torch.cat(v) for b, v in all_image_codes.items()}
    text_codes = {b: torch.cat(v) for b, v in all_text_codes.items()}
    image_features = torch.cat(all_image_features)
    text_features = torch.cat(all_text_features)

    # Generate thumbnails
    logger.info("Generating thumbnails for %d images...", len(image_paths))
    thumbnails: list[str] = []
    for path in image_paths:
        try:
            thumbnails.append(image_to_thumbnail_b64(path, size=thumbnail_size))
        except Exception:
            logger.warning("Failed to create thumbnail for %s", path)
            thumbnails.append("")

    # Build index data
    index_data: dict[str, Any] = {
        "image_codes": image_codes,
        "text_codes": text_codes,
        "image_features": image_features,
        "text_features": text_features,
        "thumbnails": thumbnails,
        "captions": captions,
        "labels": all_labels,
        "bit_list": model.bit_list,
        "num_items": len(image_paths),
    }

    # Save to disk
    output_dir = Path(output_path).parent
    output_dir.mkdir(parents=True, exist_ok=True)
    torch.save(index_data, output_path)
    logger.info("Index saved to %s (%d items)", output_path, len(image_paths))

    return index_data


def load_index(index_path: str, device: str = "cpu") -> dict[str, Any]:
    """Load a pre-built search index.

    Args:
        index_path: Path to the .pt index file.
        device: Device to load tensors on.

    Returns:
        Index data dict.
    """
    index_data = torch.load(index_path, map_location=device, weights_only=False)
    logger.info(
        "Loaded index from %s (%d items, bit_list=%s)",
        index_path,
        index_data.get("num_items", 0),
        index_data.get("bit_list", []),
    )
    return index_data
