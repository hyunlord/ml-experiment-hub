"""Pydantic schemas for ConfigSchema CRUD and field definition validation."""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, model_validator

from backend.schemas.base import TimezoneAwareResponse


class FieldType(str, Enum):
    """Supported field types for dynamic form generation."""

    SELECT = "select"
    MULTI_SELECT = "multi-select"
    TEXT = "text"
    NUMBER = "number"
    BOOLEAN = "boolean"
    SLIDER = "slider"
    JSON = "json"


class SelectOption(BaseModel):
    """Option for multi-select fields with label/value pairs."""

    value: str
    label: str
    description: str = ""


class SchemaFieldDefinition(BaseModel):
    """A single field definition within a config schema.

    The 'type' determines which UI input component renders and
    which extra fields (min, max, step, options) are relevant.
    """

    key: str = Field(
        min_length=1,
        description="Dot-notation key (e.g. 'model.backbone', 'training.batch_size')",
    )
    label: str = Field(min_length=1, description="Human-readable label for the UI")
    type: FieldType = Field(description="Input component type")
    group: str = Field(default="General", description="UI grouping category")
    description: str = Field(default="", description="Help text for the field")
    required: bool = Field(default=False)
    default: Any = Field(default=None, description="Default value")

    # Number/slider fields
    min: float | None = Field(default=None, description="Minimum value (number/slider)")
    max: float | None = Field(default=None, description="Maximum value (number/slider)")
    step: float | None = Field(default=None, description="Step increment (number/slider)")

    # Select/multi-select fields — can be simple strings or {value, label} objects
    options: list[str] | list[SelectOption] | None = Field(
        default=None,
        description="Options for select/multi-select fields",
    )

    # Dependency hints for conditional UI behavior
    depends_on: dict[str, Any] | None = Field(
        default=None,
        description="Dependency hint: {field, condition, effect, hint}",
    )

    @model_validator(mode="after")
    def validate_type_constraints(self) -> "SchemaFieldDefinition":
        """Validate that type-specific fields are present."""
        if self.type in (FieldType.SELECT, FieldType.MULTI_SELECT):
            if not self.options:
                raise ValueError(f"Field '{self.key}': '{self.type}' requires 'options'")
        if self.type == FieldType.SLIDER:
            if self.min is None or self.max is None:
                raise ValueError(f"Field '{self.key}': 'slider' requires 'min' and 'max'")
        return self


class SchemaDefinition(BaseModel):
    """The full schema definition stored in ConfigSchema.fields_schema."""

    fields: list[SchemaFieldDefinition] = Field(min_length=1)
    groups_order: list[str] = Field(
        default_factory=list,
        description="Ordered list of group names for UI rendering",
    )

    @model_validator(mode="after")
    def validate_unique_keys(self) -> "SchemaDefinition":
        """Ensure all field keys are unique."""
        keys = [f.key for f in self.fields]
        if len(keys) != len(set(keys)):
            dupes = [k for k in keys if keys.count(k) > 1]
            raise ValueError(f"Duplicate field keys: {set(dupes)}")
        return self


# --- CRUD Request/Response Schemas ---


class ConfigSchemaCreate(BaseModel):
    """Request schema for creating a new ConfigSchema."""

    name: str = Field(min_length=1)
    description: str = Field(default="")
    fields_schema: SchemaDefinition


class ConfigSchemaUpdate(BaseModel):
    """Request schema for updating a ConfigSchema."""

    name: str | None = None
    description: str | None = None
    fields_schema: SchemaDefinition | None = None


class ConfigSchemaResponse(TimezoneAwareResponse):
    """Response schema for a ConfigSchema."""

    id: int
    name: str
    description: str
    fields_schema: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class ConfigSchemaListResponse(BaseModel):
    """Response schema for listing ConfigSchemas."""

    schemas: list[ConfigSchemaResponse]
    total: int
