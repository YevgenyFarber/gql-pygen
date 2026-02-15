"""Query builder for GraphQL operations.

Constructs GraphQL query/mutation strings from operation metadata,
with support for field selection.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .ir import IROperation, IRSchema, IRType


class FieldSelectionMode(Enum):
    """Field selection modes for queries."""
    ALL = "all"       # Request all fields recursively
    MINIMAL = "minimal"  # Request only ID and __typename
    CUSTOM = "custom"    # User-specified fields


@dataclass
class FieldSelection:
    """Configuration for which fields to include in a query."""
    mode: FieldSelectionMode = FieldSelectionMode.ALL
    custom_fields: list[str] = field(default_factory=list)
    max_depth: int = 10  # Prevent infinite recursion

    # Predefined selections
    ALL: "FieldSelection" = None  # Set below
    MINIMAL: "FieldSelection" = None  # Set below

    @classmethod
    def select(cls, *fields: str) -> "FieldSelection":
        """Create a custom field selection."""
        return cls(mode=FieldSelectionMode.CUSTOM, custom_fields=list(fields))


# Initialize class-level constants
FieldSelection.ALL = FieldSelection(mode=FieldSelectionMode.ALL)
FieldSelection.MINIMAL = FieldSelection(mode=FieldSelectionMode.MINIMAL)


class QueryBuilder:
    """Builds GraphQL query strings from operation metadata."""

    def __init__(self, schema: IRSchema):
        """Initialize with schema for type lookups."""
        self.schema = schema
        self._query_cache: dict[str, str] = {}
        # Types that are considered scalars (no subfields)
        self._scalar_types = {
            "String", "Int", "Float", "Boolean", "ID",
            # Custom scalars from Cato schema
            "DateTime", "Date", "Time", "JSON", "Long", "Any",
            "IPAddress", "Asn", "Domain", "Email", "Fqdn",
            "GlobalIPRange", "Hostname", "IPSubnet", "Mac",
            "Port", "SID", "Sha256", "Url", "CountryCode",
        }
        # Add schema-defined scalars
        self._scalar_types.update(schema.scalars.keys())
        # Add enums as scalars (no subfields)
        self._scalar_types.update(schema.enums.keys())

    def build(
        self,
        operation: IROperation,
        fields: FieldSelection = FieldSelection.ALL,
    ) -> str:
        """Build a GraphQL query/mutation string.

        Args:
            operation: The operation metadata
            fields: Field selection configuration

        Returns:
            Complete GraphQL query string
        """
        cache_key = f"{operation.full_name}:{fields.mode.value}"
        if cache_key in self._query_cache and fields.mode != FieldSelectionMode.CUSTOM:
            return self._query_cache[cache_key]

        # Build variable declarations
        var_decls = self._build_variable_declarations(operation)

        # Build the nested field path
        body = self._build_operation_body(operation, fields)

        # Assemble the query
        op_type = operation.operation_type
        op_name = self._to_pascal_case(operation.full_name)

        query = f"{op_type} {op_name}({var_decls}) {{\n{body}\n}}"

        # Cache if not custom
        if fields.mode != FieldSelectionMode.CUSTOM:
            self._query_cache[cache_key] = query

        return query

    def _build_variable_declarations(self, operation: IROperation) -> str:
        """Build the variable declaration part: ($accountId: ID!, $input: SomeInput!)"""
        decls = []
        var_mapping = self._get_variable_mapping(operation)

        for arg, var_name in var_mapping:
            type_str = arg.type_name
            if arg.is_list:
                type_str = f"[{type_str}]"
            if not arg.is_optional:
                type_str = f"{type_str}!"

            decls.append(f"${var_name}: {type_str}")

        return ", ".join(decls)

    def _get_variable_mapping(self, operation: IROperation) -> list[tuple]:
        """Get a list of (arg, variable_name) tuples, handling duplicate names."""
        mapping = []
        seen_names: set[str] = set()

        for arg in operation.all_arguments:
            var_name = arg.name
            if var_name in seen_names:
                # Create unique name based on type
                var_name = f"{arg.name}_{self._type_to_var_suffix(arg.type_name)}"
            seen_names.add(var_name)
            mapping.append((arg, var_name))

        return mapping

    def _build_operation_body(
        self,
        operation: IROperation,
        fields: FieldSelection,
    ) -> str:
        """Build the body of the operation with nested path."""
        indent = "  "
        lines = []

        # Get variable mapping for proper variable references
        var_mapping = self._get_variable_mapping(operation)
        var_name_by_arg = {id(arg): var_name for arg, var_name in var_mapping}

        # Build the nested path, e.g., policy { internetFirewall { addRule { ... } } }
        path = operation.path
        parent_args = operation.parent_arguments
        op_args = operation.arguments

        # Track which parent arg we're at
        parent_arg_idx = 0

        for i, segment in enumerate(path):
            current_indent = indent * (i + 1)

            # Determine which arguments belong to this level
            if i < len(path) - 1:
                # This is a namespace level
                # Heuristic: each namespace level gets one parent arg
                if parent_arg_idx < len(parent_args):
                    level_args = [parent_args[parent_arg_idx]]
                    parent_arg_idx += 1
                else:
                    level_args = []
            else:
                # This is the operation level - use operation args
                level_args = op_args

            args_str = self._build_field_arguments_with_mapping(level_args, var_name_by_arg)
            field_call = f"{segment}{args_str}"
            lines.append(f"{current_indent}{field_call} {{")

        # Add the return type fields
        return_fields = self._build_return_fields(
            operation.return_type,
            fields,
            depth=len(path) + 1,
        )
        lines.append(return_fields)

        # Close all the braces
        for i in range(len(path) - 1, -1, -1):
            current_indent = indent * (i + 1)
            lines.append(f"{current_indent}}}")

        return "\n".join(lines)

    def _build_field_arguments(self, args: list) -> str:
        """Build argument string for a field: (accountId: $accountId, input: $input)"""
        if not args:
            return ""

        arg_strs = []
        for arg in args:
            # Use the argument name as variable name (for simple cases)
            arg_strs.append(f"{arg.name}: ${arg.name}")

        return f"({', '.join(arg_strs)})"

    def _build_field_arguments_with_mapping(self, args: list, var_name_by_arg: dict[int, str]) -> str:
        """Build argument string using variable mapping for duplicate handling."""
        if not args:
            return ""

        arg_strs = []
        for arg in args:
            var_name = var_name_by_arg.get(id(arg), arg.name)
            arg_strs.append(f"{arg.name}: ${var_name}")

        return f"({', '.join(arg_strs)})"

    def _build_return_fields(
        self,
        type_name: str,
        fields: FieldSelection,
        depth: int,
    ) -> str:
        """Build field selection for a return type."""
        indent = "  " * depth

        # Check depth limit
        if depth > fields.max_depth:
            return f"{indent}__typename"

        # Handle scalars
        if self._is_scalar(type_name):
            return ""  # Scalars don't need subfields

        # Get type definition
        type_def = self.schema.get_type_by_name(type_name)
        if not type_def:
            return f"{indent}__typename"

        if fields.mode == FieldSelectionMode.MINIMAL:
            return self._build_minimal_fields(type_def, indent)
        elif fields.mode == FieldSelectionMode.CUSTOM:
            return self._build_custom_fields(type_def, fields.custom_fields, indent, depth)
        else:  # ALL
            return self._build_all_fields(type_def, indent, depth, fields)

    def _build_minimal_fields(self, type_def: IRType, indent: str) -> str:
        """Build minimal field selection (id + __typename)."""
        lines = [f"{indent}__typename"]

        for ir_field in type_def.fields:
            if ir_field.name in ("id", "ID", "status", "name"):
                lines.append(f"{indent}{ir_field.name}")

        return "\n".join(lines)

    def _build_custom_fields(
        self,
        type_def: IRType,
        custom_fields: list[str],
        indent: str,
        depth: int,
    ) -> str:
        """Build custom field selection based on field paths."""
        lines = [f"{indent}__typename"]

        # Parse custom fields into a tree structure
        field_tree: dict[str, Any] = {}
        for field_path in custom_fields:
            parts = field_path.split(".")
            current = field_tree
            for part in parts:
                if part == "*":
                    current["*"] = True
                    break
                if part not in current:
                    current[part] = {}
                current = current[part]

        # Build fields from tree
        for ir_field in type_def.fields:
            if ir_field.name in field_tree or "*" in field_tree:
                if self._is_scalar(ir_field.type_name):
                    lines.append(f"{indent}{ir_field.name}")
                else:
                    subfields = field_tree.get(ir_field.name, {})
                    if "*" in field_tree:
                        subfields = {"*": True}
                    lines.append(f"{indent}{ir_field.name} {{")
                    # Recurse for nested types
                    nested_type = self.schema.get_type_by_name(ir_field.type_name)
                    if nested_type:
                        sub_custom = [
                            f[len(ir_field.name)+1:]
                            for f in custom_fields
                            if f.startswith(f"{ir_field.name}.")
                        ] or (["*"] if "*" in subfields else [])
                        lines.append(self._build_custom_fields(
                            nested_type, sub_custom, indent + "  ", depth + 1
                        ))
                    lines.append(f"{indent}}}")

        return "\n".join(lines)

    def _build_all_fields(
        self,
        type_def: IRType,
        indent: str,
        depth: int,
        fields: FieldSelection,
        visited: set[str] | None = None,
    ) -> str:
        """Build complete field selection (all fields recursively)."""
        if visited is None:
            visited = set()

        # Prevent infinite recursion for circular references
        if type_def.name in visited:
            return f"{indent}__typename"
        visited = visited | {type_def.name}

        lines = []

        for ir_field in type_def.fields:
            if self._is_scalar(ir_field.type_name):
                lines.append(f"{indent}{ir_field.name}")
            else:
                # Check if nested type exists
                nested_type = self.schema.get_type_by_name(ir_field.type_name)
                if nested_type and depth < fields.max_depth:
                    lines.append(f"{indent}{ir_field.name} {{")
                    lines.append(self._build_all_fields(
                        nested_type, indent + "  ", depth + 1, fields, visited
                    ))
                    lines.append(f"{indent}}}")
                else:
                    # Too deep or unknown type - just get __typename
                    lines.append(f"{indent}{field.name} {{ __typename }}")

        return "\n".join(lines) if lines else f"{indent}__typename"

    def _is_scalar(self, type_name: str) -> bool:
        """Check if a type is a scalar (no subfields)."""
        return type_name in self._scalar_types

    def _to_pascal_case(self, snake_str: str) -> str:
        """Convert snake_case to PascalCase for operation names."""
        return "".join(word.capitalize() for word in snake_str.split("_"))

    def _type_to_var_suffix(self, type_name: str) -> str:
        """Convert a type name to a variable name suffix."""
        # Remove common suffixes for cleaner names
        name = type_name
        for suffix in ("Input", "Mutation", "Payload"):
            if name.endswith(suffix):
                name = name[:-len(suffix)]
        return name[0].lower() + name[1:] if name else "arg"

