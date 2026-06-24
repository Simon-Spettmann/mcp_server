# SPDX-FileCopyrightText: 2025 Nextcloud GmbH and Nextcloud contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
from typing import Optional

from nc_py_api import AsyncNextcloudApp


async def get_tools(nc: AsyncNextcloudApp):
    async def create_share(
        path: str,
        share_type: int,
        share_with: str,
        permissions: int = 1,  # 1 = read, 2 = write, 4 = share, etc.
        expiration: Optional[str] = None,
    ) -> dict:
        """
        Create a new share for a file or directory
        :param path: The path to the file or directory to share
        :param share_type: Type of share (0 = user, 1 = group, 3 = public link, 4 = email, 6 = circle)
        :param share_with: User, group, email, or circle to share with (or empty for public link)
        :param permissions: Bitmask of permissions (1=read, 2=write, 4=share, 8=delete, 16=all)
        :param expiration: Optional expiration date (format: YYYY-MM-DD)
        :return: Share information including share ID and token
        """
        # Get file info first to get the file ID
        files = await nc.files.list(path)
        if not files:
            raise ValueError(f"File not found: {path}")
        file_id = files[0].id if hasattr(files[0], "id") else None

        # Create the share
        share_data = {
            "shareType": share_type,
            "shareWith": share_with,
            "path": path,
            "permissions": permissions,
        }
        if expiration:
            share_data["expireDate"] = expiration

        # Use OCS API for sharing
        share = await nc.ocs("POST", "/ocs/v2.php/apps/files_sharing/api/v1/shares", json=share_data)
        return share.get("ocs", {}).get("data", {})

    async def list_shares(path: Optional[str] = None, share_type: Optional[int] = None) -> list[dict]:
        """
        List shares for a file or for the current user
        :param path: Optional path to filter shares for a specific file
        :param share_type: Optional share type to filter by
        :return: List of share information
        """
        params = {}
        if path:
            params["path"] = path
        if share_type is not None:
            params["share_type"] = share_type

        shares = await nc.ocs("GET", "/ocs/v2.php/apps/files_sharing/api/v1/shares", params=params)
        return shares.get("ocs", {}).get("data", [])

    async def get_share_info(share_id: int) -> dict:
        """
        Get information about a specific share
        :param share_id: The ID of the share to get info for
        :return: Share information
        """
        share = await nc.ocs("GET", f"/ocs/v2.php/apps/files_sharing/api/v1/shares/{share_id}")
        return share.get("ocs", {}).get("data", {})

    async def delete_share(share_id: int) -> bool:
        """
        Delete a share
        :param share_id: The ID of the share to delete
        :return: True if successful
        """
        try:
            await nc.ocs("DELETE", f"/ocs/v2.php/apps/files_sharing/api/v1/shares/{share_id}")
            return True
        except Exception:
            return False

    async def update_share_permissions(share_id: int, permissions: int) -> dict:
        """
        Update permissions for a share
        :param share_id: The ID of the share to update
        :param permissions: New permissions bitmask
        :return: Updated share information
        """
        share = await nc.ocs(
            "PUT", f"/ocs/v2.php/apps/files_sharing/api/v1/shares/{share_id}", json={"permissions": permissions}
        )
        return share.get("ocs", {}).get("data", {})

    return [
        create_share,
        list_shares,
        get_share_info,
        delete_share,
        update_share_permissions,
    ]


def get_category_name():
    return "Sharing"


async def is_available(nc: AsyncNextcloudApp):
    try:
        # Check if files_sharing app is available
        caps = await nc.capabilities
        return "files_sharing" in caps
    except Exception:
        return False
