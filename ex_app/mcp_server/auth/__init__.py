# SPDX-FileCopyrightText: 2025 Nextcloud GmbH and Nextcloud contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Authentication providers and middleware."""

from .provider import NextcloudOAuthProvider
from .middleware import DualAuthMiddleware, AccessControlMiddleware
from .app_password import AppPasswordAuth

__all__ = [
    "NextcloudOAuthProvider",
    "DualAuthMiddleware",
    "AccessControlMiddleware",
    "AppPasswordAuth",
]
