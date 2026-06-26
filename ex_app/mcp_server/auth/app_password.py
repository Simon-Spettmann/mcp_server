# SPDX-FileCopyrightText: 2025 Nextcloud GmbH and Nextcloud contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Nextcloud App Password authentication for MCP Server"""

import base64
import json
from typing import Optional, Dict, Any

from nc_py_api import AsyncNextcloudApp
from niquests import RequestException

from ..models.auth import UserInfo


class AppPasswordAuth:
    """
    Authentication handler for Nextcloud App Passwords.
    
    App Passwords are used for programmatic access to Nextcloud and can be
    used as an alternative to OAuth for simpler integrations.
    """
    
    def __init__(self, nc_app: AsyncNextcloudApp):
        self.nc_app = nc_app
        self._app_password_cache: Dict[str, Dict[str, Any]] = {}
    
    async def authenticate(self, username: str, password: str) -> Optional[UserInfo]:
        """
        Authenticate using Nextcloud App Password.
        
        Args:
            username: Nextcloud username
            password: App Password (not the user's main password)
            
        Returns:
            UserInfo if authentication succeeds, None otherwise
        """
        try:
            nc = self.nc_app
            
            # Try to authenticate with the provided credentials
            # We'll use the OCS API to verify the app password
            try:
                response = await nc._session._create_adapter().request(
                    'GET',
                    f"{nc.app_cfg.endpoint}/ocs/v2.php/cloud/user",
                    auth=(username, password),
                    headers={
                        'Accept': 'application/json',
                        'OCS-APIRequest': 'true'
                    }
                )
                
                # If we get here, authentication succeeded
                user_data = response.json().get('ocs', {}).get('data', {})
                
                # Cache the app password for this session
                self._app_password_cache[username] = {
                    'username': username,
                    'password': password,  # In production, store a hash or token
                    'user_data': user_data
                }
                
                return UserInfo.from_app_password(username, user_data)
                
            except RequestException as e:
                # Check if it's an authentication error
                if e.response and e.response.status_code in [401, 403]:
                    return None
                raise
                
        except Exception as e:
            print(f"App Password authentication error: {e}")
            return None
    
    async def authenticate_with_basic_auth(self, basic_auth_string: str) -> Optional[UserInfo]:
        """
        Authenticate using HTTP Basic Authentication string.
        
        Args:
            basic_auth_string: The string after "Basic " in the Authorization header
            
        Returns:
            UserInfo if authentication succeeds, None otherwise
        """
        try:
            # Decode the Basic auth string
            decoded = base64.b64decode(basic_auth_string).decode('utf-8')
            if ':' not in decoded:
                return None
            
            username, password = decoded.split(':', 1)
            return await self.authenticate(username, password)
            
        except Exception as e:
            print(f"Basic auth decoding error: {e}")
            return None
    
    async def get_user_info(self, username: str) -> Optional[Dict[str, Any]]:
        """Get user information for a cached app password authentication"""
        cached = self._app_password_cache.get(username)
        if cached:
            return cached.get('user_data')
        return None
    
    async def validate_app_password(self, username: str, password: str) -> bool:
        """
        Validate if the given app password is valid for the user.
        
        This is a simpler check that doesn't return full user info.
        """
        user_info = await self.authenticate(username, password)
        return user_info is not None
    
    async def clear_cache(self, username: str = None) -> None:
        """Clear the app password cache"""
        if username:
            self._app_password_cache.pop(username, None)
        else:
            self._app_password_cache.clear()
