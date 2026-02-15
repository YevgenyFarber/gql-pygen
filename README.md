# gql-pygen

**GraphQL to Python Code Generator** — Generate typed Pydantic models and async clients from GraphQL schemas.

## Features

- 🎯 **Typed Pydantic Models** — All GraphQL types, inputs, and enums become Pydantic models with full IDE autocomplete
- 🔗 **Nested Async Client** — Access operations via intuitive paths like `client.policy.firewall.add_rule(...)`
- ✅ **Response Parsing** — Responses are automatically validated and converted to typed models
- 🎛️ **Field Selection** — Request ALL fields, MINIMAL fields, or custom field sets
- 📦 **Archive Support** — Works with `.graphqls` files, directories, `.zip`, `.tar.gz`, and `.tgz` archives

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
  -s, --schema PATH   Path to schema file, directory, or archive [required]
  -o, --output PATH   Output directory for generated code [required]
  -v, --verbose       Enable verbose output
```

**Examples:**

```bash
# From a directory of .graphqls files
gql-pygen generate -s ./schema -o ./generated

# From an archive
gql-pygen generate -s ./schema-bundle.tgz -o ./generated
```

### `gql-pygen client`

Generate a typed async client with all operations.

```bash
gql-pygen client [OPTIONS]

Options:
  -s, --schema PATH        Path to schema file, directory, or archive [required]
  -o, --output PATH        Output file for generated client [required]
  -n, --client-name TEXT   Client class name (default: GraphQLClient)
  -v, --verbose            Enable verbose output
```

**Examples:**

```bash
# Generate with default class name (GraphQLClient)
gql-pygen client -s ./schema.tgz -o ./client.py

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
