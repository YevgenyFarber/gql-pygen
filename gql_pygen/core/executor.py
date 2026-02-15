"""GraphQL executor for executing queries against a GraphQL endpoint.

Handles HTTP communication, error handling, and response parsing.
"""

from typing import Any

import httpx
from pydantic import BaseModel

from .auth import ApiKeyAuth, Auth
from .ir import IROperation, IRSchema
from .query_builder import FieldSelection, QueryBuilder


class GraphQLError(Exception):
    """Exception raised for GraphQL errors."""

    def __init__(self, message: str, errors: list[dict[str, Any]]):
        self.message = message
        self.errors = errors
        super().__init__(message)


class GraphQLExecutor:
    """Executes GraphQL operations against an endpoint.

    Supports pluggable authentication via the Auth protocol.

    Examples:
        # Using built-in auth
        executor = GraphQLExecutor(url, auth=BearerAuth(token))
        executor = GraphQLExecutor(url, auth=ApiKeyAuth(key))

        # Legacy api_key parameter (backward compatible)
        executor = GraphQLExecutor(url, api_key="my-key")

        # Custom auth
        executor = GraphQLExecutor(url, auth=MyCustomAuth())
    """

    def __init__(
        self,
        url: str,
        auth: Auth | None = None,
        *,
        api_key: str | None = None,  # Deprecated: use auth=ApiKeyAuth(key)
        schema: IRSchema | None = None,
        timeout: float = 30.0,
    ):
        """Initialize the executor.

        Args:
            url: GraphQL endpoint URL
            auth: Authentication handler (implements Auth protocol)
            api_key: DEPRECATED - API key for authentication. Use auth=ApiKeyAuth(key) instead.
            schema: Optional schema for query building (can be set later)
            timeout: Request timeout in seconds
        """
        self.url = url
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None
        self._query_builder: QueryBuilder | None = None

        # Handle auth - support both new auth parameter and legacy api_key
        if auth is not None:
            self._auth = auth
        elif api_key is not None:
            # Backward compatibility: convert api_key to ApiKeyAuth
            self._auth = ApiKeyAuth(api_key)
        else:
            raise ValueError("Either 'auth' or 'api_key' must be provided")

        # Operation lookup by path
        self._operations: dict[tuple, IROperation] = {}

        if schema:
            self._init_schema(schema)

    def _init_schema(self, schema: IRSchema):
        """Initialize query builder and operation lookup from schema."""
        self.schema = schema
        self._query_builder = QueryBuilder(schema)

        # Build operation lookup
        for op in schema.queries + schema.mutations:
            self._operations[tuple(op.path)] = op

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._client is None:
            # Build headers from auth handler
            headers = {"Content-Type": "application/json"}
            headers.update(self._auth.get_headers())

            self._client = httpx.AsyncClient(
                timeout=self.timeout,
                headers=headers,
            )
        return self._client

    async def close(self):
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def execute(
        self,
        query: str,
        variables: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute a raw GraphQL query.

        Args:
            query: GraphQL query string
            variables: Query variables

        Returns:
            The 'data' portion of the response

        Raises:
            GraphQLError: If the response contains errors
        """
        client = await self._get_client()

        payload = {"query": query}
        if variables:
            payload["variables"] = self._serialize_variables(variables)

        response = await client.post(self.url, json=payload)
        response.raise_for_status()

        result = response.json()

        if "errors" in result:
            error_messages = "; ".join(e.get("message", str(e)) for e in result["errors"])
            raise GraphQLError(f"GraphQL errors: {error_messages}", result["errors"])

        return result.get("data", {})

    async def execute_operation(
        self,
        operation_path: list[str],
        variables: dict[str, Any],
        fields: FieldSelection = FieldSelection.ALL,
    ) -> Any:
        """Execute an operation by its path.

        Args:
            operation_path: Path like ['policy', 'internetFirewall', 'addRule']
            variables: Operation variables
            fields: Field selection mode

        Returns:
            The operation result (extracted from nested response)
        """
        if not self._query_builder:
            raise RuntimeError("Schema not initialized. Call _init_schema first.")

        # Look up the operation
        op_key = tuple(operation_path)
        operation = self._operations.get(op_key)
        if not operation:
            raise ValueError(f"Unknown operation: {'.'.join(operation_path)}")

        # Build the query
        query = self._query_builder.build(operation, fields)

        # Execute
        data = await self.execute(query, variables)

        # Extract the nested result
        return self._extract_path(data, operation_path)

    def _extract_path(self, data: dict[str, Any], path: list[str]) -> Any:
        """Extract nested data at the given path."""
        result = data
        for segment in path:
            if result is None:
                return None
            if isinstance(result, dict):
                result = result.get(segment)
            else:
                return None
        return result

    def _serialize_variables(self, variables: dict[str, Any]) -> dict[str, Any]:
        """Serialize variables for the GraphQL request.

        Handles Pydantic models by converting them to dicts.
        """
        result = {}
        for key, value in variables.items():
            if value is None:
                continue  # Skip None values
            if isinstance(value, BaseModel):
                # Convert Pydantic model to dict, using aliases and excluding None
                result[key] = value.model_dump(by_alias=True, exclude_none=True)
            elif isinstance(value, list):
                # Handle lists of models
                result[key] = [
                    v.model_dump(by_alias=True, exclude_none=True) if isinstance(v, BaseModel) else v
                    for v in value
                ]
            else:
                result[key] = value
        return result

