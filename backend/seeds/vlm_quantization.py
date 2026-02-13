"""Seed data for vlm_quantization (Cross-Modal Deep Hashing) project.

Inserts:
  1. ConfigSchema — "Cross-Modal Deep Hashing (SigLIP2)" with all fields
  2. 4 ExperimentConfig presets (Default, Colab, DGX Spark, Multilingual)

Usage:
  python -m backend.seeds.vlm_quantization
"""

import asyncio
import logging

from sqlmodel import select

from backend.models.database import async_session_maker, init_db
from backend.models.experiment import ConfigSchema, ExperimentConfig

logger = logging.getLogger(__name__)

# =============================================================================
# ConfigSchema: field definitions for dynamic form generation
# =============================================================================

SCHEMA_DATA = {
    "name": "Cross-Modal Deep Hashing (SigLIP2)",
    "description": (
        "Multi-resolution cross-modal hashing with SigLIP2 backbone. "
        "Supports frozen/unfrozen backbone, multi-dataset training, "
        "and automatic GPU-aware batch size configuration."
    ),
    "fields_schema": {
        "groups_order": ["Model", "Training", "Loss", "Data", "Monitor"],
        "fields": [
            # ── Model ──────────────────────────────────────────────────
            {
                "key": "model.backbone",
                "label": "Backbone Model",
                "type": "select",
                "group": "Model",
                "description": "Pre-trained vision-language backbone",
                "required": True,
                "default": "google/siglip2-so400m-patch14-384",
                "options": [
                    {"value": "google/siglip2-so400m-patch14-384", "label": "SigLIP2 So400m (384px)"},
                ],
            },
            {
                "key": "model.bit_list",
                "label": "Hash Bit Lengths",
                "type": "multi-select",
                "group": "Model",
                "description": "Multi-resolution hash code lengths. Longer codes = higher recall, shorter = faster search.",
                "required": True,
                "default": [8, 16, 32, 48, 64, 128],
                "options": [
                    {"value": "8", "label": "8-bit"},
                    {"value": "16", "label": "16-bit"},
                    {"value": "32", "label": "32-bit"},
                    {"value": "48", "label": "48-bit"},
                    {"value": "64", "label": "64-bit"},
                    {"value": "128", "label": "128-bit"},
                ],
            },
            {
                "key": "model.hidden_dim",
                "label": "Hidden Dimension",
                "type": "select",
                "group": "Model",
                "description": "Hash projection layer hidden size",
                "default": 512,
                "options": [
                    {"value": "256", "label": "256"},
                    {"value": "512", "label": "512"},
                    {"value": "768", "label": "768"},
                    {"value": "1024", "label": "1024"},
                ],
            },
            {
                "key": "model.dropout",
                "label": "Dropout",
                "type": "slider",
                "group": "Model",
                "description": "Hash layer dropout rate",
                "default": 0.1,
                "min": 0.0,
                "max": 0.5,
                "step": 0.01,
            },
            {
                "key": "model.freeze_backbone",
                "label": "Freeze Backbone",
                "type": "boolean",
                "group": "Model",
                "description": "Freeze SigLIP2 weights (faster training, less VRAM). Unfreeze for multilingual fine-tuning.",
                "default": False,
            },
            # ── Training ───────────────────────────────────────────────
            {
                "key": "training.batch_size",
                "label": "Batch Size",
                "type": "select",
                "group": "Training",
                "description": "Per-GPU batch size. 'auto' detects optimal value based on GPU VRAM.",
                "required": True,
                "default": 128,
                "options": [
                    {"value": "auto", "label": "Auto (GPU-aware)"},
                    {"value": "32", "label": "32"},
                    {"value": "64", "label": "64"},
                    {"value": "128", "label": "128"},
                    {"value": "256", "label": "256"},
                    {"value": "320", "label": "320"},
                    {"value": "512", "label": "512"},
                ],
            },
            {
                "key": "training.max_epochs",
                "label": "Max Epochs",
                "type": "number",
                "group": "Training",
                "description": "Maximum training epochs (early stopping may end sooner)",
                "default": 30,
                "min": 1,
                "max": 100,
            },
            {
                "key": "training.hash_lr",
                "label": "Hash Layer LR",
                "type": "slider",
                "group": "Training",
                "description": "Learning rate for hash projection layers",
                "default": 0.001,
                "min": 0.0001,
                "max": 0.005,
                "step": 0.0001,
            },
            {
                "key": "training.backbone_lr",
                "label": "Backbone LR",
                "type": "slider",
                "group": "Training",
                "description": "Learning rate for backbone fine-tuning (ignored when frozen)",
                "default": 0.00001,
                "min": 0.000001,
                "max": 0.00005,
                "step": 0.000001,
                "depends_on": {
                    "field": "model.freeze_backbone",
                    "condition": {"eq": True},
                    "effect": "disabled",
                    "hint": "Backbone is frozen — LR not used",
                },
            },
            {
                "key": "training.weight_decay",
                "label": "Weight Decay",
                "type": "slider",
                "group": "Training",
                "description": "AdamW weight decay",
                "default": 0.01,
                "min": 0.0,
                "max": 0.1,
                "step": 0.001,
            },
            {
                "key": "training.warmup_steps",
                "label": "Warmup Steps",
                "type": "number",
                "group": "Training",
                "description": "Learning rate warmup steps (increase for larger datasets)",
                "default": 500,
                "min": 0,
                "max": 10000,
            },
            {
                "key": "training.gradient_clip_val",
                "label": "Gradient Clip",
                "type": "slider",
                "group": "Training",
                "description": "Max gradient norm for clipping",
                "default": 1.0,
                "min": 0.1,
                "max": 5.0,
                "step": 0.1,
            },
            {
                "key": "training.accumulate_grad_batches",
                "label": "Gradient Accumulation",
                "type": "number",
                "group": "Training",
                "description": "Accumulate gradients over N batches (effective_batch = batch_size × accum)",
                "default": 4,
                "min": 1,
                "max": 32,
                "depends_on": {
                    "field": "training.batch_size",
                    "condition": {"eq": "auto"},
                    "effect": "disabled",
                    "hint": "Auto-configured based on GPU VRAM",
                },
            },
            {
                "key": "training.val_check_interval",
                "label": "Validation Interval",
                "type": "slider",
                "group": "Training",
                "description": "Fraction of epoch between validation checks (0.5 = twice per epoch)",
                "default": 0.5,
                "min": 0.1,
                "max": 1.0,
                "step": 0.1,
            },
            {
                "key": "training.early_stopping_patience",
                "label": "Early Stopping Patience",
                "type": "number",
                "group": "Training",
                "description": "Stop if val/total doesn't improve for N validation checks",
                "default": 5,
                "min": 1,
                "max": 20,
            },
            {
                "key": "training.checkpoint_dir",
                "label": "Checkpoint Directory",
                "type": "text",
                "group": "Training",
                "description": "Directory for saving model checkpoints",
                "default": "checkpoints",
            },
            # ── Loss ───────────────────────────────────────────────────
            {
                "key": "loss.contrastive_weight",
                "label": "Contrastive Weight",
                "type": "slider",
                "group": "Loss",
                "description": "InfoNCE cross-modal contrastive loss weight",
                "default": 1.0,
                "min": 0.0,
                "max": 2.0,
                "step": 0.1,
            },
            {
                "key": "loss.ortho_weight",
                "label": "Ortho Weight",
                "type": "slider",
                "group": "Loss",
                "description": "Cross-modal orthogonal hashing loss weight",
                "default": 0.1,
                "min": 0.0,
                "max": 0.3,
                "step": 0.01,
            },
            {
                "key": "loss.quantization_weight",
                "label": "Quantization Weight",
                "type": "slider",
                "group": "Loss",
                "description": "EAQL adaptive quantization loss weight (ramps up during training)",
                "default": 0.1,
                "min": 0.0,
                "max": 0.3,
                "step": 0.01,
            },
            {
                "key": "loss.balance_weight",
                "label": "Balance Weight",
                "type": "slider",
                "group": "Loss",
                "description": "Bit balance + decorrelation loss weight",
                "default": 0.01,
                "min": 0.0,
                "max": 0.05,
                "step": 0.001,
            },
            {
                "key": "loss.consistency_weight",
                "label": "Consistency Weight",
                "type": "slider",
                "group": "Loss",
                "description": "Augmented image alignment consistency loss weight",
                "default": 0.5,
                "min": 0.0,
                "max": 1.0,
                "step": 0.05,
            },
            {
                "key": "loss.lcs_weight",
                "label": "LCS Weight",
                "type": "slider",
                "group": "Loss",
                "description": "Long→short self-distillation (LCS) loss weight",
                "default": 0.5,
                "min": 0.0,
                "max": 2.0,
                "step": 0.1,
            },
            {
                "key": "loss.temperature",
                "label": "Temperature",
                "type": "slider",
                "group": "Loss",
                "description": "InfoNCE temperature (lower = sharper contrast)",
                "default": 0.07,
                "min": 0.03,
                "max": 0.15,
                "step": 0.01,
            },
            {
                "key": "loss.ema_decay",
                "label": "EMA Decay",
                "type": "slider",
                "group": "Loss",
                "description": "EAQL exponential moving average decay",
                "default": 0.99,
                "min": 0.9,
                "max": 0.999,
                "step": 0.001,
            },
            # ── Data ───────────────────────────────────────────────────
            {
                "key": "data.data_root",
                "label": "Data Root",
                "type": "text",
                "group": "Data",
                "description": "Root directory for COCO images (train2014/, val2014/)",
                "required": True,
                "default": "./data/coco",
            },
            {
                "key": "data.karpathy_json",
                "label": "Karpathy Split JSON",
                "type": "text",
                "group": "Data",
                "description": "Path to Karpathy split file (leave empty for standard COCO splits)",
                "default": "./data/coco/dataset_coco.json",
            },
            {
                "key": "data.num_workers",
                "label": "DataLoader Workers",
                "type": "number",
                "group": "Data",
                "description": "Number of data loading workers",
                "default": 4,
                "min": 0,
                "max": 16,
                "depends_on": {
                    "field": "training.batch_size",
                    "condition": {"eq": "auto"},
                    "effect": "disabled",
                    "hint": "Auto-configured based on GPU",
                },
            },
            {
                "key": "data.max_text_length",
                "label": "Max Text Length",
                "type": "number",
                "group": "Data",
                "description": "Maximum caption token length (truncated beyond this)",
                "default": 64,
                "min": 16,
                "max": 256,
            },
            {
                "key": "data.image_size",
                "label": "Image Size",
                "type": "select",
                "group": "Data",
                "description": "Input image resolution (must match backbone)",
                "default": 384,
                "options": [
                    {"value": "224", "label": "224px"},
                    {"value": "256", "label": "256px"},
                    {"value": "384", "label": "384px (SigLIP2 native)"},
                    {"value": "512", "label": "512px"},
                ],
            },
            {
                "key": "data.extra_datasets",
                "label": "Extra Training Datasets",
                "type": "multi-select",
                "group": "Data",
                "description": "Additional bilingual datasets for multilingual hash training",
                "default": [],
                "options": [
                    {
                        "value": "coco_ko",
                        "label": "COCO Korean (AIHub #261)",
                        "description": "Korean captions for COCO images (reuses COCO image files)",
                    },
                    {
                        "value": "aihub",
                        "label": "AIHub #71454 (Korean-English)",
                        "description": "AIHub Korean-English parallel image-text pairs",
                    },
                    {
                        "value": "cc3m_ko",
                        "label": "CC3M-Ko (Bilingual)",
                        "description": "Conceptual Captions 3M with Korean translations",
                    },
                ],
            },
            # ── Monitor ───────────────────────────────────────────────
            {
                "key": "monitor.enabled",
                "label": "Enable Monitoring",
                "type": "boolean",
                "group": "Monitor",
                "description": "Send training metrics to ML Experiment Hub dashboard",
                "default": True,
            },
            {
                "key": "monitor.server_url",
                "label": "Monitor Server URL",
                "type": "text",
                "group": "Monitor",
                "description": "ML Experiment Hub API URL for metric collection",
                "default": "http://localhost:8000",
            },
            {
                "key": "monitor.log_every_n_steps",
                "label": "Log Interval",
                "type": "number",
                "group": "Monitor",
                "description": "Send training metrics every N optimizer steps",
                "default": 10,
                "min": 1,
                "max": 100,
            },
        ],
    },
}

# =============================================================================
# Preset ExperimentConfigs (flat dot-notation config_json)
# =============================================================================

PRESETS = [
    {
        "name": "Default Baseline",
        "description": "Standard COCO-only training with unfrozen backbone (30 epochs).",
        "tags": ["preset", "baseline"],
        "config_json": {
            "model.backbone": "google/siglip2-so400m-patch14-384",
            "model.bit_list": [8, 16, 32, 48, 64, 128],
            "model.hidden_dim": 512,
            "model.dropout": 0.1,
            "model.freeze_backbone": False,
            "training.batch_size": 128,
            "training.max_epochs": 30,
            "training.hash_lr": 0.001,
            "training.backbone_lr": 0.00001,
            "training.weight_decay": 0.01,
            "training.warmup_steps": 500,
            "training.gradient_clip_val": 1.0,
            "training.accumulate_grad_batches": 4,
            "training.early_stopping_patience": 5,
            "loss.contrastive_weight": 1.0,
            "loss.ortho_weight": 0.1,
            "loss.quantization_weight": 0.1,
            "loss.balance_weight": 0.01,
            "loss.consistency_weight": 0.5,
            "loss.lcs_weight": 0.5,
            "loss.temperature": 0.07,
            "loss.ema_decay": 0.99,
            "data.data_root": "./data/coco",
            "data.karpathy_json": "./data/coco/dataset_coco.json",
            "data.num_workers": 4,
            "data.max_text_length": 64,
            "data.image_size": 384,
            "data.extra_datasets": [],
            "monitor.enabled": True,
            "monitor.server_url": "http://localhost:8000",
            "monitor.log_every_n_steps": 10,
        },
    },
    {
        "name": "Colab (T4/A100)",
        "description": "Google Colab optimized: frozen backbone, auto batch size, all multilingual datasets, 15 epochs.",
        "tags": ["preset", "colab"],
        "config_json": {
            "model.backbone": "google/siglip2-so400m-patch14-384",
            "model.bit_list": [8, 16, 32, 48, 64, 128],
            "model.hidden_dim": 512,
            "model.dropout": 0.1,
            "model.freeze_backbone": True,
            "training.batch_size": "auto",
            "training.max_epochs": 15,
            "training.hash_lr": 0.001,
            "training.backbone_lr": 0.00001,
            "training.weight_decay": 0.01,
            "training.warmup_steps": 2000,
            "training.gradient_clip_val": 1.0,
            "training.accumulate_grad_batches": 4,
            "training.val_check_interval": 0.5,
            "training.early_stopping_patience": 3,
            "training.checkpoint_dir": "/content/drive/MyDrive/vlm_quantization/checkpoints",
            "loss.contrastive_weight": 1.0,
            "loss.ortho_weight": 0.1,
            "loss.quantization_weight": 0.1,
            "loss.balance_weight": 0.01,
            "loss.consistency_weight": 0.5,
            "loss.lcs_weight": 0.5,
            "loss.temperature": 0.07,
            "loss.ema_decay": 0.99,
            "data.data_root": "/content/data/coco",
            "data.karpathy_json": "/content/data/coco/dataset_coco.json",
            "data.num_workers": 4,
            "data.max_text_length": 64,
            "data.image_size": 384,
            "data.extra_datasets": ["coco_ko", "aihub", "cc3m_ko"],
            "monitor.enabled": True,
            "monitor.server_url": "http://localhost:8000",
            "monitor.log_every_n_steps": 10,
        },
    },
    {
        "name": "DGX Spark",
        "description": "NVIDIA DGX Spark (GH200, 128GB unified): frozen backbone, auto batch size, all datasets, 30 epochs.",
        "tags": ["preset", "dgx-spark"],
        "config_json": {
            "model.backbone": "google/siglip2-so400m-patch14-384",
            "model.bit_list": [8, 16, 32, 48, 64, 128],
            "model.hidden_dim": 512,
            "model.dropout": 0.1,
            "model.freeze_backbone": True,
            "training.batch_size": "auto",
            "training.max_epochs": 30,
            "training.hash_lr": 0.001,
            "training.backbone_lr": 0.00001,
            "training.weight_decay": 0.01,
            "training.warmup_steps": 2000,
            "training.gradient_clip_val": 1.0,
            "training.accumulate_grad_batches": 1,
            "training.val_check_interval": 0.5,
            "training.early_stopping_patience": 5,
            "training.checkpoint_dir": "checkpoints",
            "loss.contrastive_weight": 1.0,
            "loss.ortho_weight": 0.1,
            "loss.quantization_weight": 0.1,
            "loss.balance_weight": 0.01,
            "loss.consistency_weight": 0.5,
            "loss.lcs_weight": 0.5,
            "loss.temperature": 0.07,
            "loss.ema_decay": 0.99,
            "data.data_root": "data/coco",
            "data.karpathy_json": "data/coco/dataset_coco.json",
            "data.num_workers": 8,
            "data.max_text_length": 64,
            "data.image_size": 384,
            "data.extra_datasets": ["coco_ko", "aihub", "cc3m_ko"],
            "monitor.enabled": True,
            "monitor.server_url": "http://localhost:8000",
            "monitor.log_every_n_steps": 10,
        },
    },
    {
        "name": "Multilingual Fine-tune",
        "description": "A100 multilingual: unfrozen backbone (lower backbone_lr), aihub + cc3m_ko datasets, 5 epochs.",
        "tags": ["preset", "multilingual"],
        "config_json": {
            "model.backbone": "google/siglip2-so400m-patch14-384",
            "model.bit_list": [8, 16, 32, 48, 64, 128],
            "model.hidden_dim": 512,
            "model.dropout": 0.1,
            "model.freeze_backbone": False,
            "training.batch_size": "auto",
            "training.max_epochs": 5,
            "training.hash_lr": 0.001,
            "training.backbone_lr": 0.000005,
            "training.weight_decay": 0.01,
            "training.warmup_steps": 500,
            "training.gradient_clip_val": 1.0,
            "training.accumulate_grad_batches": 4,
            "training.val_check_interval": 5000,
            "training.early_stopping_patience": 3,
            "training.checkpoint_dir": "/content/drive/MyDrive/vlm_quantization/checkpoints",
            "loss.contrastive_weight": 1.0,
            "loss.ortho_weight": 0.1,
            "loss.quantization_weight": 0.1,
            "loss.balance_weight": 0.01,
            "loss.consistency_weight": 0.5,
            "loss.lcs_weight": 0.5,
            "loss.temperature": 0.07,
            "loss.ema_decay": 0.99,
            "data.data_root": "/content/data/coco",
            "data.karpathy_json": "/content/data/coco/dataset_coco.json",
            "data.num_workers": 4,
            "data.max_text_length": 64,
            "data.image_size": 384,
            "data.extra_datasets": ["aihub", "cc3m_ko"],
            "monitor.enabled": True,
            "monitor.server_url": "http://localhost:8000",
            "monitor.log_every_n_steps": 10,
        },
    },
]


async def seed() -> None:
    """Insert ConfigSchema and preset ExperimentConfigs into the database.

    Idempotent: skips if the schema already exists (matched by name).
    """
    await init_db()

    async with async_session_maker() as session:
        # Check if schema already exists
        result = await session.execute(
            select(ConfigSchema).where(
                ConfigSchema.name == SCHEMA_DATA["name"]
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            logger.info("Schema '%s' already exists (id=%d), skipping", existing.name, existing.id)
            schema_id = existing.id
        else:
            schema = ConfigSchema(
                name=SCHEMA_DATA["name"],
                description=SCHEMA_DATA["description"],
                fields_schema=SCHEMA_DATA["fields_schema"],
            )
            session.add(schema)
            await session.commit()
            await session.refresh(schema)
            schema_id = schema.id
            logger.info("Created schema '%s' (id=%d)", schema.name, schema_id)

        # Insert presets (skip if name already exists)
        for preset in PRESETS:
            result = await session.execute(
                select(ExperimentConfig).where(
                    ExperimentConfig.name == preset["name"]
                )
            )
            if result.scalar_one_or_none():
                logger.info("Preset '%s' already exists, skipping", preset["name"])
                continue

            config = ExperimentConfig(
                name=preset["name"],
                description=preset["description"],
                config_json=preset["config_json"],
                config_schema_id=schema_id,
                tags=preset["tags"],
            )
            session.add(config)
            logger.info("Created preset '%s'", preset["name"])

        await session.commit()

    logger.info("Seed complete")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(seed())
