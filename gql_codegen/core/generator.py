"""Code generator for GraphQL schemas.

Renders Jinja2 templates to produce Python code from IR.
"""

import ast
import os
import re
from typing import Any, Dict, Set

from jinja2 import Environment, PackageLoader, select_autoescape

from .ir import IRSchema


def snake_case(name: str) -> str:
    """Convert PascalCase or camelCase to snake_case."""
    s1 = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub("([a-z0-9])([A-Z])", r"\1_\2", s1).lower()


def pascal_case(name: str) -> str:
    """Convert snake_case to PascalCase."""
    return "".join(word.capitalize() for word in name.split("_"))


def upper_case(name: str) -> str:
    """Convert to UPPER_CASE."""
    return snake_case(name).upper()


def safe_docstring(text: str) -> str:
    """Escape text for use in docstrings."""
    if not text:
        return ""
    text = text.replace('"""', '\\"\\"\\"')
    if text.endswith('"'):
        text += " "
    return text


def safe_comment(text: str) -> str:
    """Make text safe for a single-line Python comment.

    Removes newlines, replaces markdown formatting, and ensures
    the text doesn't cause syntax errors when used as # comment.
    """
    if not text:
        return ""
    # Replace newlines with spaces
    text = text.replace('\n', ' ').replace('\r', '')
    # Remove markdown bold/italic markers
    text = text.replace('**', '').replace('*', '')
    # Collapse multiple spaces
    import re
    text = re.sub(r'\s+', ' ', text)
    # Truncate very long descriptions
    if len(text) > 120:
        text = text[:117] + "..."
    return text.strip()


# Python reserved keywords that cannot be used as parameter names
PYTHON_KEYWORDS = {
    'False', 'None', 'True', 'and', 'as', 'assert', 'async', 'await',
    'break', 'class', 'continue', 'def', 'del', 'elif', 'else', 'except',
    'finally', 'for', 'from', 'global', 'if', 'import', 'in', 'is',
    'lambda', 'nonlocal', 'not', 'or', 'pass', 'raise', 'return', 'try',
    'while', 'with', 'yield'
}


def safe_param_name(name: str) -> str:
    """Make a parameter name safe for Python by suffixing keywords with underscore."""
    if name in PYTHON_KEYWORDS:
        return f"{name}_"
    return name


class CodeGenerator:
    """Generates Python code from GraphQL IR."""

    # Maximum depth for field expansion in queries
    MAX_FIELD_DEPTH = 2

    def __init__(self, ir: IRSchema, output_dir: str):
        self.ir = ir
        self.output_dir = output_dir
        self.env = Environment(
            loader=PackageLoader("gql_codegen", "templates"),
            autoescape=select_autoescape(),
        )
        # Register custom filters
        self.env.filters["snake_case"] = snake_case
        self.env.filters["pascal_case"] = pascal_case
        self.env.filters["upper_case"] = upper_case
        self.env.filters["repr"] = repr
        self.env.filters["safe_docstring"] = safe_docstring
        self.env.filters["safe_comment"] = safe_comment
        self.env.filters["safe_param"] = safe_param_name
        self.env.filters["expand_fields"] = self._expand_fields_filter

    def _expand_fields_filter(self, type_name: str) -> str:
        """Jinja2 filter to expand fields for a type."""
        return self._expand_fields(type_name, depth=0)

    def _expand_fields(self, type_name: str, depth: int = 0) -> str:
        """Recursively expand fields for a type up to MAX_FIELD_DEPTH."""
        if depth > self.MAX_FIELD_DEPTH:
            return "__typename"

        # Check if it's a scalar or enum
        if type_name in self.ir.scalars or type_name in self.ir.enums:
            return ""
        if type_name in ["String", "Int", "Float", "Boolean", "ID"]:
            return ""

        # Find the type
        ir_type = self.ir.get_type_by_name(type_name)
        if not ir_type or not hasattr(ir_type, "fields"):
            return "__typename"

        lines = ["__typename"]
        for field in ir_type.fields:
            field_type = field.type_name
            # Check if field is a scalar or enum
            if field_type in self.ir.scalars or field_type in self.ir.enums:
                lines.append(field.name)
            elif field_type in ["String", "Int", "Float", "Boolean", "ID"]:
                lines.append(field.name)
            else:
                # It's a nested object - expand it
                nested = self._expand_fields(field_type, depth + 1)
                if nested:
                    lines.append(f"{field.name} {{\n                {nested}\n            }}")
                else:
                    lines.append(field.name)

        return "\n                ".join(lines)

    def generate(self):
        """Generate all code files."""
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(os.path.join(self.output_dir, "models"), exist_ok=True)
        os.makedirs(os.path.join(self.output_dir, "clients"), exist_ok=True)

        # 1. Generate scalars
        self._generate_file(
            "scalars.py.j2", "scalars.py",
            {"scalars": list(self.ir.scalars.values())}
        )

        # 2. Generate enums
        self._generate_file(
            "enums.py.j2", "enums.py",
            {"enums": list(self.ir.enums.values())}
        )

        # 3. Generate base client
        self._generate_file("base_client.py.j2", "clients/base_client.py", {})

        # 4. Generate models (modularized by source file)
        self._generate_models()

        # 5. Generate clients (grouped by operation domain)
        self._generate_clients()

        # 6. Generate __init__.py files
        self._generate_init_files()

    def _generate_file(
        self, template_name: str, output_path: str, context: Dict[str, Any]
    ):
        """Render a template and write to file."""
        template = self.env.get_template(template_name)
        content = template.render(context)

        # Validate Python syntax
        if output_path.endswith(".py"):
            try:
                ast.parse(content)
            except SyntaxError as e:
                raise ValueError(
                    f"Generated invalid Python for {output_path}: {e}\n"
                    f"Template: {template_name}"
                )

        full_path = os.path.join(self.output_dir, output_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w") as f:
            f.write(content)

    def _generate_models(self):
        """Generate model files, organized by source schema file."""
        models_by_file: Dict[str, Dict] = {}

        for type_name, file_name in self.ir.type_to_file.items():
            base_name = (
                file_name.replace(".graphqls", "")
                .replace(".", "_")
                .replace("-", "_")
            )
            if base_name not in models_by_file:
                models_by_file[base_name] = {"types": [], "interfaces": []}

            if type_name in self.ir.types:
                models_by_file[base_name]["types"].append(self.ir.types[type_name])
            elif type_name in self.ir.inputs:
                models_by_file[base_name]["types"].append(self.ir.inputs[type_name])
            elif type_name in self.ir.interfaces:
                models_by_file[base_name]["interfaces"].append(
                    self.ir.interfaces[type_name]
                )

        # Build interface field mapping for inheritance
        interface_fields = {}
        for iface in self.ir.interfaces.values():
            interface_fields[iface.name] = [f.name for f in iface.fields]

        for base_name in sorted(models_by_file.keys()):
            content = models_by_file[base_name]
            self._prepare_model_context(base_name, content, models_by_file)
            content["interface_fields"] = interface_fields
            self._generate_file("models.py.j2", f"models/{base_name}.py", content)

    def _prepare_model_context(
        self, base_name: str, content: Dict, all_models: Dict
    ):
        """Prepare cross-module imports and full type names."""
        local_types = {t.name for t in content["types"]} | {
            i.name for i in content["interfaces"]
        }
        type_to_module: Dict[str, str] = {}
        external_deps: Set[tuple] = set()

        # Find external dependencies
        for type_name in local_types:
            for dep in self.ir.dependencies.get(type_name, []):
                if (
                    dep not in local_types
                    and dep not in self.ir.scalars
                    and dep not in self.ir.enums
                ):
                    dep_file = self.ir.type_to_file.get(dep)
                    if dep_file:
                        dep_base = (
                            dep_file.replace(".graphqls", "")
                            .replace(".", "_")
                            .replace("-", "_")
                        )
                        if dep_base != base_name:
                            external_deps.add((dep_base, dep))
                            type_to_module[dep] = dep_base

        # Set full_type_name and full_interfaces for types
        for ir_type in content["types"]:
            ir_type.full_type_name = ir_type.name
            ir_type.full_interfaces = []
            for iface in ir_type.interfaces:
                if iface in type_to_module:
                    ir_type.full_interfaces.append(f"{type_to_module[iface]}.{iface}")
                else:
                    ir_type.full_interfaces.append(iface)
            for field in ir_type.fields:
                if field.type_name in type_to_module:
                    field.full_type_name = f"{type_to_module[field.type_name]}.{field.type_name}"
                else:
                    field.full_type_name = field.type_name

        # Set full_type_name for interfaces
        for interface in content["interfaces"]:
            for field in interface.fields:
                if field.type_name in type_to_module:
                    field.full_type_name = f"{type_to_module[field.type_name]}.{field.type_name}"
                else:
                    field.full_type_name = field.type_name

        # Group imports by file
        imports_by_file: Dict[str, list] = {}
        for dep_base, dep_type in external_deps:
            if dep_base not in imports_by_file:
                imports_by_file[dep_base] = []
            imports_by_file[dep_base].append(dep_type)

        content["external_imports"] = imports_by_file

    def _generate_clients(self):
        """Generate client files grouped by operation domain."""
        clients: Dict[str, list] = {}
        for op in self.ir.queries + self.ir.mutations:
            domain = op.name.split("_")[0] if "_" in op.name else op.name[:7]
            if domain not in clients:
                clients[domain] = []
            clients[domain].append(op)

        for domain, ops in clients.items():
            client_name = pascal_case(domain)
            self._generate_file(
                "client.py.j2",
                f"clients/{snake_case(domain)}_client.py",
                {"client_name": client_name, "operations": ops},
            )

    def _generate_init_files(self):
        """Generate __init__.py files for packages."""
        # Root __init__.py
        with open(os.path.join(self.output_dir, "__init__.py"), "w") as f:
            f.write('"""Generated GraphQL client package."""\n')

        # models/__init__.py - export all models
        model_files = [
            f[:-3]  # Remove .py
            for f in os.listdir(os.path.join(self.output_dir, "models"))
            if f.endswith(".py") and f != "__init__.py"
        ]
        with open(os.path.join(self.output_dir, "models/__init__.py"), "w") as f:
            f.write('"""Generated GraphQL models."""\n\n')
            for model_file in sorted(model_files):
                f.write(f"from .{model_file} import *\n")

        # clients/__init__.py - export all clients
        client_files = [
            f[:-3]  # Remove .py
            for f in os.listdir(os.path.join(self.output_dir, "clients"))
            if f.endswith(".py") and f != "__init__.py"
        ]
        with open(os.path.join(self.output_dir, "clients/__init__.py"), "w") as f:
            f.write('"""Generated GraphQL clients."""\n\n')
            f.write("from .base_client import GraphQLClient, GraphQLError\n")
            for client_file in sorted(client_files):
                if client_file != "base_client":
                    f.write(f"from .{client_file} import *\n")

