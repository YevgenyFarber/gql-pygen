"""Intermediate Representation (IR) for GraphQL schemas.

This module defines dataclasses that represent GraphQL schema constructs
in a language-agnostic way, suitable for code generation.
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class IRField:
    """Represents a field in a GraphQL type or interface."""
    name: str
    type_name: str
    is_list: bool = False
    is_optional: bool = True  # True if nullable (no ! in GraphQL)
    description: str | None = None
    arguments: list["IRArgument"] = field(default_factory=list)
    # Runtime-populated by generator for cross-module refs
    full_type_name: str = ""

    def __post_init__(self):
        if not self.full_type_name:
            self.full_type_name = self.type_name


@dataclass
class IRArgument:
    """Represents an argument to a field or operation."""
    name: str
    type_name: str
    is_list: bool = False
    is_optional: bool = True
    default_value: Any = None
    description: str | None = None


@dataclass
class IREnumValue:
    """Represents a single value in a GraphQL enum."""
    name: str
    description: str | None = None


@dataclass
class IREnum:
    """Represents a GraphQL enum type."""
    name: str
    values: list[IREnumValue]
    description: str | None = None


@dataclass
class IRType:
    """Represents a GraphQL object type or input type."""
    name: str
    fields: list[IRField]
    interfaces: list[str] = field(default_factory=list)
    description: str | None = None
    is_input: bool = False
    # Runtime-populated by generator
    full_interfaces: list[str] = field(default_factory=list)


@dataclass
class IRInterface:
    """Represents a GraphQL interface type."""
    name: str
    fields: list[IRField]
    description: str | None = None


@dataclass
class IRScalar:
    """Represents a GraphQL scalar type."""
    name: str
    description: str | None = None


@dataclass
class IROperation:
    """Represents a GraphQL query or mutation.

    For nested operations (e.g., policy.internetFirewall.addRule),
    the path field contains the full traversal path from the root.
    """
    name: str
    operation_type: str  # 'query' or 'mutation'
    arguments: list[IRArgument]
    return_type: str
    is_return_list: bool = False
    is_return_optional: bool = True
    description: str | None = None
    # Full path from root, e.g., ["policy", "internetFirewall", "addRule"]
    path: list[str] = field(default_factory=list)
    # Arguments collected from parent namespace fields (e.g., accountId from policy(accountId))
    parent_arguments: list[IRArgument] = field(default_factory=list)

    def __post_init__(self):
        # If a path is empty, set it to just the operation name
        if not self.path:
            self.path = [self.name]

    @property
    def full_name(self) -> str:
        """Return underscore-joined path for method names, e.g., 'policy_internet_firewall_add_rule'."""
        return "_".join(self._to_snake_case(p) for p in self.path)

    @property
    def all_arguments(self) -> list[IRArgument]:
        """Return all arguments including parent namespace arguments."""
        return self.parent_arguments + self.arguments

    @staticmethod
    def _to_snake_case(name: str) -> str:
        """Convert camelCase to snake_case."""
        import re
        s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
        return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()


@dataclass
class IRSchema:
    """Complete intermediate representation of a GraphQL schema."""
    scalars: dict[str, IRScalar] = field(default_factory=dict)
    enums: dict[str, IREnum] = field(default_factory=dict)
    types: dict[str, IRType] = field(default_factory=dict)
    inputs: dict[str, IRType] = field(default_factory=dict)
    interfaces: dict[str, IRInterface] = field(default_factory=dict)
    queries: list[IROperation] = field(default_factory=list)
    mutations: list[IROperation] = field(default_factory=list)

    # Metadata for modularization
    type_to_file: dict[str, str] = field(default_factory=dict)
    dependencies: dict[str, set[str]] = field(default_factory=dict)

    def get_type_by_name(self, name: str) -> IRType | IRInterface | None:
        """Look up a type or interface by name."""
        if name in self.types:
            return self.types[name]
        if name in self.inputs:
            return self.inputs[name]
        if name in self.interfaces:
            return self.interfaces[name]
        return None

    def get_all_types(self) -> dict[str, IRType | IRInterface]:
        """Return all types and interfaces."""
        result = {}
        result.update(self.types)
        result.update(self.inputs)
        result.update(self.interfaces)
        return result

    @property
    def all_operations(self) -> list[IROperation]:
        """Return all queries and mutations."""
        return self.queries + self.mutations

    @staticmethod
    def is_namespace_type(type_name: str) -> bool:
        """Check if a type is a namespace type (ends with Mutations or Queries)."""
        return type_name.endswith("Mutations") or type_name.endswith("Queries")
