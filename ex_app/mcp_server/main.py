# SPDX-FileCopyrightText: 2025 Nextcloud GmbH and Nextcloud contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Main entry point for the dedicated MCP Server exApp.

This module provides a standalone MCP server with:
- OAuth 2.1 authentication with PKCE support
- Nextcloud App Password authentication
- File access operations (CRUD, list, search)
- Per-user access control

Usage:
    python -m ex_app.mcp_server.main
"""

import asyncio
import json
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from nc_py_api import AsyncNextcloudApp
from nc_py_api.ex_app import (
    AppAPIAuthMiddleware,
    run_app,
    set_handlers,
    SettingsForm,
    SettingsField,
    SettingsFieldType
)

from .server import MCPServer, SETTINGS, enabled_handler
from .auth.provider import NextcloudOAuthProvider
from .auth.app_password import AppPasswordAuth
from .auth.middleware import DualAuthMiddleware, AccessControlMiddleware, UserContextMiddleware
from .tools import file_tools


# Create the main FastAPI app
APP = FastAPI()
APP.add_middleware(AppAPIAuthMiddleware)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Initialize Nextcloud app
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


if __name__ == "__main__":
    # Run the app
    run_app("ex_app.mcp_server.main:APP", log_level="trace")
