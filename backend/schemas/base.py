"""Base schemas with timezone-aware datetime serialization."""

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, model_serializer


class TimezoneAwareResponse(BaseModel):
    """Base response model that serializes naive datetimes as UTC with timezone info.

    All datetime fields are serialized with UTC timezone indicator (Z or +00:00).
    This ensures the frontend correctly interprets times as UTC rather than local time.
    """

    class Config:
        from_attributes = True

    @model_serializer(mode="wrap", when_used="json")
    def _serialize_datetimes_as_utc(self, serializer: Any, info: Any) -> dict[str, Any]:
        """Ensure all datetime values include UTC timezone info in JSON output."""
        data = serializer(self)
        return self._add_timezone_to_datetimes(data)

    @classmethod
    def _add_timezone_to_datetimes(cls, obj: Any) -> Any:
        """Recursively add UTC timezone to naive datetime objects."""
        if isinstance(obj, datetime):
            if obj.tzinfo is None:
                obj = obj.replace(tzinfo=timezone.utc)
            return obj.isoformat()
        elif isinstance(obj, dict):
            return {k: cls._add_timezone_to_datetimes(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [cls._add_timezone_to_datetimes(item) for item in obj]
        return obj
