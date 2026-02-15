"""Core modules for GraphQL code generation."""

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
from .parser import SchemaParser
from .query_builder import FieldSelection, FieldSelectionMode, QueryBuilder
from .executor import GraphQLError, GraphQLExecutor
from .client_generator import ClientGenerator

__all__ = [
    # IR types
    "IRArgument",
    "IREnum",
    "IREnumValue",
    "IRField",
    "IRInterface",
    "IROperation",
    "IRScalar",
    "IRSchema",
    "IRType",
    # Parser
    "SchemaParser",
    # Query Builder
    "FieldSelection",
    "FieldSelectionMode",
    "QueryBuilder",
    # Executor
    "GraphQLError",
    "GraphQLExecutor",
    # Client Generator
    "ClientGenerator",
]

