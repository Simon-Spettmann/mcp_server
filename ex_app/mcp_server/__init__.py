# SPDX-FileCopyrightText: 2025 Nextcloud GmbH and Nextcloud contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Dedicated MCP Server exApp for Nextcloud.

This module provides a standalone MCP server with:
- OAuth 2.1 authentication with PKCE support
- Nextcloud App Password authentication
- File access operations (CRUD, list, search)
- Per-user access control
"""

from .server import create_mcp_server
from .auth.provider import NextcloudOAuthProvider
from .auth.middleware import DualAuthMiddleware, AccessControlMiddleware
from .tools import file_tools

__all__ = [
    "create_mcp_server",
    "NextcloudOAuthProvider",
    "DualAuthMiddleware",
    "AccessControlMiddleware",
    "file_tools",
]
