"""Custom scalar handlers for GraphQL code generation.

Provides a protocol for defining how GraphQL custom scalars map to Python types
and how they're serialized/deserialized.

Example usage:
    from gql_pygen.core.scalars import ScalarHandler, ScalarRegistry, DateTimeHandler

    # Use built-in handlers
    registry = ScalarRegistry()
    registry.register("DateTime", DateTimeHandler())

    # Create custom handler
    class MoneyHandler(ScalarHandler):
        python_type = "Decimal"
        import_statement = "from decimal import Decimal"

        def serialize(self, value):
            return str(value)

        def deserialize(self, value):
            from decimal import Decimal
            return Decimal(value)

    registry.register("Money", MoneyHandler())
"""

from datetime import datetime
from typing import Any, Protocol, runtime_checkable
from uuid import UUID


@runtime_checkable
class ScalarHandler(Protocol):
    """Protocol for custom scalar handlers.

    Implement this protocol to define how a GraphQL scalar maps to Python.

    Attributes:
        python_type: The Python type name (e.g., "datetime", "Decimal")
        import_statement: The import needed for this type (e.g., "from datetime import datetime")
    """

    python_type: str
    import_statement: str

    def serialize(self, value: Any) -> Any:
        """Convert Python value to JSON-serializable format for GraphQL."""
        ...

    def deserialize(self, value: Any) -> Any:
        """Convert JSON value from GraphQL to Python type."""
        ...


class DateTimeHandler:
    """Handler for DateTime scalars using ISO 8601 format."""

    python_type = "datetime"
    import_statement = "from datetime import datetime"

    def serialize(self, value: datetime) -> str:
        """Convert datetime to ISO 8601 string."""
        return value.isoformat()

    def deserialize(self, value: str) -> datetime:
        """Parse ISO 8601 string to datetime."""
        return datetime.fromisoformat(value.replace("Z", "+00:00"))


class DateHandler:
    """Handler for Date scalars using ISO 8601 date format."""

    python_type = "date"
    import_statement = "from datetime import date"

    def serialize(self, value) -> str:
        """Convert date to ISO 8601 string."""
        return value.isoformat()

    def deserialize(self, value: str):
        """Parse ISO 8601 date string."""
        from datetime import date
        return date.fromisoformat(value)


class UUIDHandler:
    """Handler for UUID scalars."""

    python_type = "UUID"
    import_statement = "from uuid import UUID"

    def serialize(self, value: UUID) -> str:
        """Convert UUID to string."""
        return str(value)

    def deserialize(self, value: str) -> UUID:
        """Parse string to UUID."""
        return UUID(value)


class JSONHandler:
    """Handler for JSON scalars (pass-through)."""

    python_type = "Any"
    import_statement = "from typing import Any"

    def serialize(self, value: Any) -> Any:
        """JSON values are already serializable."""
        return value

    def deserialize(self, value: Any) -> Any:
        """JSON values are already deserialized."""
        return value


class ScalarRegistry:
    """Registry for custom scalar handlers.

    Manages the mapping between GraphQL scalar names and their handlers.

    Example:
        registry = ScalarRegistry()
        registry.register("DateTime", DateTimeHandler())

        handler = registry.get("DateTime")
        if handler:
            python_type = handler.python_type  # "datetime"
    """

    def __init__(self):
        self._handlers: dict[str, ScalarHandler] = {}
        # Register default handlers
        self._register_defaults()

    def _register_defaults(self):
        """Register built-in default handlers."""
        self.register("DateTime", DateTimeHandler())
        self.register("Date", DateHandler())
        self.register("UUID", UUIDHandler())
        self.register("JSON", JSONHandler())
        self.register("JSONObject", JSONHandler())

    def register(self, scalar_name: str, handler: ScalarHandler):
        """Register a handler for a scalar type."""
        self._handlers[scalar_name] = handler

    def get(self, scalar_name: str) -> ScalarHandler | None:
        """Get the handler for a scalar type, or None if not registered."""
        return self._handlers.get(scalar_name)

    def has(self, scalar_name: str) -> bool:
        """Check if a handler is registered for a scalar type."""
        return scalar_name in self._handlers

    def get_all_imports(self) -> set:
        """Get all import statements needed for registered handlers."""
        return {h.import_statement for h in self._handlers.values()}

