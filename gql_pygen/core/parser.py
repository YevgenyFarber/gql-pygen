"""GraphQL schema parser using graphql-core.

Parses .graphqls files and produces an IRSchema.
"""

import os
from typing import Any

from graphql import (
    EnumTypeDefinitionNode,
    InputObjectTypeDefinitionNode,
    InterfaceTypeDefinitionNode,
    ListTypeNode,
    NamedTypeNode,
    NonNullTypeNode,
    ObjectTypeDefinitionNode,
    ObjectTypeExtensionNode,
    ScalarTypeDefinitionNode,
    TypeNode,
    parse,
)

from .ir import (
    IRArgument,
    IREnum,
    IREnumValue,
    IRField,
    IRInterface,
    IROperation,
    IRScalar,
    IRSchema,
    IRType,
)


class SchemaParser:
    """Parses GraphQL schema files into IR."""

    def __init__(self, schema_path: str):
        """Initialize a parser with a path to a schema file or directory."""
        self.schema_path = schema_path
        self.ir = IRSchema()
        self.current_file = ""

    def parse_all(self) -> IRSchema:
        """Parse all schema files and return the complete IR."""
        schema_files = self._collect_schema_files()

        for file_path in schema_files:
            self.current_file = os.path.basename(file_path)
            with open(file_path) as f:
                content = f.read()
                try:
                    ast = parse(content)
                    self._process_ast(ast)
                except Exception as e:
                    print(f"Error parsing {self.current_file}: {e}")
                    raise

        self._resolve_dependencies()
        # Discover nested operations after all types are parsed
        self._discover_nested_operations()
        return self.ir

    def _collect_schema_files(self) -> list[str]:
        """Collect all .graphqls files from path."""
        files = []
        if os.path.isfile(self.schema_path):
            if self.schema_path.endswith(".graphqls"):
                files.append(self.schema_path)
        else:
            for root, _, filenames in os.walk(self.schema_path):
                for filename in filenames:
                    if filename.endswith(".graphqls"):
                        files.append(os.path.join(root, filename))
        return sorted(files)

    def _resolve_dependencies(self):
        """Track type dependencies for cross-module imports."""
        all_types = {**self.ir.types, **self.ir.inputs, **self.ir.interfaces}
        for type_name, ir_type in all_types.items():
            deps = set()
            if hasattr(ir_type, "fields"):
                for field in ir_type.fields:
                    deps.add(field.type_name)
            if hasattr(ir_type, "interfaces"):
                for interface in ir_type.interfaces:
                    deps.add(interface)
            self.ir.dependencies[type_name] = deps

    def _process_ast(self, ast):
        """Process GraphQL AST and populate IR."""
        for definition in ast.definitions:
            if isinstance(definition, ScalarTypeDefinitionNode):
                self._process_scalar(definition)
            elif isinstance(definition, EnumTypeDefinitionNode):
                self._process_enum(definition)
            elif isinstance(definition, InterfaceTypeDefinitionNode):
                self._process_interface(definition)
            elif isinstance(definition, ObjectTypeDefinitionNode):
                self._process_object_type(definition)
            elif isinstance(definition, ObjectTypeExtensionNode):
                # Handle 'extend type Query/Mutation' as operations
                self._process_object_extension(definition)
            elif isinstance(definition, InputObjectTypeDefinitionNode):
                self._process_input_type(definition)

    def _process_scalar(self, node: ScalarTypeDefinitionNode):
        name = node.name.value
        self.ir.scalars[name] = IRScalar(
            name=name,
            description=node.description.value if node.description else None,
        )
        self.ir.type_to_file[name] = self.current_file

    def _process_enum(self, node: EnumTypeDefinitionNode):
        name = node.name.value
        values = [
            IREnumValue(
                name=v.name.value,
                description=v.description.value if v.description else None,
            )
            for v in node.values
        ]
        self.ir.enums[name] = IREnum(
            name=name,
            values=values,
            description=node.description.value if node.description else None,
        )
        self.ir.type_to_file[name] = self.current_file

    def _process_interface(self, node: InterfaceTypeDefinitionNode):
        name = node.name.value
        fields = self._process_fields(node.fields)
        self.ir.interfaces[name] = IRInterface(
            name=name,
            fields=fields,
            description=node.description.value if node.description else None,
        )
        self.ir.type_to_file[name] = self.current_file

    def _process_object_type(self, node: ObjectTypeDefinitionNode):
        name = node.name.value
        if name in ("Query", "Mutation"):
            self._process_operations(node)
        else:
            fields = self._process_fields(node.fields)
            interfaces = [i.name.value for i in node.interfaces]

            # Check if the type already exists (from earlier extension processing)
            if name in self.ir.types:
                existing = self.ir.types[name]
                # Merge: add base fields + description, keep existing extension fields
                existing_names = {f.name for f in existing.fields}
                for field in fields:
                    if field.name not in existing_names:
                        existing.fields.append(field)
                # Update metadata from the base type definition
                existing.interfaces = interfaces
                if node.description:
                    existing.description = node.description.value
            else:
                self.ir.types[name] = IRType(
                    name=name,
                    fields=fields,
                    interfaces=interfaces,
                    description=node.description.value if node.description else None,
                )
            self.ir.type_to_file[name] = self.current_file

    def _process_input_type(self, node: InputObjectTypeDefinitionNode):
        name = node.name.value
        fields = self._process_fields(node.fields)
        self.ir.inputs[name] = IRType(
            name=name,
            fields=fields,
            description=node.description.value if node.description else None,
            is_input=True,
        )
        self.ir.type_to_file[name] = self.current_file

    def _process_object_extension(self, node: ObjectTypeExtensionNode):
        """Process 'extend type' definitions.

        For Query/Mutation: treats fields as operations.
        For other types: merges fields into the existing type definition.
        """
        name = node.name.value
        if name in ("Query", "Mutation"):
            self._process_operations(node)
        else:
            # Merge extension fields into the existing type
            self._merge_extension_fields(name, node)

    def _merge_extension_fields(self, type_name: str, node: ObjectTypeExtensionNode):
        """Merge extension fields into an existing type.

        This handles `extend type PolicyMutations { ... }` by adding the
        extension fields to the existing PolicyMutations type.
        """
        extension_fields = self._process_fields(node.fields)

        # Check if the type already exists
        if type_name in self.ir.types:
            existing_type = self.ir.types[type_name]
            # Track existing field names to avoid duplicates
            existing_names = {f.name for f in existing_type.fields}
            for field in extension_fields:
                if field.name not in existing_names:
                    existing_type.fields.append(field)
                    existing_names.add(field.name)
        else:
            # Type doesn't exist yet, create it
            self.ir.types[type_name] = IRType(
                name=type_name,
                fields=extension_fields,
                description=None,
            )
            self.ir.type_to_file[type_name] = self.current_file

    def _process_fields(self, field_nodes) -> list[IRField]:
        """Process field definitions into the IRField list."""
        fields = []
        for node in field_nodes:
            type_info = self._get_type_info(node.type)
            args = []
            if hasattr(node, "arguments") and node.arguments:
                for arg_node in node.arguments:
                    arg_type_info = self._get_type_info(arg_node.type)
                    args.append(
                        IRArgument(
                            name=arg_node.name.value,
                            type_name=arg_type_info["name"],
                            is_list=arg_type_info["is_list"],
                            is_optional=arg_type_info["is_optional"],
                            description=arg_node.description.value
                            if arg_node.description
                            else None,
                        )
                    )
            fields.append(
                IRField(
                    name=node.name.value,
                    type_name=type_info["name"],
                    is_list=type_info["is_list"],
                    is_optional=type_info["is_optional"],
                    description=node.description.value if node.description else None,
                    arguments=args,
                )
            )
        return fields

    def _process_operations(
        self, node: ObjectTypeDefinitionNode | ObjectTypeExtensionNode
    ):
        """Process Query or Mutation type into operations."""
        op_type = "query" if node.name.value == "Query" else "mutation"
        for field in node.fields:
            type_info = self._get_type_info(field.type)
            args = []
            for arg_node in field.arguments:
                arg_type_info = self._get_type_info(arg_node.type)
                args.append(
                    IRArgument(
                        name=arg_node.name.value,
                        type_name=arg_type_info["name"],
                        is_list=arg_type_info["is_list"],
                        is_optional=arg_type_info["is_optional"],
                        description=arg_node.description.value
                        if arg_node.description
                        else None,
                    )
                )
            op = IROperation(
                name=field.name.value,
                operation_type=op_type,
                arguments=args,
                return_type=type_info["name"],
                is_return_list=type_info["is_list"],
                is_return_optional=type_info["is_optional"],
                description=field.description.value if field.description else None,
            )
            if op_type == "query":
                self.ir.queries.append(op)
            else:
                self.ir.mutations.append(op)

    @staticmethod
    def _get_type_info(type_node: TypeNode) -> dict[str, Any]:
        """Extract the type name, is_list, and is_optional from the type node."""
        is_optional = True
        is_list = False

        # NonNull wrapper means not optional
        if isinstance(type_node, NonNullTypeNode):
            is_optional = False
            type_node = type_node.type

        # List wrapper
        if isinstance(type_node, ListTypeNode):
            is_list = True
            type_node = type_node.type
            # Handle non-null inside a list [Type!]
            if isinstance(type_node, NonNullTypeNode):
                type_node = type_node.type

        # Handle nested lists [[Type]] (rare but possible)
        if isinstance(type_node, ListTypeNode):
            type_node = type_node.type
            if isinstance(type_node, NonNullTypeNode):
                type_node = type_node.type

        # After unwrapping, we should have a NamedTypeNode
        assert isinstance(type_node, NamedTypeNode), f"Expected NamedTypeNode, got {type(type_node)}"

        return {
            "name": type_node.name.value,
            "is_list": is_list,
            "is_optional": is_optional,
        }

    def _discover_nested_operations(self):
        """Discover nested operations in namespace types.

        Traverses types ending with 'Mutations' or 'Queries' to find
        actual operations (fields with input arguments that return non-namespace types).

        Example path: Mutation.policy -> PolicyMutations.internetFirewall ->
                      InternetFirewallPolicyMutations.addRule
        Result: IROperation with path=[ "policy", "internetFirewall", "addRule"]
        """
        nested_queries: list[IROperation] = []
        nested_mutations: list[IROperation] = []

        # Process top-level queries/mutations that return namespace types
        for op in self.ir.queries:
            if self.ir.is_namespace_type(op.return_type):
                # This is a namespace, recurse into it
                self._traverse_namespace(
                    type_name=op.return_type,
                    op_type="query",
                    path=[op.name],
                    parent_args=op.arguments,
                    results=nested_queries
                )

        for op in self.ir.mutations:
            if self.ir.is_namespace_type(op.return_type):
                self._traverse_namespace(
                    type_name=op.return_type,
                    op_type="mutation",
                    path=[op.name],
                    parent_args=op.arguments,
                    results=nested_mutations
                )

        # Add discovered nested operations
        self.ir.queries.extend(nested_queries)
        self.ir.mutations.extend(nested_mutations)

    def _traverse_namespace(
        self,
        type_name: str,
        op_type: str,
        path: list[str],
        parent_args: list[IRArgument],
        results: list[IROperation]
    ):
        """Recursively traverse a namespace type to find operations.

        Args:
            type_name: The namespace type to explore (e.g., PolicyMutations)
            op_type: 'query' or 'mutation'
            path: Current path from root (e.g., ["policy"])
            parent_args: Arguments accumulated from parent namespaces
            results: List to append discovered operations to
        """
        type_def = self.ir.types.get(type_name)
        if not type_def:
            return

        for field in type_def.fields:
            field_path = path + [field.name]

            if self.ir.is_namespace_type(field.type_name):
                # This is another namespace - recurse deeper
                # Accumulate any arguments from this field
                accumulated_args = parent_args + field.arguments
                self._traverse_namespace(
                    type_name=field.type_name,
                    op_type=op_type,
                    path=field_path,
                    parent_args=accumulated_args,
                    results=results
                )
            else:
                # This is a leaf operation (returns a non-namespace type)
                # Only include it if it has arguments or returns a meaningful type
                # (skip placeholder fields)
                if field.name == "placeholder" and field.type_name == "bool":
                    continue

                op = IROperation(
                    name=field.name,
                    operation_type=op_type,
                    arguments=field.arguments,
                    return_type=field.type_name,
                    is_return_list=field.is_list,
                    is_return_optional=field.is_optional,
                    description=field.description,
                    path=field_path,
                    parent_arguments=list(parent_args),  # Copy to avoid mutation
                )
                results.append(op)
