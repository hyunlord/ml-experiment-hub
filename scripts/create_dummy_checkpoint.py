"""Generate a dummy checkpoint and test data for smoke tests.

Creates:
- tests/fixtures/dummy_checkpoint.pt — random-weight model checkpoint
- tests/fixtures/dummy_images/*.png — 10 tiny test images (32x32)
- tests/fixtures/dummy_captions.json — 10 test captions

Usage:
    python scripts/create_dummy_checkpoint.py
"""

import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import torch
from PIL import Image

from adapters.vlm_quantization.model import CrossModalHashModel, ModelConfig

FIXTURES_DIR = Path(__file__).parent.parent / "tests" / "fixtures"
IMAGES_DIR = FIXTURES_DIR / "dummy_images"


CAPTIONS = [
    "a cat sitting on a sofa",
    "고양이가 소파에 앉아있다",
    "a dog running in the park",
    "sunset over the ocean with golden light",
    "a red car parked on the street",
    "fresh fruits on a wooden table",
    "a person reading a book in a library",
    "mountains covered in snow during winter",
    "a cup of coffee on a desk",
    "children playing in a playground",
]


def main() -> None:
    """Generate dummy checkpoint and test data."""
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)

    # Set seed for reproducibility
    torch.manual_seed(42)

    # Create dummy model with small dimensions
    config = ModelConfig(
        backbone_name="dummy",
        backbone_dim=256,
        bit_list=[8, 16, 32, 64, 128],
        hidden_dim=128,
        dropout=0.0,
    )
    model = CrossModalHashModel(config)

    # Save checkpoint
    checkpoint = {
        "config": {
            "backbone_name": config.backbone_name,
            "backbone_dim": config.backbone_dim,
            "bit_list": config.bit_list,
            "hidden_dim": config.hidden_dim,
            "dropout": config.dropout,
        },
        "state_dict": model.state_dict(),
    }
    ckpt_path = FIXTURES_DIR / "dummy_checkpoint.pt"
    torch.save(checkpoint, ckpt_path)
    print(f"Checkpoint saved: {ckpt_path}")

    # Generate 10 tiny images (32x32 with distinct colors)
    colors = [
        (255, 0, 0),
        (0, 255, 0),
        (0, 0, 255),
        (255, 255, 0),
        (255, 0, 255),
        (0, 255, 255),
        (128, 0, 0),
        (0, 128, 0),
        (0, 0, 128),
        (128, 128, 128),
    ]
    image_paths = []
    for i, color in enumerate(colors):
        img = Image.new("RGB", (32, 32), color)
        # Add some variation
        for x in range(0, 32, 8):
            for y in range(0, 32, 8):
                variation = ((x * 7 + y * 13 + i * 37) % 64,) * 3
                mixed = tuple(min(255, c + v) for c, v in zip(color, variation))
                for dx in range(min(4, 32 - x)):
                    for dy in range(min(4, 32 - y)):
                        img.putpixel((x + dx, y + dy), mixed)
        path = IMAGES_DIR / f"img_{i:03d}.png"
        img.save(path)
        image_paths.append(str(path))

    print(f"Generated {len(image_paths)} test images in {IMAGES_DIR}")

    # Save captions
    captions_path = FIXTURES_DIR / "dummy_captions.json"
    data = {
        "captions": CAPTIONS,
        "image_paths": [str(p) for p in image_paths],
        "labels": list(range(len(CAPTIONS))),
    }
    with open(captions_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"Captions saved: {captions_path}")

    # Verify: load and encode
    from adapters.vlm_quantization.model import load_model

    loaded = load_model(str(ckpt_path), device="cpu")
    test_img = torch.randn(1, 3, 32, 32)
    codes = loaded.encode_image(test_img, bit_length=64)
    print(f"Verification: encode_image → {codes.shape}, values: {codes[0, :8]}")

    print("\nDone! Dummy checkpoint and test data ready.")


if __name__ == "__main__":
    main()
