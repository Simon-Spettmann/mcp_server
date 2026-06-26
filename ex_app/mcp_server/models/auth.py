# SPDX-FileCopyrightText: 2025 Nextcloud GmbH and Nextcloud contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Authentication models for OAuth 2.1 implementation."""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field
import secrets


class OAuthClient(BaseModel):
    """OAuth client information."""

    client_id: str = Field(..., description="Unique client identifier")
    client_secret: str = Field(..., description="Client secret")
    client_name: str = Field(default="", description="Human-readable client name")
    redirect_uris: List[str] = Field(default_factory=list, description="Allowed redirect URIs")
    scopes: List[str] = Field(default_factory=list, description="Allowed scopes")
    user_id: Optional[str] = Field(default=None, description="Associated user ID")
    created_at: datetime = Field(default_factory=datetime.now, description="Creation timestamp")
    is_confidential: bool = Field(default=True, description="Whether client is confidential")

    @classmethod
    def generate(cls, client_name: str = "", user_id: Optional[str] = None) -> "OAuthClient":
        """Generate a new OAuth client with secure random credentials."""
        return cls(
            client_id=secrets.token_urlsafe(32),
            client_secret=secrets.token_urlsafe(64),
            client_name=client_name,
            user_id=user_id,
            is_confidential=True,
        )


class AuthorizationCode(BaseModel):
    """OAuth authorization code with PKCE support."""

    code: str = Field(..., description="Authorization code")
    client_id: str = Field(..., description="Client ID that requested the code")
    user_id: str = Field(..., description="User ID that authorized the code")
    redirect_uri: str = Field(..., description="Redirect URI for the authorization response")
    scopes: List[str] = Field(default_factory=list, description="Granted scopes")
    code_challenge: Optional[str] = Field(default=None, description="PKCE code challenge")
    code_challenge_method: Optional[str] = Field(default=None, description="PKCE code challenge method")
    expires_at: datetime = Field(
        default_factory=lambda: datetime.now(), description="Expiration timestamp"
    )

    @classmethod
    def generate(
        cls,
        client_id: str,
        user_id: str,
        redirect_uri: str,
        scopes: List[str],
        code_challenge: Optional[str] = None,
        code_challenge_method: Optional[str] = None,
    ) -> "AuthorizationCode":
        """Generate a new authorization code."""
        from datetime import timedelta
        return cls(
            code=secrets.token_urlsafe(48),
            client_id=client_id,
            user_id=user_id,
            redirect_uri=redirect_uri,
            scopes=scopes or [],
            code_challenge=code_challenge,
            code_challenge_method=code_challenge_method,
            expires_at=datetime.now() + timedelta(minutes=10),  # 10 minute expiration
        )

    def is_expired(self) -> bool:
        """Check if the authorization code has expired."""
        return datetime.now() > self.expires_at


class AccessToken(BaseModel):
    """OAuth access token."""

    token: str = Field(..., description="Access token string")
    client_id: str = Field(..., description="Client ID that owns the token")
    user_id: str = Field(..., description="User ID that the token represents")
    scopes: List[str] = Field(default_factory=list, description="Granted scopes")
    refresh_token: Optional[str] = Field(default=None, description="Associated refresh token")
    expires_at: datetime = Field(..., description="Expiration timestamp")
    created_at: datetime = Field(default_factory=datetime.now, description="Creation timestamp")

    @classmethod
    def generate(
        cls, client_id: str, user_id: str, scopes: List[str], expires_in: int = 3600
    ) -> "AccessToken":
        """Generate a new access token."""
        from datetime import timedelta
        return cls(
            token=secrets.token_urlsafe(64),
            client_id=client_id,
            user_id=user_id,
            scopes=scopes,
            refresh_token=secrets.token_urlsafe(64),
            expires_at=datetime.now() + timedelta(seconds=expires_in),
        )

    def is_expired(self) -> bool:
        """Check if the access token has expired."""
        return datetime.now() > self.expires_at


class RefreshToken(BaseModel):
    """OAuth refresh token."""

    token: str = Field(..., description="Refresh token string")
    client_id: str = Field(..., description="Client ID that owns the token")
    user_id: str = Field(..., description="User ID that the token represents")
    access_token: str = Field(..., description="Associated access token")
    scopes: List[str] = Field(default_factory=list, description="Granted scopes")
    created_at: datetime = Field(default_factory=datetime.now, description="Creation timestamp")
    used: bool = Field(default=False, description="Whether the token has been used")

    @classmethod
    def generate(
        cls, client_id: str, user_id: str, access_token: str, scopes: List[str]
    ) -> "RefreshToken":
        """Generate a new refresh token."""
        return cls(
            token=secrets.token_urlsafe(64),
            client_id=client_id,
            user_id=user_id,
            access_token=access_token,
            scopes=scopes,
        )


class UserInfo(BaseModel):
    """User information from authentication."""

    user_id: str = Field(..., description="Nextcloud user ID")
    username: Optional[str] = Field(default=None, description="Username")
    display_name: Optional[str] = Field(default=None, description="Display name")
    email: Optional[str] = Field(default=None, description="Email address")
    auth_method: str = Field(..., description="Authentication method used")
    scopes: List[str] = Field(default_factory=list, description="Granted scopes")
    client_id: Optional[str] = Field(default=None, description="OAuth client ID if applicable")

    @classmethod
    def from_oauth(cls, access_token: "AccessToken", user_data: dict) -> "UserInfo":
        """Create UserInfo from OAuth access token and user data."""
        return cls(
            user_id=user_data.get("id", access_token.user_id),
            username=user_data.get("username"),
            display_name=user_data.get("display_name"),
            email=user_data.get("email"),
            auth_method="oauth",
            scopes=access_token.scopes,
            client_id=access_token.client_id,
        )

    @classmethod
    def from_app_password(cls, username: str, user_data: dict) -> "UserInfo":
        """Create UserInfo from App Password authentication."""
        return cls(
            user_id=user_data.get("id", username),
            username=username,
            display_name=user_data.get("display_name"),
            email=user_data.get("email"),
            auth_method="app_password",
            scopes=["read", "write"],  # Default scopes for App Password
            client_id=None,
        )
