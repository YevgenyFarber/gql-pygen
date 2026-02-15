"""Intermediate Representation (IR) for GraphQL schemas.

This module defines dataclasses that represent GraphQL schema constructs
in a language-agnostic way, suitable for code generation.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set


@dataclass
class IRField:
    """Represents a field in a GraphQL type or interface."""
    name: str
    type_name: str
    is_list: bool = False
    is_optional: bool = True  # True if nullable (no ! in GraphQL)
    description: Optional[str] = None
    arguments: List["IRArgument"] = field(default_factory=list)
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
    description: Optional[str] = None


@dataclass
class IREnumValue:
    """Represents a single value in a GraphQL enum."""
    name: str
    description: Optional[str] = None


@dataclass
class IREnum:
    """Represents a GraphQL enum type."""
    name: str
    values: List[IREnumValue]
    description: Optional[str] = None


@dataclass
class IRType:
    """Represents a GraphQL object type or input type."""
    name: str
    fields: List[IRField]
    interfaces: List[str] = field(default_factory=list)
    description: Optional[str] = None
    is_input: bool = False
    # Runtime-populated by generator
    full_interfaces: List[str] = field(default_factory=list)


@dataclass
class IRInterface:
    """Represents a GraphQL interface type."""
    name: str
    fields: List[IRField]
    description: Optional[str] = None


@dataclass
class IRScalar:
    """Represents a GraphQL scalar type."""
    name: str
    description: Optional[str] = None


@dataclass
class IROperation:
    """Represents a GraphQL query or mutation."""
    name: str
    operation_type: str  # 'query' or 'mutation'
    arguments: List[IRArgument]
    return_type: str
    is_return_list: bool = False
    is_return_optional: bool = True
    description: Optional[str] = None


@dataclass
class IRSchema:
    """Complete intermediate representation of a GraphQL schema."""
    scalars: Dict[str, IRScalar] = field(default_factory=dict)
    enums: Dict[str, IREnum] = field(default_factory=dict)
    types: Dict[str, IRType] = field(default_factory=dict)
    inputs: Dict[str, IRType] = field(default_factory=dict)
    interfaces: Dict[str, IRInterface] = field(default_factory=dict)
    queries: List[IROperation] = field(default_factory=list)
    mutations: List[IROperation] = field(default_factory=list)

    # Metadata for modularization
    type_to_file: Dict[str, str] = field(default_factory=dict)
    dependencies: Dict[str, Set[str]] = field(default_factory=dict)

    def get_type_by_name(self, name: str) -> Optional[IRType | IRInterface]:
        """Look up a type or interface by name."""
        if name in self.types:
            return self.types[name]
        if name in self.inputs:
            return self.inputs[name]
        if name in self.interfaces:
            return self.interfaces[name]
        return None

    def get_all_types(self) -> Dict[str, IRType | IRInterface]:
        """Return all types and interfaces."""
        result = {}
        result.update(self.types)
        result.update(self.inputs)
        result.update(self.interfaces)
        return result

