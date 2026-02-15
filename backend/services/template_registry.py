"""Template registry for predefined ML project structures."""

from typing import Any

from backend.schemas.project import TemplateConfigSchema, TemplateInfo, TemplateTask

# Predefined templates
TEMPLATES: list[TemplateInfo] = [
    TemplateInfo(
        id="pytorch-lightning",
        framework="pytorch-lightning",
        name="PyTorch Lightning",
        description="PyTorch Lightning-based training with built-in logging, checkpointing, and distributed training",
        tasks=[
            TemplateTask(
                id="image-classification",
                name="Image Classification",
                description="CNN/ViT image classification",
            ),
            TemplateTask(
                id="text-classification",
                name="Text Classification",
                description="Text classification with transformers",
            ),
            TemplateTask(
                id="object-detection",
                name="Object Detection",
                description="Object detection (YOLO, DETR, etc.)",
            ),
            TemplateTask(
                id="cross-modal-retrieval",
                name="Cross-Modal Retrieval",
                description="Cross-modal hashing and retrieval",
            ),
            TemplateTask(
                id="custom", name="Custom", description="Custom PyTorch Lightning project"
            ),
        ],
    ),
    TemplateInfo(
        id="huggingface",
        framework="huggingface",
        name="HuggingFace Trainer",
        description="HuggingFace Transformers Trainer API for fine-tuning and evaluation",
        tasks=[
            TemplateTask(
                id="text-classification",
                name="Text Classification",
                description="Sequence classification",
            ),
            TemplateTask(
                id="token-classification",
                name="Token Classification",
                description="NER, POS tagging",
            ),
            TemplateTask(
                id="seq2seq",
                name="Seq2Seq",
                description="Sequence-to-sequence (translation, summarization)",
            ),
            TemplateTask(
                id="causal-lm",
                name="Causal LM Fine-tune",
                description="Causal language model fine-tuning",
            ),
            TemplateTask(
                id="image-classification",
                name="Image Classification",
                description="ViT image classification",
            ),
            TemplateTask(id="custom", name="Custom", description="Custom HuggingFace project"),
        ],
    ),
    TemplateInfo(
        id="plain-pytorch",
        framework="plain-pytorch",
        name="Plain PyTorch",
        description="Vanilla PyTorch training loop with manual control",
        tasks=[
            TemplateTask(
                id="image-classification",
                name="Image Classification",
                description="Basic image classification",
            ),
            TemplateTask(id="custom", name="Custom", description="Custom PyTorch project"),
        ],
    ),
    TemplateInfo(
        id="custom-script",
        framework="custom-script",
        name="Custom Script",
        description="Bring your own training script with minimal scaffolding",
        tasks=[
            TemplateTask(id="custom", name="Custom", description="Any custom training workflow"),
        ],
    ),
]

# Config schemas per template+task combination
_CONFIG_SCHEMAS: dict[str, dict[str, Any]] = {
    "pytorch-lightning": {
        "common": {
            "batch_size": {"type": "number", "default": 32, "min": 1, "max": 2048},
            "learning_rate": {
                "type": "number",
                "default": 0.001,
                "min": 0.0,
                "max": 1.0,
                "step": 0.0001,
            },
            "max_epochs": {"type": "number", "default": 100, "min": 1, "max": 10000},
            "optimizer": {
                "type": "select",
                "default": "adam",
                "options": ["adam", "adamw", "sgd", "rmsprop"],
            },
            "scheduler": {
                "type": "select",
                "default": "cosine",
                "options": ["cosine", "step", "plateau", "none"],
            },
            "precision": {
                "type": "select",
                "default": "16-mixed",
                "options": ["32", "16-mixed", "bf16-mixed"],
            },
            "accelerator": {
                "type": "select",
                "default": "auto",
                "options": ["auto", "gpu", "cpu", "tpu"],
            },
            "devices": {"type": "number", "default": 1, "min": 1, "max": 8},
            "seed": {"type": "number", "default": 42, "min": 0, "max": 999999},
        },
    },
    "huggingface": {
        "common": {
            "batch_size": {"type": "number", "default": 16, "min": 1, "max": 512},
            "learning_rate": {
                "type": "number",
                "default": 5e-5,
                "min": 0.0,
                "max": 1.0,
                "step": 0.00001,
            },
            "num_train_epochs": {"type": "number", "default": 3, "min": 1, "max": 1000},
            "weight_decay": {"type": "number", "default": 0.01, "min": 0.0, "max": 1.0},
            "warmup_steps": {"type": "number", "default": 500, "min": 0, "max": 100000},
            "fp16": {"type": "boolean", "default": True},
            "gradient_accumulation_steps": {"type": "number", "default": 1, "min": 1, "max": 128},
            "seed": {"type": "number", "default": 42, "min": 0, "max": 999999},
        },
    },
    "plain-pytorch": {
        "common": {
            "batch_size": {"type": "number", "default": 64, "min": 1, "max": 2048},
            "learning_rate": {"type": "number", "default": 0.01, "min": 0.0, "max": 1.0},
            "epochs": {"type": "number", "default": 50, "min": 1, "max": 10000},
            "optimizer": {"type": "select", "default": "sgd", "options": ["adam", "adamw", "sgd"]},
            "seed": {"type": "number", "default": 42, "min": 0, "max": 999999},
        },
    },
    "custom-script": {
        "common": {
            "config_format": {
                "type": "select",
                "default": "yaml",
                "options": ["yaml", "json", "toml"],
            },
        },
    },
}


def list_templates() -> list[TemplateInfo]:
    """Return all available templates."""
    return TEMPLATES


def get_template(template_id: str) -> TemplateInfo | None:
    """Get a template by ID."""
    for t in TEMPLATES:
        if t.id == template_id:
            return t
    return None


def get_template_config_schema(
    template_id: str,
    task_id: str | None = None,
) -> TemplateConfigSchema | None:
    """Get the config schema for a template (optionally filtered by task)."""
    schema_group = _CONFIG_SCHEMAS.get(template_id)
    if not schema_group:
        return None

    fields = dict(schema_group.get("common", {}))
    if task_id and task_id in schema_group:
        fields.update(schema_group[task_id])

    return TemplateConfigSchema(
        template_id=template_id,
        task_id=task_id,
        fields=fields,
    )
