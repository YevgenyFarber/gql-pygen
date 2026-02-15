"""Authentication handlers for GraphQL clients.

Provides pluggable authentication via the Auth protocol.
Users can implement custom auth or use built-in handlers.
"""

import base64
from typing import Dict, Protocol, runtime_checkable


@runtime_checkable
class Auth(Protocol):
    """Protocol for authentication handlers.
    
    Implement this protocol to create custom authentication.
    
    Example:
        class MyCustomAuth:
            def __init__(self, token: str, org_id: str):
                self.token = token
                self.org_id = org_id
            
            def get_headers(self) -> dict[str, str]:
                return {
                    "Authorization": f"Bearer {self.token}",
                    "X-Org-ID": self.org_id,
                }
    """
    
    def get_headers(self) -> Dict[str, str]:
        """Return headers to include in requests."""
        ...


class ApiKeyAuth:
    """API key authentication via a custom header.
    
    Args:
        api_key: The API key value
        header_name: Header name (default: "x-api-key")
    
    Example:
        auth = ApiKeyAuth("my-secret-key")
        auth = ApiKeyAuth("my-key", header_name="Authorization")
    """
    
    def __init__(self, api_key: str, header_name: str = "x-api-key"):
        self.api_key = api_key
        self.header_name = header_name
    
    def get_headers(self) -> Dict[str, str]:
        return {self.header_name: self.api_key}


class BearerAuth:
    """Bearer token authentication.
    
    Args:
        token: The bearer token
    
    Example:
        auth = BearerAuth("eyJhbGciOiJIUzI1NiIs...")
    """
    
    def __init__(self, token: str):
        self.token = token
    
    def get_headers(self) -> Dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"}


class BasicAuth:
    """HTTP Basic authentication.
    
    Args:
        username: Username
        password: Password
    
    Example:
        auth = BasicAuth("user", "pass")
    """
    
    def __init__(self, username: str, password: str):
        self.username = username
        self.password = password
    
    def get_headers(self) -> Dict[str, str]:
        credentials = f"{self.username}:{self.password}"
        encoded = base64.b64encode(credentials.encode()).decode()
        return {"Authorization": f"Basic {encoded}"}


class HeaderAuth:
    """Custom headers authentication.
    
    Args:
        headers: Dictionary of headers to include
    
    Example:
        auth = HeaderAuth({
            "X-API-Key": "key123",
            "X-Tenant-ID": "tenant456",
        })
    """
    
    def __init__(self, headers: Dict[str, str]):
        self._headers = headers
    
    def get_headers(self) -> Dict[str, str]:
        return self._headers.copy()


class NoAuth:
    """No authentication (for public APIs or testing)."""
    
    def get_headers(self) -> Dict[str, str]:
        return {}

