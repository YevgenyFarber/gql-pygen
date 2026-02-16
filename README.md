# gql-pygen

**GraphQL to Python Code Generator** — Generate typed Pydantic models and async clients from GraphQL schemas.

## Features

- 🎯 **Typed Pydantic Models** — All GraphQL types, inputs, and enums become Pydantic models with full IDE autocomplete
- 🔗 **Nested Client** — Access operations via intuitive paths like `client.policy.firewall.add_rule(...)`
- ⚡ **Async & Sync Support** — Generate async clients (default) or sync clients with `--sync` flag
- ✅ **Response Parsing** — Responses are automatically validated and converted to typed models
- 🎛️ **Field Selection** — Request ALL fields, MINIMAL fields, or custom field sets
- 📦 **Archive Support** — Works with `.graphqls` files, directories, `.zip`, `.tar.gz`, and `.tgz` archives
- 🔌 **Extensible** — Custom auth, templates, scalar handlers, and generation hooks

## Installation

```bash
pip install gql-pygen
```

Or with [uv](https://github.com/astral-sh/uv):

```bash
uv add gql-pygen
```

## Quick Start

### 1. Generate Pydantic Models

```bash
gql-pygen generate -s ./schema.graphqls -o ./generated
```

This creates:
- `generated/models/` — Pydantic models for all types
- `generated/enums.py` — All GraphQL enums
- `generated/scalars.py` — Custom scalar definitions

### 2. Generate Typed Client

```bash
gql-pygen client -s ./schema.graphqls -o ./client.py --client-name MyAPIClient
```

This creates a single file with:
- Nested client classes matching your schema structure
- Typed async methods for all queries and mutations
- Automatic response parsing with `model_validate()`

### 3. Use the Client

```python
import asyncio
from generated.client import MyAPIClient
from generated.models import CreateUserInput

async def main():
    async with MyAPIClient(url="https://api.example.com/graphql", api_key="...") as client:
        # Full IDE autocomplete on nested paths
        result = await client.users.create_user(
            input=CreateUserInput(name="Alice", email="alice@example.com")
        )

        # Response is already typed — no manual parsing needed
        print(f"Created user: {result.user.id}")

asyncio.run(main())
```

## CLI Reference

### `gql-pygen generate`

Generate Pydantic models from a GraphQL schema.

```bash
gql-pygen generate [OPTIONS]

Options:
  -s, --schema PATH        Path to schema file, directory, or archive [required]
  -o, --output PATH        Output directory for generated code [required]
  -t, --templates PATH     Custom template directory (overrides built-in templates)
  --async                  Generate async clients (async def + await). Default: sync
  -v, --verbose            Enable verbose output
```

**Examples:**

```bash
# From a directory of .graphqls files (sync mode, default)
gql-pygen generate -s ./schema -o ./generated

# Generate async clients
gql-pygen generate -s ./schema -o ./generated --async

# From an archive
gql-pygen generate -s ./schema-bundle.tgz -o ./generated

# With custom templates
gql-pygen generate -s ./schema -o ./generated --templates ./my_templates
```

### `gql-pygen client`

Generate a typed client with all operations. By default generates async clients.

```bash
gql-pygen client [OPTIONS]

Options:
  -s, --schema PATH        Path to schema file, directory, or archive [required]
  -o, --output PATH        Output file for generated client [required]
  -n, --client-name TEXT   Client class name (default: GraphQLClient)
  --async                  Generate async clients (default: True)
  --sync                   Generate sync clients instead of async
  -v, --verbose            Enable verbose output
```

**Examples:**

```bash
# Generate async client (default)
gql-pygen client -s ./schema.tgz -o ./client.py

# Generate sync client
gql-pygen client -s ./schema.tgz -o ./client.py --sync

# Generate with custom class name
gql-pygen client -s ./schema.tgz -o ./client.py --client-name CatoClient
```

## Generated Client Usage

### Async Context Manager

```python
async with MyAPIClient(url=API_URL, api_key=API_KEY) as client:
    result = await client.namespace.operation(...)
```

### Field Selection

Control which fields are requested:

```python
from generated.client import FieldSelection

# Request all fields (default)
result = await client.users.get_user(id="123", fields=FieldSelection.ALL)

# Request minimal fields (just IDs and __typename)
result = await client.users.get_user(id="123", fields=FieldSelection.MINIMAL)

# Request specific fields
result = await client.users.get_user(
    id="123",
    fields=FieldSelection.custom(["id", "name", "email"])
)
```

### Error Handling

```python
from generated.client import GraphQLError

try:
    result = await client.users.create_user(input=user_input)
except GraphQLError as e:
    print(f"GraphQL error: {e.message}")
    for error in e.errors:
        print(f"  - {error}")
```

## Extensibility

gql-pygen is designed to be extensible. You can customize authentication, templates, scalar handling, and code generation without modifying the package.

### Custom Authentication

The generated client supports pluggable authentication:

```python
from gql_pygen.core import BearerAuth, BasicAuth, HeaderAuth, ApiKeyAuth

# Bearer token (OAuth, JWT)
async with MyClient(url=URL, auth=BearerAuth("your-token")) as client:
    result = await client.users.get_user(id="123")

# Basic auth
async with MyClient(url=URL, auth=BasicAuth("user", "pass")) as client:
    ...

# Custom headers
async with MyClient(url=URL, auth=HeaderAuth({"X-Custom": "value"})) as client:
    ...

# API key (default, backward compatible)
async with MyClient(url=URL, auth=ApiKeyAuth("key", header_name="x-api-key")) as client:
    ...
```

You can also implement your own auth by following the `Auth` protocol:

```python
class MyCustomAuth:
    def get_headers(self) -> dict[str, str]:
        return {"Authorization": f"Custom {self.token}"}
```

### Custom Templates

Override built-in Jinja2 templates to customize generated code:

```bash
gql-pygen generate -s ./schema -o ./generated --templates ./my_templates
```

Templates in your directory take precedence. Available templates to override:
- `models.py.j2` — Pydantic model generation
- `enums.py.j2` — Enum generation
- `scalars.py.j2` — Scalar type definitions

### Custom Scalar Handlers

Define how GraphQL custom scalars map to Python types:

```python
from gql_pygen.core import ScalarHandler, ScalarRegistry

class MoneyHandler:
    python_type = "Decimal"
    import_statement = "from decimal import Decimal"

    def serialize(self, value):
        return str(value)

    def deserialize(self, value):
        from decimal import Decimal
        return Decimal(value)

# Register custom scalars
registry = ScalarRegistry()
registry.register("Money", MoneyHandler())
```

Built-in handlers: `DateTimeHandler`, `DateHandler`, `UUIDHandler`, `JSONHandler`

### Generation Hooks

Transform the IR before generation or modify generated code after:

```python
from gql_pygen.core import HookRunner, FilterTypesHook, AddHeaderHook

runner = HookRunner()

# Pre-generation: filter out internal types
runner.add_pre_hook(FilterTypesHook(exclude_prefix="_"))

# Post-generation: add license header
runner.add_post_hook(AddHeaderHook("# Copyright 2024 My Company"))
```

Custom hooks follow the `PreGenerateHook` and `PostGenerateHook` protocols:

```python
class MyPreHook:
    def pre_generate(self, ir):
        # Modify IR
        return ir

class MyPostHook:
    def post_generate(self, filename: str, content: str) -> str:
        # Transform generated code
        return content
```

## How It Works

1. **Parse** — Reads GraphQL schema files using `graphql-core`
2. **Transform** — Converts to an intermediate representation (IR)
3. **Generate** — Renders Pydantic models and client code via Jinja2 templates

The generated client:
- Uses `httpx` for async HTTP requests
- Validates responses with Pydantic's `model_validate()`
- Handles lists, optionals, and nested types correctly

## Development

```bash
# Clone the repository
git clone https://github.com/your-org/gql-pygen.git
cd gql-pygen

# Install with dev dependencies
uv sync

# Run tests
uv run pytest tests/ -v

# Run a specific test file
uv run pytest tests/test_client_generator.py -v
```

## License

MIT
