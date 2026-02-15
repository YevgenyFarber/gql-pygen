"""Unit tests for the client generator."""

import ast
import pytest
from gql_pygen.core.client_generator import (
    ClientGenerator,
    ClientNode,
    to_snake_case,
    to_pascal_case,
)
from gql_pygen.core.ir import IRSchema, IROperation, IRArgument


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def simple_operation():
    """A simple mutation with one required arg and one optional."""
    return IROperation(
        name="addAccount",
        operation_type="mutation",
        arguments=[
            IRArgument(name="input", type_name="AddAccountInput", is_optional=False),
        ],
        return_type="AccountInfo",
        is_return_optional=True,
        path=["accountManagement", "addAccount"],
        parent_arguments=[
            IRArgument(name="accountId", type_name="ID", is_optional=False),
        ],
    )


@pytest.fixture
def list_return_operation():
    """An operation that returns a list."""
    return IROperation(
        name="getRules",
        operation_type="query",
        arguments=[],
        return_type="Rule",
        is_return_list=True,
        is_return_optional=False,
        path=["policy", "getRules"],
        parent_arguments=[
            IRArgument(name="accountId", type_name="ID", is_optional=False),
        ],
    )


@pytest.fixture
def reserved_keyword_operation():
    """An operation with a reserved keyword as parameter name."""
    return IROperation(
        name="importData",
        operation_type="mutation",
        arguments=[
            IRArgument(name="from", type_name="String", is_optional=False),
            IRArgument(name="import", type_name="ImportInput", is_optional=True),
        ],
        return_type="ImportResult",
        path=["importData"],
    )


@pytest.fixture
def duplicate_param_operation():
    """An operation with duplicate parameter names needing suffixes."""
    return IROperation(
        name="addRule",
        operation_type="mutation",
        arguments=[
            IRArgument(name="input", type_name="AddRuleInput", is_optional=False),
        ],
        return_type="RulePayload",
        path=["policy", "internetFirewall", "addRule"],
        parent_arguments=[
            IRArgument(name="accountId", type_name="ID", is_optional=False),
            IRArgument(name="input", type_name="PolicyMutationInput", is_optional=True),
        ],
    )


@pytest.fixture
def minimal_schema(simple_operation):
    """A minimal schema with one mutation."""
    return IRSchema(
        scalars={},
        enums={},
        types={},
        inputs={},
        interfaces={},
        queries=[],
        mutations=[simple_operation],
    )


# =============================================================================
# Tests: Helper Functions
# =============================================================================


class TestHelperFunctions:
    """Tests for to_snake_case and to_pascal_case."""

    def test_to_snake_case_camel(self):
        assert to_snake_case("internetFirewall") == "internet_firewall"

    def test_to_snake_case_pascal(self):
        assert to_snake_case("InternetFirewall") == "internet_firewall"

    def test_to_snake_case_already_snake(self):
        assert to_snake_case("internet_firewall") == "internet_firewall"

    def test_to_snake_case_single_word(self):
        assert to_snake_case("policy") == "policy"

    def test_to_snake_case_acronym(self):
        assert to_snake_case("getHTTPStatus") == "get_http_status"

    def test_to_pascal_case_from_snake(self):
        assert to_pascal_case("internet_firewall") == "InternetFirewall"

    def test_to_pascal_case_from_camel(self):
        assert to_pascal_case("internetFirewall") == "InternetFirewall"

    def test_to_pascal_case_single_word(self):
        assert to_pascal_case("policy") == "Policy"


# =============================================================================
# Tests: ClientNode
# =============================================================================


class TestClientNode:
    """Tests for ClientNode hierarchy building."""

    def test_add_operation_single_level(self, simple_operation):
        """Operations at depth 1 are added directly."""
        root = ClientNode(name="Root", snake_name="root")
        # Path is ["accountManagement", "addAccount"], so we start at accountManagement
        root.add_operation(["addAccount"], simple_operation)
        
        assert len(root.operations) == 1
        assert root.operations[0].name == "addAccount"

    def test_add_operation_creates_children(self, simple_operation):
        """Nested paths create child nodes."""
        root = ClientNode(name="Root", snake_name="root")
        root.add_operation(["accountManagement", "addAccount"], simple_operation)

        assert "accountManagement" in root.children
        child = root.children["accountManagement"]
        assert child.snake_name == "account_management"
        assert len(child.operations) == 1

    def test_add_operation_deeply_nested(self, simple_operation):
        """Deep paths create multiple levels of children."""
        root = ClientNode(name="Root", snake_name="root")
        root.add_operation(["policy", "internetFirewall", "addRule"], simple_operation)

        assert "policy" in root.children
        policy = root.children["policy"]
        assert "internetFirewall" in policy.children
        firewall = policy.children["internetFirewall"]
        assert len(firewall.operations) == 1


# =============================================================================
# Tests: Method Generation
# =============================================================================


class TestOperationMethodGeneration:
    """Tests for _generate_operation_method."""

    def test_required_params_before_optional(self, simple_operation, minimal_schema):
        """Required parameters should come before optional ones."""
        gen = ClientGenerator(minimal_schema)
        lines = gen._generate_operation_method(simple_operation)
        method_code = "\n".join(lines)

        # Find parameter positions
        account_id_pos = method_code.find("account_id: str")
        input_pos = method_code.find("input: AddAccountInput")
        fields_pos = method_code.find("fields: FieldSelection")

        # Required params before optional, fields last
        assert account_id_pos < input_pos < fields_pos

    def test_reserved_keyword_escaping(self, reserved_keyword_operation, minimal_schema):
        """Python reserved keywords should be escaped with trailing underscore."""
        schema = IRSchema(
            scalars={}, enums={}, types={}, inputs={}, interfaces={},
            queries=[], mutations=[reserved_keyword_operation],
        )
        gen = ClientGenerator(schema)
        lines = gen._generate_operation_method(reserved_keyword_operation)
        method_code = "\n".join(lines)

        # 'from' and 'import' should be escaped
        assert "from_: str" in method_code
        assert "import_: Optional[ImportInput]" in method_code

    def test_duplicate_params_get_suffix(self, duplicate_param_operation, minimal_schema):
        """Duplicate parameter names get type-based suffixes."""
        schema = IRSchema(
            scalars={}, enums={}, types={}, inputs={}, interfaces={},
            queries=[], mutations=[duplicate_param_operation],
        )
        gen = ClientGenerator(schema)
        lines = gen._generate_operation_method(duplicate_param_operation)
        method_code = "\n".join(lines)

        # First 'input' from parent args stays as-is, second gets suffix
        assert "input:" in method_code or "input_" in method_code
        # Should have both variations
        assert "input_add_rule" in method_code or "input_policy" in method_code

    def test_optional_return_generates_none_check(self, simple_operation, minimal_schema):
        """Optional return types should have None check before model_validate."""
        gen = ClientGenerator(minimal_schema)
        lines = gen._generate_operation_method(simple_operation)
        method_code = "\n".join(lines)

        assert "if result is None:" in method_code
        assert "return None" in method_code
        assert "AccountInfo.model_validate(result)" in method_code

    def test_list_return_generates_comprehension(self, list_return_operation, minimal_schema):
        """List return types should use list comprehension for model_validate."""
        schema = IRSchema(
            scalars={}, enums={}, types={}, inputs={}, interfaces={},
            queries=[list_return_operation], mutations=[],
        )
        gen = ClientGenerator(schema)
        lines = gen._generate_operation_method(list_return_operation)
        method_code = "\n".join(lines)

        assert "return []" in method_code  # Empty list fallback
        assert "[Rule.model_validate(item) for item in result]" in method_code

    def test_method_has_docstring(self, simple_operation, minimal_schema):
        """Generated methods should have docstrings."""
        gen = ClientGenerator(minimal_schema)
        lines = gen._generate_operation_method(simple_operation)
        method_code = "\n".join(lines)

        assert '"""' in method_code


# =============================================================================
# Tests: Full Generation
# =============================================================================


class TestFullGeneration:
    """Tests for complete client code generation."""

    def test_generates_valid_python(self, minimal_schema):
        """Generated code should be valid Python syntax."""
        gen = ClientGenerator(minimal_schema)
        code = gen.generate_client_code()

        # Should not raise SyntaxError
        ast.parse(code)

    def test_has_expected_imports(self, minimal_schema):
        """Generated code should have required imports."""
        gen = ClientGenerator(minimal_schema)
        code = gen.generate_client_code()

        assert "from __future__ import annotations" in code
        assert "from typing import" in code
        assert "from .query_builder import FieldSelection" in code
        assert "from .executor import GraphQLExecutor" in code
        assert "from ..models import *" in code

    def test_generates_default_client_class(self, minimal_schema):
        """Should generate the root client class with default name."""
        gen = ClientGenerator(minimal_schema)
        code = gen.generate_client_code()

        assert "class GraphQLClient:" in code
        assert "def __init__(self, url: str, api_key: str):" in code
        assert "async def close(self):" in code
        assert "async def __aenter__(self):" in code
        assert "async def __aexit__(self" in code

    def test_generates_custom_client_class(self, minimal_schema):
        """Should generate the root client class with custom name."""
        gen = ClientGenerator(minimal_schema, client_name="MyAPIClient")
        code = gen.generate_client_code()

        assert "class MyAPIClient:" in code
        assert "MyAPIClient(url=" in code  # In docstring example

    def test_generates_namespace_client(self, minimal_schema):
        """Should generate namespace client classes."""
        gen = ClientGenerator(minimal_schema)
        code = gen.generate_client_code()

        # Should have AccountManagement client
        assert "AccountManagementClient" in code

    def test_model_validate_in_output(self, minimal_schema):
        """All methods should have model_validate calls."""
        gen = ClientGenerator(minimal_schema)
        code = gen.generate_client_code()

        assert "model_validate" in code

