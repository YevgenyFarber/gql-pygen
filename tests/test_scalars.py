"""Tests for custom scalar handlers."""

from datetime import date, datetime
from uuid import UUID

import pytest

from gql_pygen.core.scalars import (
    DateHandler,
    DateTimeHandler,
    JSONHandler,
    ScalarHandler,
    ScalarRegistry,
    UUIDHandler,
)


class TestDateTimeHandler:
    """Tests for DateTimeHandler."""

    def test_python_type(self):
        handler = DateTimeHandler()
        assert handler.python_type == "datetime"

    def test_import_statement(self):
        handler = DateTimeHandler()
        assert handler.import_statement == "from datetime import datetime"

    def test_serialize(self):
        handler = DateTimeHandler()
        dt = datetime(2024, 1, 15, 10, 30, 0)
        assert handler.serialize(dt) == "2024-01-15T10:30:00"

    def test_deserialize(self):
        handler = DateTimeHandler()
        result = handler.deserialize("2024-01-15T10:30:00")
        assert result == datetime(2024, 1, 15, 10, 30, 0)

    def test_deserialize_with_z_suffix(self):
        handler = DateTimeHandler()
        result = handler.deserialize("2024-01-15T10:30:00Z")
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15


class TestDateHandler:
    """Tests for DateHandler."""

    def test_python_type(self):
        handler = DateHandler()
        assert handler.python_type == "date"

    def test_serialize(self):
        handler = DateHandler()
        d = date(2024, 1, 15)
        assert handler.serialize(d) == "2024-01-15"

    def test_deserialize(self):
        handler = DateHandler()
        result = handler.deserialize("2024-01-15")
        assert result == date(2024, 1, 15)


class TestUUIDHandler:
    """Tests for UUIDHandler."""

    def test_python_type(self):
        handler = UUIDHandler()
        assert handler.python_type == "UUID"

    def test_serialize(self):
        handler = UUIDHandler()
        uid = UUID("12345678-1234-5678-1234-567812345678")
        assert handler.serialize(uid) == "12345678-1234-5678-1234-567812345678"

    def test_deserialize(self):
        handler = UUIDHandler()
        result = handler.deserialize("12345678-1234-5678-1234-567812345678")
        assert result == UUID("12345678-1234-5678-1234-567812345678")


class TestJSONHandler:
    """Tests for JSONHandler."""

    def test_python_type(self):
        handler = JSONHandler()
        assert handler.python_type == "Any"

    def test_serialize_dict(self):
        handler = JSONHandler()
        data = {"key": "value", "number": 42}
        assert handler.serialize(data) == data

    def test_deserialize_list(self):
        handler = JSONHandler()
        data = [1, 2, 3]
        assert handler.deserialize(data) == data


class TestScalarRegistry:
    """Tests for ScalarRegistry."""

    def test_default_handlers_registered(self):
        registry = ScalarRegistry()
        assert registry.has("DateTime")
        assert registry.has("Date")
        assert registry.has("UUID")
        assert registry.has("JSON")
        assert registry.has("JSONObject")

    def test_get_handler(self):
        registry = ScalarRegistry()
        handler = registry.get("DateTime")
        assert handler is not None
        assert handler.python_type == "datetime"

    def test_get_nonexistent(self):
        registry = ScalarRegistry()
        assert registry.get("NonExistent") is None

    def test_register_custom(self):
        registry = ScalarRegistry()

        class MoneyHandler:
            python_type = "Decimal"
            import_statement = "from decimal import Decimal"

            def serialize(self, value):
                return str(value)

            def deserialize(self, value):
                from decimal import Decimal
                return Decimal(value)

        registry.register("Money", MoneyHandler())
        assert registry.has("Money")
        assert registry.get("Money").python_type == "Decimal"

    def test_get_all_imports(self):
        registry = ScalarRegistry()
        imports = registry.get_all_imports()
        assert "from datetime import datetime" in imports
        assert "from datetime import date" in imports
        assert "from uuid import UUID" in imports


class TestScalarHandlerProtocol:
    """Tests for protocol compliance."""

    def test_datetime_handler_is_scalar_handler(self):
        assert isinstance(DateTimeHandler(), ScalarHandler)

    def test_date_handler_is_scalar_handler(self):
        assert isinstance(DateHandler(), ScalarHandler)

    def test_uuid_handler_is_scalar_handler(self):
        assert isinstance(UUIDHandler(), ScalarHandler)

    def test_json_handler_is_scalar_handler(self):
        assert isinstance(JSONHandler(), ScalarHandler)

