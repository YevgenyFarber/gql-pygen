"""Core modules for GraphQL code generation."""

from .auth import (
    ApiKeyAuth,
    Auth,
    BasicAuth,
    BearerAuth,
    HeaderAuth,
    NoAuth,
)
from .client_generator import ClientGenerator
from .executor import GraphQLError, GraphQLExecutor
from .hooks import (
    AddHeaderHook,
    FilterTypesHook,
    HookRunner,
    PostGenerateHook,
    PreGenerateHook,
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
from .parser import SchemaParser
from .query_builder import FieldSelection, FieldSelectionMode, QueryBuilder
from .scalars import (
    DateHandler,
    DateTimeHandler,
    JSONHandler,
    ScalarHandler,
    ScalarRegistry,
    UUIDHandler,
)

__all__ = [
    # Auth
    "Auth",
    "ApiKeyAuth",
    "BearerAuth",
    "BasicAuth",
    "HeaderAuth",
    "NoAuth",
    # Scalars
    "ScalarHandler",
    "ScalarRegistry",
    "DateTimeHandler",
    "DateHandler",
    "UUIDHandler",
    "JSONHandler",
    # Hooks
    "PreGenerateHook",
    "PostGenerateHook",
    "AddHeaderHook",
    "FilterTypesHook",
    "HookRunner",
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

