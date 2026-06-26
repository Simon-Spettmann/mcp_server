# SPDX-FileCopyrightText: 2025 Nextcloud GmbH and Nextcloud contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
"""FastMCP Server for Nextcloud with OAuth 2.1 and App Password authentication"""

import asyncio
import json
import os
from contextlib import asynccontextmanager
from typing import Optional, List, Dict, Any

from fastapi import FastAPI
from fastmcp import FastMCP
from nc_py_api import AsyncNextcloudApp, NextcloudApp
from nc_py_api.ex_app import (
    AppAPIAuthMiddleware,
    LogLvl,
    run_app,
    set_handlers,
    SettingsForm,
    SettingsField,
    SettingsFieldType
)

from .auth.provider import NextcloudOAuthProvider
from .auth.app_password import AppPasswordAuth
from .auth.middleware import DualAuthMiddleware, AccessControlMiddleware, UserContextMiddleware
from .tools import file_tools
from .models.auth import UserInfo


class MCPServer:
    """
    Main MCP Server class that manages the FastMCP server with OAuth 2.1 and App Password support.
    
    This server provides:
    - OAuth 2.1 authentication with PKCE support
    - Nextcloud App Password authentication
    - File access tools (CRUD, list, search)
    - Per-user access control
    """
    
    def __init__(self, name: str = "nextcloud-mcp-server", 
                 enabled_auth_methods: List[str] = None):
        """
        Initialize the MCP Server.
        
        Args:
            name: Name of the MCP server
            enabled_auth_methods: List of enabled authentication methods
        """
        self.name = name
        self.enabled_auth_methods = enabled_auth_methods or ["oauth", "app_password", "legacy"]
        self.mcp: Optional[FastMCP] = None
        self.oauth_provider: Optional[NextcloudOAuthProvider] = None
        self.app_password_auth: Optional[AppPasswordAuth] = None
        self.nc_app: Optional[AsyncNextcloudApp] = None
    
    async def initialize(self, nc_app: AsyncNextcloudApp = None) -> FastMCP:
        """
        Initialize the MCP server with Nextcloud app instance.
        
        Args:
            nc_app: Nextcloud app instance (if None, creates a new one)
            
        Returns:
            FastMCP server instance
        """
        # Create or use provided Nextcloud app
        self.nc_app = nc_app or AsyncNextcloudApp()
        
        # Initialize authentication providers
        self.oauth_provider = NextcloudOAuthProvider(self.nc_app)
        self.app_password_auth = AppPasswordAuth(self.nc_app)
        
        # Create FastMCP server
        self.mcp = FastMCP(name=self.name)
        
        # Add authentication middleware
        dual_auth = DualAuthMiddleware(
            oauth_provider=self.oauth_provider,
            app_password_auth=self.app_password_auth,
            nc_app=self.nc_app,
            enabled_methods=self.enabled_auth_methods
        )
        
        access_control = AccessControlMiddleware()
        user_context = UserContextMiddleware(self.nc_app)
        
        self.mcp.add_middleware(dual_auth)
        self.mcp.add_middleware(user_context)
        self.mcp.add_middleware(access_control)
        
        # Add file tools
        for tool in file_tools:
            self.mcp.tool()(tool)
        
        return self.mcp
    
    def get_fastapi_app(self) -> FastAPI:
        """Get the FastAPI app with MCP server mounted"""
        if self.mcp is None:
            raise RuntimeError("Server not initialized. Call initialize() first.")
        
        # Create FastAPI app
        app = FastAPI()
        
        # Mount MCP server
        http_mcp_app = self.mcp.http_app("/mcp", transport="http", stateless_http=True)
        app.mount("/mcp", http_mcp_app)
        
        return app
    
    async def create_oauth_client(self, user_id: str, client_name: str = "",
                                  redirect_uris: List[str] = None) -> Dict[str, str]:
        """
        Create an OAuth client for a user.
        
        Args:
            user_id: Nextcloud user ID
            client_name: Human-readable client name
            redirect_uris: List of allowed redirect URIs
            
        Returns:
            Dictionary with client credentials
        """
        if self.oauth_provider is None:
            raise RuntimeError("Server not initialized. Call initialize() first.")
        
        client = await self.oauth_provider.create_client_for_user(
            user_id=user_id,
            client_name=client_name,
            redirect_uris=redirect_uris or ["http://localhost:8080/callback"]
        )
        
        return {
            "client_id": client.client_id,
            "client_secret": client.client_secret,
            "client_name": client.client_name,
            "redirect_uris": client.redirect_uris,
            "scopes": client.scopes
        }
    
    async def get_oauth_authorization_url(self, client_id: str, 
                                         redirect_uri: str = "http://localhost:8080/callback",
                                         scopes: List[str] = None,
                                         state: str = None) -> str:
        """
        Get OAuth authorization URL for a client.
        
        Args:
            client_id: OAuth client ID
            redirect_uri: Redirect URI for the OAuth flow
            scopes: List of requested scopes
            state: State parameter for CSRF protection
            
        Returns:
            Authorization URL
        """
        if self.oauth_provider is None:
            raise RuntimeError("Server not initialized. Call initialize() first.")
        
        # Get client info
        client = await self.oauth_provider.get_client(client_id)
        if client is None:
            raise ValueError(f"Client {client_id} not found")
        
        # Generate PKCE code verifier and challenge
        import secrets
        import base64
        import hashlib
        
        code_verifier = secrets.token_urlsafe(64)
        code_challenge = base64.urlsafe_b64encode(
            hashlib.sha256(code_verifier.encode()).digest()
        ).decode().rstrip('=')
        
        # Build authorization URL
        params = {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scope": " ".join(scopes or ["read", "write"]),
            "state": state or secrets.token_urlsafe(32),
            "code_challenge": code_challenge,
            "code_challenge_method": "S256"
        }
        
        # For this POC, we'll use a simplified authorization flow
        # In production, this would redirect to a proper authorization endpoint
        return f"/mcp/oauth/authorize?{self._urlencode(params)}"
    
    def _urlencode(self, params: Dict[str, Any]) -> str:
        """URL encode parameters"""
        from urllib.parse import urlencode
        return urlencode(params)


def create_mcp_server(nc_app: AsyncNextcloudApp = None, 
                      enabled_auth_methods: List[str] = None) -> FastMCP:
    """
    Create and initialize an MCP server.
    
    Args:
        nc_app: Nextcloud app instance
        enabled_auth_methods: List of enabled authentication methods
        
    Returns:
        FastMCP server instance
    """
    server = MCPServer(
        name="nextcloud-mcp-server",
        enabled_auth_methods=enabled_auth_methods or ["oauth", "app_password", "legacy"]
    )
    
    # Initialize the server (synchronous wrapper for async method)
    import asyncio
    loop = asyncio.get_event_loop()
    if loop.is_running():
        # If we're already in an async context, create a new task
        task = asyncio.create_task(server.initialize(nc_app))
        return task.result()
    else:
        # If we're not in an async context, run synchronously
        return asyncio.run(server.initialize(nc_app))


# Settings for the exApp
SETTINGS = SettingsForm(
    id="settings_mcp_server",
    section_type="admin",
    section_id="ai",
    title="MCP Server",
    description="Configuration for the dedicated MCP Server with OAuth 2.1 and App Password support",
    fields=[
        SettingsField(
            id="enabled_auth_methods",
            title="Enabled Authentication Methods",
            type=SettingsFieldType.MULTI_CHECKBOX,
            default={"oauth": True, "app_password": True, "legacy": False},
            options={
                "oauth": "OAuth 2.1 (Recommended)",
                "app_password": "Nextcloud App Passwords",
                "legacy": "Legacy Token Authentication"
            },
            description="Select which authentication methods to enable for the MCP server"
        ),
        SettingsField(
            id="default_scopes",
            title="Default OAuth Scopes",
            type=SettingsFieldType.TEXT,
            default="read write",
            placeholder="read write delete",
            description="Default scopes for new OAuth clients (space-separated)"
        ),
        SettingsField(
            id="token_expiration",
            title="Access Token Expiration (seconds)",
            type=SettingsFieldType.NUMBER,
            default=3600,
            description="Expiration time for access tokens in seconds"
        ),
        SettingsField(
            id="enable_pkce",
            title="Enable PKCE for OAuth",
            type=SettingsFieldType.CHECKBOX,
            default=True,
            description="Whether to require PKCE for OAuth authorization code flow"
        )
    ]
)


# FastAPI app for the exApp
APP = FastAPI()
APP.add_middleware(AppAPIAuthMiddleware)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Initialize MCP server
    nc = AsyncNextcloudApp()
    
    # Get enabled auth methods from config
    enabled_methods_json = await nc.appconfig_ex.get_value('enabled_auth_methods', '{}')
    try:
        enabled_methods_config = json.loads(enabled_methods_json)
        enabled_methods = [
            method for method, enabled in enabled_methods_config.items() 
            if enabled
        ]
    except json.JSONDecodeError:
        enabled_methods = ["oauth", "app_password", "legacy"]
    
    # Create and initialize MCP server
    server = MCPServer(
        name="nextcloud-mcp-server",
        enabled_auth_methods=enabled_methods
    )
    
    mcp = await server.initialize(nc)
    
    # Mount MCP server
    http_mcp_app = mcp.http_app("/mcp", transport="http", stateless_http=True)
    app.mount("/mcp", http_mcp_app)
    
    # Set up handlers
    set_handlers(
        app,
        enabled_handler,
        trigger_handler=None,
        default_heartbeat=True,
        default_init=True
    )
    
    # Register settings
    await nc.ui.settings.register_form(SETTINGS)
    
    yield


APP.lifespan = lifespan


async def enabled_handler(enabled: bool, nc: AsyncNextcloudApp) -> str:
    """Handle app enable/disable events"""
    if enabled:
        print(f"MCP Server app enabled: {nc.app_cfg.app_name}")
        
        # Initialize OAuth clients if needed
        server = MCPServer()
        await server.initialize(nc)
        
        # Create default OAuth client for the app
        try:
            await server.create_oauth_client(
                user_id="admin",
                client_name="MCP Server Default Client",
                redirect_uris=["http://localhost:8080/callback"]
            )
        except Exception as e:
            print(f"Error creating default OAuth client: {e}")
    else:
        print(f"MCP Server app disabled: {nc.app_cfg.app_name}")
    
    return ""


if __name__ == "__main__":
    # Run the app directly for testing
    run_app("server:APP", log_level="trace")
