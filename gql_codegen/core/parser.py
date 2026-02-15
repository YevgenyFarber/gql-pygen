"""GraphQL schema parser using graphql-core.

Parses .graphqls files and produces an IRSchema.
"""

import os
from typing import Any, Dict, List

from graphql import (
    EnumTypeDefinitionNode,
    InputObjectTypeDefinitionNode,
    InterfaceTypeDefinitionNode,
    ListTypeNode,
    NonNullTypeNode,
    ObjectTypeDefinitionNode,
    ScalarTypeDefinitionNode,
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
        """Initialize parser with path to schema file or directory."""
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
        return self.ir

    def _collect_schema_files(self) -> List[str]:
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

    def _process_fields(self, field_nodes) -> List[IRField]:
        """Process field definitions into IRField list."""
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

    def _process_operations(self, node: ObjectTypeDefinitionNode):
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

    def _get_type_info(self, type_node) -> Dict[str, Any]:
        """Extract type name, is_list, and is_optional from type node."""
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
            # Handle non-null inside list [Type!]
            if isinstance(type_node, NonNullTypeNode):
                type_node = type_node.type

        # Handle nested lists [[Type]] (rare but possible)
        if isinstance(type_node, ListTypeNode):
            type_node = type_node.type
            if isinstance(type_node, NonNullTypeNode):
                type_node = type_node.type

        return {
            "name": type_node.name.value,
            "is_list": is_list,
            "is_optional": is_optional,
        }

