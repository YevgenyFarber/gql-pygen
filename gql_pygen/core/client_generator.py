"""Client class generator for GraphQL operations.

Generates a nested client structure like:
    client.policy.internet_firewall.add_rule(account_id, input)
"""

import re
from dataclasses import dataclass, field
from typing import Any

from .ir import IROperation, IRSchema


@dataclass
class ClientNode:
    """Represents a node in the client hierarchy."""
    name: str  # e.g., "policy", "internetFirewall"
    snake_name: str  # e.g., "policy", "internet_firewall"
    children: dict[str, "ClientNode"] = field(default_factory=dict)
    operations: list[IROperation] = field(default_factory=list)

    def add_operation(self, path: list[str], operation: IROperation):
        """Add an operation at the given path."""
        if len(path) == 1:
            # This is the leaf - add the operation here
            self.operations.append(operation)
        else:
            # Navigate/create child nodes
            child_name = path[0]
            if child_name not in self.children:
                self.children[child_name] = ClientNode(
                    name=child_name,
                    snake_name=to_snake_case(child_name),
                )
            self.children[child_name].add_operation(path[1:], operation)


def to_snake_case(name: str) -> str:
    """Convert camelCase to snake_case."""
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()


def to_pascal_case(name: str) -> str:
    """Convert snake_case or camelCase to PascalCase."""
    # First convert to snake_case, then to PascalCase
    snake = to_snake_case(name)
    return "".join(word.capitalize() for word in snake.split("_"))


class ClientGenerator:
    """Generates client code from schema operations."""

    def __init__(self, schema: IRSchema, client_name: str = "GraphQLClient"):
        self.schema = schema
        self.client_name = client_name
        self.query_tree = ClientNode(name="Query", snake_name="query")
        self.mutation_tree = ClientNode(name="Mutation", snake_name="mutation")
        self._build_trees()

    def _build_trees(self):
        """Build client hierarchies from operations."""
        for op in self.schema.queries:
            if len(op.path) > 0:
                self.query_tree.add_operation(op.path, op)

        for op in self.schema.mutations:
            if len(op.path) > 0:
                self.mutation_tree.add_operation(op.path, op)

    def generate_client_code(self) -> str:
        """Generate the complete client module code."""
        lines = [
            '"""Auto-generated GraphQL client."""',
            "",
            "from __future__ import annotations",
            "from typing import Any, Dict, List, Optional, Union",
            "",
            "# Runtime imports from gql-pygen package",
            "from gql_pygen.core.auth import Auth, ApiKeyAuth, BearerAuth, BasicAuth, HeaderAuth, NoAuth",
            "from gql_pygen.core.query_builder import FieldSelection, QueryBuilder",
            "from gql_pygen.core.executor import GraphQLExecutor",
            "",
            "# Import generated models (relative to the generated package)",
            "from .models import *",
            "",
        ]

        # Generate namespace client classes
        generated_classes = set()

        # Generate mutation clients
        lines.extend(self._generate_client_classes(
            self.mutation_tree, "Mutation", generated_classes
        ))

        # Generate query clients
        lines.extend(self._generate_client_classes(
            self.query_tree, "Query", generated_classes
        ))

        # Generate root client
        lines.extend(self._generate_root_client())

        return "\n".join(lines)

    def _generate_client_classes(
        self,
        node: ClientNode,
        prefix: str,
        generated: set[str],
    ) -> list[str]:
        """Recursively generate client classes for a node and its children."""
        lines = []

        # Generate classes for children first (bottom-up)
        for child_name, child_node in sorted(node.children.items()):
            child_prefix = f"{prefix}_{to_pascal_case(child_name)}"
            lines.extend(self._generate_client_classes(child_node, child_prefix, generated))

        # Generate this node's class if it has operations or children
        if node.operations or node.children:
            class_name = f"{prefix}Client"
            if class_name not in generated:
                generated.add(class_name)
                lines.extend(self._generate_single_client_class(node, class_name))

        return lines

    def _generate_single_client_class(
        self,
        node: ClientNode,
        class_name: str,
    ) -> list[str]:
        """Generate a single client class."""
        lines = [
            f"class {class_name}:",
            f'    """Client for {node.name} operations."""',
            "",
            "    def __init__(self, executor: GraphQLExecutor, query_builder: QueryBuilder):",
            "        self._executor = executor",
            "        self._query_builder = query_builder",
        ]

        # Initialize child clients
        for child_name, child_node in sorted(node.children.items()):
            child_class = f"{class_name[:-6]}_{to_pascal_case(child_name)}Client"
            lines.append(f"        self.{child_node.snake_name} = {child_class}(executor, query_builder)")

        lines.append("")

        # Generate operation methods
        for op in node.operations:
            lines.extend(self._generate_operation_method(op))

        lines.append("")
        return lines

    def _generate_operation_method(self, op: IROperation) -> list[str]:
        """Generate an async method for an operation."""
        method_name = to_snake_case(op.name)

        # Build parameter list with unique names for duplicates
        # Also compute unique variable names (matching query builder logic)
        seen_var_names: set[str] = set()
        arg_to_param: list[tuple[Any, str, str]] = []  # (arg, param_name, var_name)
        required_params: list[str] = []
        optional_params: list[str] = []

        # Python reserved keywords that need to be escaped
        reserved_keywords = {
            "from", "import", "class", "def", "return", "yield", "raise",
            "try", "except", "finally", "with", "as", "pass", "break",
            "continue", "if", "elif", "else", "for", "while", "and", "or",
            "not", "in", "is", "lambda", "global", "nonlocal", "True",
            "False", "None", "async", "await", "type",
        }

        # Track all used param names to avoid collision with our 'fields' parameter
        used_param_names: set[str] = set()

        for arg in op.all_arguments:
            to_snake_case(arg.name)

            # Compute unique variable name (matching query builder)
            var_name = arg.name
            if var_name in seen_var_names:
                # Match the query builder's suffix logic
                type_suffix = self._type_to_var_suffix(arg.type_name)
                var_name = f"{arg.name}_{type_suffix}"
            seen_var_names.add(var_name)

            # Python param name (snake_case of var_name)
            param_name = to_snake_case(var_name)

            # Escape Python reserved keywords
            if param_name in reserved_keywords:
                param_name = f"{param_name}_"

            arg_to_param.append((arg, param_name, var_name))
            used_param_names.add(param_name)
            type_hint = self._arg_type_hint(arg)

            if arg.is_optional:
                optional_params.append(f"{param_name}: Optional[{type_hint}] = None")
            else:
                required_params.append(f"{param_name}: {type_hint}")

        # Determine field selection parameter name (avoid collision with operation arguments)
        field_selection_param = "fields"
        if "fields" in used_param_names:
            field_selection_param = "field_selection"

        # Build final params list: self, required, optional, fields
        params = ["self"] + required_params + optional_params
        params.append(f"{field_selection_param}: FieldSelection = FieldSelection.ALL")

        # Return type
        return_type = op.return_type
        if op.is_return_list:
            return_type = f"List[{return_type}]"
        if op.is_return_optional:
            return_type = f"Optional[{return_type}]"

        # Build method signature
        lines = [
            f"    async def {method_name}(",
        ]
        for i, param in enumerate(params):
            comma = "," if i < len(params) - 1 else ""
            lines.append(f"        {param}{comma}")
        lines.append(f"    ) -> {return_type}:")

        # Docstring
        desc = op.description or f"Execute {op.name} operation."
        lines.append(f'        """{desc}"""')

        # Build variables dict using unique variable names
        lines.append("        variables = {")
        for arg, param_name, var_name in arg_to_param:
            lines.append(f'            "{var_name}": {param_name},')
        lines.append("        }")

        # Get operation reference (we'll need to store ops or look them up)
        lines.append(f"        # Operation path: {op.path}")
        lines.append("        result = await self._executor.execute_operation(")
        lines.append(f'            operation_path={op.path!r},')
        lines.append("            variables=variables,")
        lines.append(f"            fields={field_selection_param},")
        lines.append("        )")

        # Add response parsing with model_validate()
        base_type = op.return_type
        if op.is_return_list and op.is_return_optional:
            # Optional[List[T]] - return None or list of parsed models
            lines.append("        if result is None:")
            lines.append("            return None")
            lines.append(f"        return [{base_type}.model_validate(item) for item in result]")
        elif op.is_return_list:
            # List[T] - return list of parsed models (empty list if None)
            lines.append("        if result is None:")
            lines.append("            return []")
            lines.append(f"        return [{base_type}.model_validate(item) for item in result]")
        elif op.is_return_optional:
            # Optional[T] - return None or parsed model
            lines.append("        if result is None:")
            lines.append("            return None")
            lines.append(f"        return {base_type}.model_validate(result)")
        else:
            # T - return parsed model (required)
            lines.append(f"        return {base_type}.model_validate(result)")
        lines.append("")

        return lines

    @staticmethod
    def _arg_type_hint(arg) -> str:
        """Get Python type hint for an argument."""
        # Map GraphQL types to Python types
        type_map = {
            "String": "str",
            "Int": "int",
            "Float": "float",
            "Boolean": "bool",
            "ID": "str",
        }

        base_type = type_map.get(arg.type_name, arg.type_name)

        if arg.is_list:
            return f"List[{base_type}]"
        return base_type

    @staticmethod
    def _type_to_var_suffix(type_name: str) -> str:
        """Convert a type name to a variable name suffix (matching QueryBuilder)."""
        name = type_name
        for suffix in ("Input", "Mutation", "Payload"):
            if name.endswith(suffix):
                name = name[:-len(suffix)]
        # Convert to camelCase
        return name[0].lower() + name[1:] if name else "arg"

    def _generate_root_client(self) -> list[str]:
        """Generate the root client class."""
        lines = [
            f"class {self.client_name}:",
            '    """Auto-generated GraphQL client.',
            "",
            "    Supports pluggable authentication via the Auth protocol.",
            "",
            "    Usage:",
            "        # Using API key (backward compatible)",
            f"        client = {self.client_name}(url='https://api.example.com/graphql', api_key='...')",
            "",
            "        # Using auth handlers",
            f"        client = {self.client_name}(url='...', auth=BearerAuth(token))",
            f"        client = {self.client_name}(url='...', auth=ApiKeyAuth(key, header_name='Authorization'))",
            "",
            "        # Execute operations",
            "        result = await client.namespace.operation(...)",
            '    """',
            "",
            "    def __init__(",
            "        self,",
            "        url: str,",
            "        auth: Optional[Auth] = None,",
            "        *,",
            "        api_key: Optional[str] = None,",
            "        timeout: float = 30.0,",
            "    ):",
            '        """Initialize the client.',
            "",
            "        Args:",
            "            url: GraphQL endpoint URL",
            "            auth: Authentication handler (BearerAuth, ApiKeyAuth, etc.)",
            "            api_key: DEPRECATED - Use auth=ApiKeyAuth(key) instead",
            "            timeout: Request timeout in seconds",
            '        """',
            "        self._executor = GraphQLExecutor(url, auth=auth, api_key=api_key, timeout=timeout)",
            "        self._query_builder = QueryBuilder()",
        ]

        # Initialize top-level namespace clients
        for child_name, child_node in sorted(self.mutation_tree.children.items()):
            child_class = f"Mutation_{to_pascal_case(child_name)}Client"
            lines.append(f"        self.{child_node.snake_name} = {child_class}(self._executor, self._query_builder)")

        lines.append("")
        lines.append("    async def close(self):")
        lines.append('        """Close the client connection."""')
        lines.append("        await self._executor.close()")
        lines.append("")
        lines.append("    async def __aenter__(self):")
        lines.append("        return self")
        lines.append("")
        lines.append("    async def __aexit__(self, exc_type, exc_val, exc_tb):")
        lines.append("        await self.close()")
        lines.append("")

        return lines
