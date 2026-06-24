# SPDX-FileCopyrightText: 2025 Nextcloud GmbH and Nextcloud contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Nextcloud MCP Server

A clean MCP server that exposes Nextcloud capabilities as tools.
This is a standalone tool gateway with no LLM or agent dependencies.
"""
import asyncio
import json
import time
from functools import wraps
from typing import Any, Callable

import requests
from fastmcp import FastMCP
from fastmcp.server.dependencies import get_context, get_http_headers
from fastmcp.server.middleware import CallNext, Middleware, MiddlewareContext
from nc_py_api import AsyncNextcloudApp


class UserAuthMiddleware(Middleware):
    """Middleware to authenticate requests and set up Nextcloud context."""

    async def on_message(self, context: MiddlewareContext, call_next: CallNext) -> Any:
        authorization_header = get_http_headers().get("authorization")
        if authorization_header is None:
            raise Exception("Authorization header is missing")

        # Get user info from Nextcloud
        nc = AsyncNextcloudApp()
        user = self._get_user(authorization_header, nc)
        await nc.set_user(user)

        # Store Nextcloud instance in context state
        context.fastmcp_context.set_state("nextcloud", nc)

        return await call_next(context)

    def _get_user(self, authorization_header: str, nc: AsyncNextcloudApp) -> str:
        """Get the current user from Nextcloud using the authorization header."""
        response = requests.get(
            f"{nc.app_cfg.endpoint}/ocs/v2.php/cloud/user",
            headers={
                "Accept": "application/json",
                "Ocs-Apirequest": "1",
                "Authorization": authorization_header,
            },
        )
        if response.status_code != 200:
            raise Exception("Failed to get user info")
        return response.json()["ocs"]["data"]["id"]


def create_mcp_server() -> FastMCP:
    """Create and configure the MCP server."""
    mcp = FastMCP(name="nextcloud")

    # Add authentication middleware
    mcp.add_middleware(UserAuthMiddleware())

    return mcp


def get_nextcloud_from_context() -> AsyncNextcloudApp:
    """Get the Nextcloud instance from the FastMCP context."""
    ctx = get_context()
    nc = ctx.get_state("nextcloud")
    if nc is None:
        raise Exception("Nextcloud instance not found in context")
    return nc


# Create the MCP server instance
mcp = create_mcp_server()

# Register resources
from ex_app.lib.resources import register_resources

register_resources(mcp)

# HTTP app for MCP
http_mcp_app = mcp.http_app("/", transport="http", stateless_http=True)

# Also support stdio transport for CLI clients
stdio_mcp_app = mcp.stdio_app()
