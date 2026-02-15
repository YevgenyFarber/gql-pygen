"""Tests for authentication handlers."""

import base64

from gql_pygen.core.auth import (
    ApiKeyAuth,
    Auth,
    BasicAuth,
    BearerAuth,
    HeaderAuth,
    NoAuth,
)


class TestApiKeyAuth:
    """Tests for ApiKeyAuth."""

    def test_default_header_name(self):
        """Test default x-api-key header."""
        auth = ApiKeyAuth("my-secret-key")
        headers = auth.get_headers()
        assert headers == {"x-api-key": "my-secret-key"}

    def test_custom_header_name(self):
        """Test custom header name."""
        auth = ApiKeyAuth("my-key", header_name="Authorization")
        headers = auth.get_headers()
        assert headers == {"Authorization": "my-key"}

    def test_x_auth_token_header(self):
        """Test x-auth-token header."""
        auth = ApiKeyAuth("token123", header_name="x-auth-token")
        headers = auth.get_headers()
        assert headers == {"x-auth-token": "token123"}


class TestBearerAuth:
    """Tests for BearerAuth."""

    def test_bearer_token(self):
        """Test bearer token header."""
        auth = BearerAuth("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9")
        headers = auth.get_headers()
        assert headers == {"Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"}


class TestBasicAuth:
    """Tests for BasicAuth."""

    def test_basic_auth(self):
        """Test basic auth encoding."""
        auth = BasicAuth("user", "pass")
        headers = auth.get_headers()

        # Verify the encoding
        expected = base64.b64encode(b"user:pass").decode()
        assert headers == {"Authorization": f"Basic {expected}"}

    def test_basic_auth_special_chars(self):
        """Test basic auth with special characters."""
        auth = BasicAuth("user@domain.com", "p@ss:word!")
        headers = auth.get_headers()

        expected = base64.b64encode(b"user@domain.com:p@ss:word!").decode()
        assert headers == {"Authorization": f"Basic {expected}"}


class TestHeaderAuth:
    """Tests for HeaderAuth."""

    def test_single_header(self):
        """Test single custom header."""
        auth = HeaderAuth({"X-Custom-Header": "value"})
        headers = auth.get_headers()
        assert headers == {"X-Custom-Header": "value"}

    def test_multiple_headers(self):
        """Test multiple custom headers."""
        auth = HeaderAuth({
            "X-API-Key": "key123",
            "X-Tenant-ID": "tenant456",
            "X-Request-ID": "req789",
        })
        headers = auth.get_headers()
        assert headers == {
            "X-API-Key": "key123",
            "X-Tenant-ID": "tenant456",
            "X-Request-ID": "req789",
        }

    def test_returns_copy(self):
        """Test that get_headers returns a copy."""
        original = {"X-Key": "value"}
        auth = HeaderAuth(original)
        headers = auth.get_headers()
        headers["X-New"] = "new"

        # Original should not be modified
        assert "X-New" not in auth.get_headers()


class TestNoAuth:
    """Tests for NoAuth."""

    def test_no_auth(self):
        """Test no auth returns empty headers."""
        auth = NoAuth()
        headers = auth.get_headers()
        assert headers == {}


class TestAuthProtocol:
    """Tests for Auth protocol compliance."""

    def test_api_key_auth_is_auth(self):
        """Test ApiKeyAuth implements Auth protocol."""
        auth = ApiKeyAuth("key")
        assert isinstance(auth, Auth)

    def test_bearer_auth_is_auth(self):
        """Test BearerAuth implements Auth protocol."""
        auth = BearerAuth("token")
        assert isinstance(auth, Auth)

    def test_basic_auth_is_auth(self):
        """Test BasicAuth implements Auth protocol."""
        auth = BasicAuth("user", "pass")
        assert isinstance(auth, Auth)

    def test_header_auth_is_auth(self):
        """Test HeaderAuth implements Auth protocol."""
        auth = HeaderAuth({})
        assert isinstance(auth, Auth)

    def test_no_auth_is_auth(self):
        """Test NoAuth implements Auth protocol."""
        auth = NoAuth()
        assert isinstance(auth, Auth)

    def test_custom_auth_class(self):
        """Test custom auth class implements protocol."""
        class CustomAuth:
            def get_headers(self):
                return {"X-Custom": "value"}

        auth = CustomAuth()
        assert isinstance(auth, Auth)
        assert auth.get_headers() == {"X-Custom": "value"}

