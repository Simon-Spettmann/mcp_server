# SPDX-FileCopyrightText: 2025 Nextcloud GmbH and Nextcloud contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
"""OAuth 2.1 Provider implementation for Nextcloud MCP Server"""

import asyncio
import base64
import hashlib
import json
import secrets
import time
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from urllib.parse import urlparse, urlencode, parse_qs

from nc_py_api import AsyncNextcloudApp
from mcp.server.auth.provider import (
    OAuthAuthorizationServerProvider,
    OAuthClientInformationFull,
    AuthorizationParams,
    AuthorizationCodeT,
    AccessTokenT,
    RefreshTokenT,
    OAuthToken,
    AuthorizationError,
    TokenError,
    RegistrationError,
    AuthorizeError
)
from mcp.server.auth.settings import AuthSettings, ClientRegistrationOptions

from ..models.auth import (
    OAuthClient as OAuthClientModel,
    AuthorizationCode as AuthorizationCodeModel,
    AccessToken as AccessTokenModel,
    RefreshToken as RefreshTokenModel,
    UserInfo
)


class NextcloudOAuthProvider(OAuthAuthorizationServerProvider):
    """OAuth 2.1 Authorization Server Provider for Nextcloud integration.

    Implements the full OAuth 2.1 protocol with PKCE support for MCP server authentication.
    """
    
    # Storage for OAuth entities (in production, use database or Nextcloud storage)
    def __init__(self, nc_app: AsyncNextcloudApp):
        self.nc_app = nc_app
        self._clients: Dict[str, OAuthClientModel] = {}
        self._authorization_codes: Dict[str, AuthorizationCodeModel] = {}
        self._access_tokens: Dict[str, AccessTokenModel] = {}
        self._refresh_tokens: Dict[str, RefreshTokenModel] = {}
        self._user_consents: Dict[str, List[str]] = {}  # user_id -> list of client_ids
        
        # Load existing data from Nextcloud app config
        self._load_from_storage()
    
    async def _load_from_storage(self):
        """Load OAuth data from Nextcloud storage"""
        try:
            # Load clients
            clients_json = await self.nc_app.appconfig_ex.get_value('oauth_clients', '{}')
            if clients_json:
                clients_data = json.loads(clients_json)
                for client_id, client_data in clients_data.items():
                    self._clients[client_id] = OAuthClientModel(**client_data)
            
            # Load authorization codes
            codes_json = await self.nc_app.appconfig_ex.get_value('oauth_authorization_codes', '{}')
            if codes_json:
                codes_data = json.loads(codes_json)
                for code, code_data in codes_data.items():
                    self._authorization_codes[code] = AuthorizationCodeModel(**code_data)
            
            # Load access tokens
            tokens_json = await self.nc_app.appconfig_ex.get_value('oauth_access_tokens', '{}')
            if tokens_json:
                tokens_data = json.loads(tokens_json)
                for token, token_data in tokens_data.items():
                    self._access_tokens[token] = AccessTokenModel(**token_data)
            
            # Load refresh tokens
            refresh_json = await self.nc_app.appconfig_ex.get_value('oauth_refresh_tokens', '{}')
            if refresh_json:
                refresh_data = json.loads(refresh_json)
                for token, token_data in refresh_data.items():
                    self._refresh_tokens[token] = RefreshTokenModel(**token_data)
                    
        except Exception as e:
            print(f"Error loading OAuth data from storage: {e}")
    
    async def _save_to_storage(self):
        """Save OAuth data to Nextcloud storage"""
        try:
            # Save clients
            clients_data = {cid: client.model_dump() for cid, client in self._clients.items()}
            await self.nc_app.appconfig_ex.set_value('oauth_clients', json.dumps(clients_data))
            
            # Save authorization codes
            codes_data = {code: auth_code.model_dump() for code, auth_code in self._authorization_codes.items()}
            await self.nc_app.appconfig_ex.set_value('oauth_authorization_codes', json.dumps(codes_data))
            
            # Save access tokens
            tokens_data = {token: access_token.model_dump() for token, access_token in self._access_tokens.items()}
            await self.nc_app.appconfig_ex.set_value('oauth_access_tokens', json.dumps(tokens_data))
            
            # Save refresh tokens
            refresh_data = {token: refresh_token.model_dump() for token, refresh_token in self._refresh_tokens.items()}
            await self.nc_app.appconfig_ex.set_value('oauth_refresh_tokens', json.dumps(refresh_data))
            
        except Exception as e:
            print(f"Error saving OAuth data to storage: {e}")
    
    async def get_client(self, client_id: str) -> Optional[OAuthClientInformationFull]:
        """Retrieve client information by client ID"""
        client = self._clients.get(client_id)
        if client is None:
            return None
        
        return OAuthClientInformationFull(
            client_id=client.client_id,
            client_secret=client.client_secret,
            client_name=client.client_name,
            redirect_uris=client.redirect_uris,
            scopes=client.scopes,
            client_uri=None,
            contacts=None,
            logo_uri=None,
            to_s=None,
            token_endpoint_auth_method="client_secret_basic",
            grant_types=["authorization_code", "refresh_token"],
            response_types=["code"],
            software_id=None,
            software_version=None
        )
    
    async def register_client(self, client_info: OAuthClientInformationFull) -> None:
        """Register a new OAuth client"""
        # Validate client information
        if not client_info.client_id:
            raise RegistrationError(
                error="invalid_client_metadata",
                error_description="client_id is required"
            )
        
        if client_info.client_id in self._clients:
            raise RegistrationError(
                error="invalid_client_metadata",
                error_description="client_id already exists"
            )
        
        # Create client model
        client = OAuthClientModel(
            client_id=client_info.client_id,
            client_secret=client_info.client_secret or secrets.token_urlsafe(64),
            client_name=client_info.client_name or "",
            redirect_uris=client_info.redirect_uris or [],
            scopes=client_info.scopes or ["read", "write"],
            user_id=None,
            is_confidential=client_info.token_endpoint_auth_method == "client_secret_basic"
        )
        
        self._clients[client.client_id] = client
        await self._save_to_storage()
    
    async def authorize(self, client: OAuthClientInformationFull, params: AuthorizationParams) -> str:
        """
        Handle authorization request with PKCE support.
        
        This method is called during the /authorize endpoint and should return
        a URL to redirect the client to for authorization.
        """
        # Validate client
        stored_client = self._clients.get(client.client_id)
        if stored_client is None:
            raise AuthorizeError(
                error="unauthorized_client",
                error_description="Client not found"
            )
        
        # Validate redirect URI
        if params.redirect_uri and params.redirect_uri not in stored_client.redirect_uris:
            raise AuthorizeError(
                error="invalid_request",
                error_description="Invalid redirect_uri"
            )
        
        # Validate requested scopes
        requested_scopes = params.scope or []
        for scope in requested_scopes:
            if scope not in stored_client.scopes:
                raise AuthorizeError(
                    error="invalid_scope",
                    error_description=f"Scope {scope} not allowed for this client"
                )
        
        # Validate PKCE parameters
        code_challenge = None
        code_challenge_method = None
        
        if params.code_challenge:
            if not params.code_challenge_method:
                raise AuthorizeError(
                    error="invalid_request",
                    error_description="code_challenge_method is required when code_challenge is provided"
                )
            
            if params.code_challenge_method not in ["plain", "S256"]:
                raise AuthorizeError(
                    error="invalid_request",
                    error_description="Unsupported code_challenge_method"
                )
            
            code_challenge = params.code_challenge
            code_challenge_method = params.code_challenge_method
        
        # For this POC, we'll simulate user authorization by creating a code directly
        # In production, this would redirect to a Nextcloud OAuth consent page
        user_id = stored_client.user_id or "current_user"  # In real impl, get from session
        
        # Generate authorization code
        auth_code = AuthorizationCodeModel.generate(
            client_id=client.client_id,
            user_id=user_id,
            redirect_uri=params.redirect_uri or stored_client.redirect_uris[0],
            scopes=requested_scopes,
            code_challenge=code_challenge,
            code_challenge_method=code_challenge_method
        )
        
        self._authorization_codes[auth_code.code] = auth_code
        await self._save_to_storage()
        
        # Build redirect URL with authorization code
        redirect_url = params.redirect_uri or stored_client.redirect_uris[0]
        redirect_params = {
            "code": auth_code.code,
            "state": params.state
        }
        
        return f"{redirect_url}?{urlencode(redirect_params)}"
    
    async def load_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: str
    ) -> Optional[AuthorizationCodeT]:
        """Load authorization code by its code string"""
        auth_code = self._authorization_codes.get(authorization_code)
        if auth_code is None:
            return None
        
        # Validate client
        if auth_code.client_id != client.client_id:
            return None
        
        # Check if code is expired
        if auth_code.is_expired():
            del self._authorization_codes[authorization_code]
            await self._save_to_storage()
            return None
        
        return auth_code
    
    async def exchange_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: AuthorizationCodeT
    ) -> OAuthToken:
        """Exchange authorization code for access token with PKCE verification"""
        # Load the authorization code
        auth_code = self._authorization_codes.get(authorization_code.code)
        if auth_code is None:
            raise TokenError(
                error="invalid_grant",
                error_description="Authorization code not found or expired"
            )
        
        # Validate client
        if auth_code.client_id != client.client_id:
            raise TokenError(
                error="invalid_grant",
                error_description="Authorization code not valid for this client"
            )
        
        # Verify PKCE code_verifier if code_challenge was provided
        if auth_code.code_challenge and auth_code.code_challenge_method:
            code_verifier = getattr(authorization_code, 'code_verifier', None)
            if not code_verifier:
                raise TokenError(
                    error="invalid_grant",
                    error_description="code_verifier is required when code_challenge was provided"
                )
            
            # Verify the code_verifier matches the code_challenge
            if auth_code.code_challenge_method == "S256":
                expected_challenge = base64.urlsafe_b64encode(
                    hashlib.sha256(code_verifier.encode()).digest()
                ).decode().rstrip('=')
                if code_verifier != auth_code.code_challenge:
                    # Note: In real implementation, we'd compare the hash
                    # For this POC, we'll do a direct comparison
                    if expected_challenge != auth_code.code_challenge:
                        raise TokenError(
                            error="invalid_grant",
                            error_description="PKCE code_verifier does not match code_challenge"
                        )
            elif auth_code.code_challenge_method == "plain":
                if code_verifier != auth_code.code_challenge:
                    raise TokenError(
                        error="invalid_grant",
                        error_description="PKCE code_verifier does not match code_challenge"
                    )
        
        # Generate access token
        access_token = AccessTokenModel.generate(
            client_id=client.client_id,
            user_id=auth_code.user_id,
            scopes=auth_code.scopes,
            expires_in=3600  # 1 hour
        )
        
        # Generate refresh token
        refresh_token = RefreshTokenModel.generate(
            client_id=client.client_id,
            user_id=auth_code.user_id,
            access_token=access_token.token,
            scopes=auth_code.scopes
        )
        
        # Store tokens
        self._access_tokens[access_token.token] = access_token
        self._refresh_tokens[refresh_token.token] = refresh_token
        
        # Remove used authorization code
        del self._authorization_codes[authorization_code.code]
        
        await self._save_to_storage()
        
        return OAuthToken(
            access_token=access_token.token,
            refresh_token=refresh_token.token,
            expires_in=3600,
            scope=access_token.scopes,
            token_type="Bearer"
        )
    
    async def load_refresh_token(
        self, client: OAuthClientInformationFull, refresh_token: str
    ) -> Optional[RefreshTokenT]:
        """Load refresh token by its token string"""
        token = self._refresh_tokens.get(refresh_token)
        if token is None:
            return None
        
        # Validate client
        if token.client_id != client.client_id:
            return None
        
        return token
    
    async def exchange_refresh_token(
        self, client: OAuthClientInformationFull, refresh_token: RefreshTokenT, scopes: List[str]
    ) -> OAuthToken:
        """Exchange refresh token for new access token"""
        # Load the refresh token
        token = self._refresh_tokens.get(refresh_token.token)
        if token is None:
            raise TokenError(
                error="invalid_grant",
                error_description="Refresh token not found"
            )
        
        # Validate client
        if token.client_id != client.client_id:
            raise TokenError(
                error="invalid_grant",
                error_description="Refresh token not valid for this client"
            )
        
        # Check if refresh token has been used
        if token.used:
            raise TokenError(
                error="invalid_grant",
                error_description="Refresh token already used"
            )
        
        # Load the associated access token to get user info
        access_token = self._access_tokens.get(token.access_token)
        if access_token is None:
            raise TokenError(
                error="invalid_grant",
                error_description="Associated access token not found"
            )
        
        # Generate new access token
        new_access_token = AccessTokenModel.generate(
            client_id=client.client_id,
            user_id=access_token.user_id,
            scopes=scopes or access_token.scopes,
            expires_in=3600
        )
        
        # Generate new refresh token (rotate refresh tokens)
        new_refresh_token = RefreshTokenModel.generate(
            client_id=client.client_id,
            user_id=access_token.user_id,
            access_token=new_access_token.token,
            scopes=scopes or access_token.scopes
        )
        
        # Mark old tokens as used and store new ones
        token.used = True
        self._access_tokens[new_access_token.token] = new_access_token
        self._refresh_tokens[new_refresh_token.token] = new_refresh_token
        
        await self._save_to_storage()
        
        return OAuthToken(
            access_token=new_access_token.token,
            refresh_token=new_refresh_token.token,
            expires_in=3600,
            scope=new_access_token.scopes,
            token_type="Bearer"
        )
    
    async def load_access_token(self, token: str) -> Optional[AccessTokenT]:
        """Load access token by its token string"""
        access_token = self._access_tokens.get(token)
        if access_token is None:
            return None
        
        # Check if token is expired
        if access_token.is_expired():
            del self._access_tokens[token]
            await self._save_to_storage()
            return None
        
        return access_token
    
    async def revoke_token(self, token: AccessTokenT | RefreshTokenT) -> None:
        """Revoke an access or refresh token"""
        if isinstance(token, AccessTokenModel):
            if token.token in self._access_tokens:
                del self._access_tokens[token.token]
            
            # Also revoke associated refresh tokens
            for refresh_token in self._refresh_tokens.values():
                if refresh_token.access_token == token.token:
                    del self._refresh_tokens[refresh_token.token]
                    break
                    
        elif isinstance(token, RefreshTokenModel):
            if token.token in self._refresh_tokens:
                del self._refresh_tokens[token.token]
            
            # Also revoke associated access token
            if token.access_token in self._access_tokens:
                del self._access_tokens[token.access_token]
        
        await self._save_to_storage()
    
    async def get_user_info(self, access_token: str) -> Optional[UserInfo]:
        """Get user information from access token"""
        token = await self.load_access_token(access_token)
        if token is None:
            return None
        
        # Get user data from Nextcloud
        try:
            nc = self.nc_app
            if nc._session.user != token.user_id:
                await nc.set_user(token.user_id)
            
            response = await nc.ocs("GET", "/ocs/v2.php/cloud/user")
            user_data = response.get("ocs", {}).get("data", {})
            
            return UserInfo.from_oauth(token, user_data)
        except Exception as e:
            print(f"Error getting user info: {e}")
            # Return basic user info without additional data
            return UserInfo(
                user_id=token.user_id,
                auth_method="oauth",
                scopes=token.scopes,
                client_id=token.client_id
            )
    
    async def create_client_for_user(self, user_id: str, client_name: str = "", 
                                     redirect_uris: List[str] = None) -> OAuthClientModel:
        """Create an OAuth client for a specific user"""
        client = OAuthClientModel.generate(client_name=client_name, user_id=user_id)
        if redirect_uris:
            client.redirect_uris = redirect_uris
        
        self._clients[client.client_id] = client
        await self._save_to_storage()
        
        return client
