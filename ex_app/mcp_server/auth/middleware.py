# SPDX-FileCopyrightText: 2025 Nextcloud GmbH and Nextcloud contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Authentication middleware for MCP Server."""

from typing import Optional, List

from fastmcp.server.middleware import Middleware, MiddlewareContext
from fastmcp.server.dependencies import get_http_headers
from nc_py_api import AsyncNextcloudApp

from .provider import NextcloudOAuthProvider
from .app_password import AppPasswordAuth
from ..models.auth import UserInfo


class DualAuthMiddleware(Middleware):
    """Middleware that handles both OAuth Bearer tokens and Nextcloud App Passwords.

    This middleware tries authentication methods in the following order:
    1. OAuth Bearer token (Authorization: Bearer <token>)
    2. HTTP Basic Auth with App Password (Authorization: Basic <base64>)
    3. Legacy Authorization header (current implementation)

    The first successful authentication method is used, and the user context
    is stored in the FastMCP context for use by other middleware and tools.
    """

    def __init__(
        self,
        oauth_provider: NextcloudOAuthProvider,
        app_password_auth: AppPasswordAuth,
        nc_app: AsyncNextcloudApp,
        enabled_methods: Optional[List[str]] = None,
    ):
        """Initialize the dual authentication middleware.

        Args:
            oauth_provider: OAuth 2.1 provider instance
            app_password_auth: App Password authentication handler
            nc_app: Nextcloud app instance
            enabled_methods: List of enabled auth methods (oauth, app_password, legacy)
        """
        self.oauth_provider = oauth_provider
        self.app_password_auth = app_password_auth
        self.nc_app = nc_app
        self.enabled_methods = enabled_methods or ["oauth", "app_password", "legacy"]

    async def on_message(self, context: MiddlewareContext, call_next):
        """Handle authentication for incoming messages."""
        headers = get_http_headers(include={"authorization"})
        auth_header = headers.get("authorization", "")

        user_info = None
        auth_method = None

        # Try OAuth Bearer token first (if enabled)
        if "oauth" in self.enabled_methods and auth_header.startswith("Bearer "):
            token = auth_header[7:]  # Remove "Bearer " prefix
            user_info = await self._authenticate_oauth(token)
            if user_info:
                auth_method = "oauth"

        # Try Basic Auth with App Password (if enabled and not already authenticated)
        if (
            user_info is None
            and "app_password" in self.enabled_methods
            and auth_header.startswith("Basic ")
        ):
            basic_auth_string = auth_header[6:]  # Remove "Basic " prefix
            user_info = await self._authenticate_app_password(basic_auth_string)
            if user_info:
                auth_method = "app_password"

        # Try legacy Authorization header (if enabled and not already authenticated)
        if user_info is None and "legacy" in self.enabled_methods and auth_header:
            user_info = await self._authenticate_legacy(auth_header)
            if user_info:
                auth_method = "legacy"

        # If no authentication succeeded, raise an error
        if user_info is None:
            raise Exception(
                "Authentication required. Please provide a valid OAuth Bearer token, "
                "Basic Auth with App Password, or Authorization header."
            )

        # Store user context in FastMCP context
        context.fastmcp_context.set_state("user", user_info.model_dump())
        context.fastmcp_context.set_state("auth_method", auth_method)
        context.fastmcp_context.set_state("nextcloud", self.nc_app)

        # Set user on Nextcloud app instance
        if hasattr(self.nc_app, "_session"):
            await self.nc_app.set_user(user_info.user_id)

        return await call_next(context)

    async def _authenticate_oauth(self, token: str) -> Optional[UserInfo]:
        """Authenticate using OAuth Bearer token."""
        try:
            user_info = await self.oauth_provider.get_user_info(token)
            if user_info:
                return user_info
        except Exception as e:
            print(f"OAuth authentication error: {e}")
        return None

    async def _authenticate_app_password(self, basic_auth_string: str) -> Optional[UserInfo]:
        """Authenticate using HTTP Basic Auth with App Password."""
        try:
            return await self.app_password_auth.authenticate_with_basic_auth(basic_auth_string)
        except Exception as e:
            print(f"App Password authentication error: {e}")
        return None

    async def _authenticate_legacy(self, auth_header: str) -> Optional[UserInfo]:
        """Authenticate using legacy Authorization header (current implementation)."""
        try:
            # Import here to avoid circular imports
            from ex_app.lib.mcp_server import get_user

            nc = self.nc_app
            user = get_user(auth_header, nc)

            # Get user info from Nextcloud
            try:
                response = await nc.ocs("GET", "/ocs/v2.php/cloud/user")
                user_data = response.get("ocs", {}).get("data", {})
            except Exception:
                user_data = {"id": user, "username": user}

            return UserInfo(
                user_id=user,
                username=user_data.get("username", user),
                display_name=user_data.get("display_name"),
                email=user_data.get("email"),
                auth_method="legacy",
                scopes=["read", "write"],  # Default scopes for legacy auth
                client_id=None,
            )
        except Exception as e:
            print(f"Legacy authentication error: {e}")
        return None


class AccessControlMiddleware(Middleware):
    """Middleware that applies per-user access control based on authentication method and scopes.

    This middleware checks the user's permissions and scopes to determine if they
    have access to the requested resource or tool.
    """

    # Define access levels for different authentication methods
    AUTH_METHOD_ACCESS_LEVELS = {
        "oauth": {
            "read": True,
            "write": True,
            "delete": True,
            "admin": False,
            "search": True,
        },
        "app_password": {
            "read": True,
            "write": True,
            "delete": False,  # More restrictive for App Passwords
            "admin": False,
            "search": True,
        },
        "legacy": {
            "read": True,
            "write": False,  # Most restrictive for legacy auth
            "delete": False,
            "admin": False,
            "search": False,
        },
    }

    # Define scope-based permissions
    SCOPE_PERMISSIONS = {
        "read": ["list_files", "read_file", "get_file_info", "search_files"],
        "write": ["create_file", "update_file", "create_directory"],
        "delete": ["delete_file", "delete_directory"],
        "admin": ["manage_users", "configure_server"],
    }

    def __init__(self, allowed_scopes: Optional[List[str]] = None):
        """Initialize the access control middleware.

        Args:
            allowed_scopes: List of scopes that are allowed for this server
        """
        self.allowed_scopes = allowed_scopes or ["read", "write", "delete", "admin", "search"]

    async def on_message(self, context: MiddlewareContext, call_next):
        """Apply access control to incoming messages."""
        # Get user context from FastMCP context
        user_data = context.fastmcp_context.get_state("user")
        auth_method = context.fastmcp_context.get_state("auth_method")

        if not user_data or not auth_method:
            raise Exception("User not authenticated")

        # Convert user_data to UserInfo if it's a dict
        if isinstance(user_data, dict):
            user_info = UserInfo(**user_data)
        else:
            user_info = user_data

        # Check if the user has access to the requested tool/resource
        tool_name = self._get_tool_name(context)

        if not self._check_access(user_info, auth_method, tool_name):
            raise PermissionError(f"Access denied for {auth_method} user to {tool_name}")

        return await call_next(context)

    def _get_tool_name(self, context: MiddlewareContext) -> str:
        """Extract the tool name from the context."""
        # Try to get tool name from the request
        if hasattr(context, "request") and context.request:
            if hasattr(context.request, "method"):
                return context.request.method

        # Try to get from the message
        if hasattr(context, "message") and context.message:
            if hasattr(context.message, "name"):
                return context.message.name

        return "unknown"

    def _check_access(self, user_info: UserInfo, auth_method: str, tool_name: str) -> bool:
        """Check if the user has access to the requested tool."""
        # Get access levels for this auth method
        access_levels = self.AUTH_METHOD_ACCESS_LEVELS.get(auth_method, {})

        # Get user scopes
        user_scopes = set(user_info.scopes or [])

        # Check if tool is allowed by any of the user's scopes
        for scope, tools in self.SCOPE_PERMISSIONS.items():
            if scope in user_scopes and tool_name in tools:
                return True

        # Check if tool is allowed by auth method access levels
        for scope, tools in self.SCOPE_PERMISSIONS.items():
            if access_levels.get(scope, False) and tool_name in tools:
                return True

        # Default: allow read-only operations for authenticated users
        if tool_name in ["list_files", "read_file", "get_file_info", "search_files"]:
            return True

        return False

    def check_scope(self, user_info: UserInfo, required_scope: str) -> bool:
        """Check if user has a specific scope."""
        return required_scope in (user_info.scopes or [])

    def check_permission(self, user_info: UserInfo, auth_method: str, permission: str) -> bool:
        """Check if user has a specific permission based on auth method and scopes."""
        # Check scopes first
        if permission in (user_info.scopes or []):
            return True

        # Check auth method access levels
        access_levels = self.AUTH_METHOD_ACCESS_LEVELS.get(auth_method, {})
        return access_levels.get(permission, False)


class UserContextMiddleware(Middleware):
    """Middleware that ensures user context is properly set for all requests.

    This middleware works in conjunction with DualAuthMiddleware to ensure
    that the Nextcloud app instance has the correct user context set.
    """

    def __init__(self, nc_app: AsyncNextcloudApp):
        self.nc_app = nc_app

    async def on_message(self, context: MiddlewareContext, call_next):
        """Ensure user context is set."""
        user_data = context.fastmcp_context.get_state("user")

        if user_data:
            user_id = user_data.get("user_id") if isinstance(user_data, dict) else user_data.user_id
            if user_id and hasattr(self.nc_app, "_session"):
                try:
                    await self.nc_app.set_user(user_id)
                except Exception as e:
                    print(f"Error setting user context: {e}")

        return await call_next(context)
