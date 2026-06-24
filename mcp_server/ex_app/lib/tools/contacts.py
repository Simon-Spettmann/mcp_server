# SPDX-FileCopyrightText: 2025 Nextcloud GmbH and Nextcloud contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
from typing import Optional

from nc_py_api import AsyncNextcloudApp


async def get_tools(nc: AsyncNextcloudApp):
    async def list_address_books() -> list[dict]:
        """
        List all address books
        :return: List of address books with their IDs and display names
        """
        address_books = await nc.contacts.get_address_books()
        return [
            {
                "id": ab.id,
                "displayName": ab.display_name,
                "description": getattr(ab, "description", None),
            }
            for ab in address_books
        ]

    async def list_all_contacts(address_book_id: Optional[str] = None, limit: int = 100) -> list[dict]:
        """
        List all contacts from a specific address book or all address books
        :param address_book_id: Optional ID of the address book to list contacts from
        :param limit: Maximum number of contacts to return
        :return: List of all contacts
        """
        if address_book_id:
            contacts = await nc.contacts.get_all_from_address_book(address_book_id, limit=limit)
        else:
            contacts = await nc.contacts.get_all(limit=limit)

        return [
            {
                "id": contact.id,
                "addressBookId": getattr(contact, "address_book_id", None),
                "displayName": contact.display_name,
                "givenName": getattr(contact, "given_name", None),
                "familyName": getattr(contact, "family_name", None),
                "email": getattr(contact, "email", None),
                "emails": getattr(contact, "emails", []),
                "phone": getattr(contact, "phone", None),
                "phones": getattr(contact, "phones", []),
                "address": getattr(contact, "address", None),
                "addresses": getattr(contact, "addresses", []),
                "organization": getattr(contact, "organization", None),
                "title": getattr(contact, "title", None),
                "note": getattr(contact, "note", None),
                "birthday": getattr(contact, "birthday", None),
                "url": getattr(contact, "url", None),
                "photo": getattr(contact, "photo", None),
            }
            for contact in contacts
        ]

    async def find_person_in_contacts(query: str, limit: int = 10) -> list[dict]:
        """
        Find a person in the user's contacts
        :param query: The search query (name, email, etc.)
        :param limit: Maximum number of results to return
        :return: List of matching contacts with their details
        """
        contacts = await nc.contacts.search(query, limit=limit)
        return [
            {
                "id": contact.id,
                "addressBookId": getattr(contact, "address_book_id", None),
                "displayName": contact.display_name,
                "givenName": getattr(contact, "given_name", None),
                "familyName": getattr(contact, "family_name", None),
                "email": getattr(contact, "email", None),
                "emails": getattr(contact, "emails", []),
                "phone": getattr(contact, "phone", None),
                "phones": getattr(contact, "phones", []),
            }
            for contact in contacts
        ]

    async def get_contact_info(contact_id: str) -> dict:
        """
        Get detailed information about a specific contact
        :param contact_id: The ID of the contact
        :return: Contact information
        """
        contacts = await nc.contacts.get_all(limit=100)
        for contact in contacts:
            if contact.id == contact_id:
                return {
                    "id": contact.id,
                    "addressBookId": getattr(contact, "address_book_id", None),
                    "displayName": contact.display_name,
                    "givenName": getattr(contact, "given_name", None),
                    "familyName": getattr(contact, "family_name", None),
                    "email": getattr(contact, "email", None),
                    "emails": getattr(contact, "emails", []),
                    "phone": getattr(contact, "phone", None),
                    "phones": getattr(contact, "phones", []),
                    "address": getattr(contact, "address", None),
                    "addresses": getattr(contact, "addresses", []),
                    "organization": getattr(contact, "organization", None),
                    "title": getattr(contact, "title", None),
                    "note": getattr(contact, "note", None),
                    "birthday": getattr(contact, "birthday", None),
                    "url": getattr(contact, "url", None),
                    "photo": getattr(contact, "photo", None),
                }
        raise ValueError(f"Contact not found: {contact_id}")

    async def create_contact(
        address_book_id: str,
        display_name: str,
        given_name: Optional[str] = None,
        family_name: Optional[str] = None,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        organization: Optional[str] = None,
        title: Optional[str] = None,
        address: Optional[str] = None,
        note: Optional[str] = None,
        birthday: Optional[str] = None,
        url: Optional[str] = None,
    ) -> str:
        """
        Create a new contact
        :param address_book_id: The ID of the address book to create the contact in
        :param display_name: The display name of the contact
        :param given_name: The given/first name
        :param family_name: The family/last name
        :param email: The email address
        :param phone: The phone number
        :param organization: The organization
        :param title: The job title
        :param address: The address
        :param note: Notes about the contact
        :param birthday: Birthday (format: YYYY-MM-DD)
        :param url: Website URL
        :return: The ID of the created contact
        """
        contact_data = {
            "displayName": display_name,
        }
        if given_name:
            contact_data["givenName"] = given_name
        if family_name:
            contact_data["familyName"] = family_name
        if email:
            contact_data["email"] = email
        if phone:
            contact_data["phone"] = phone
        if organization:
            contact_data["organization"] = organization
        if title:
            contact_data["title"] = title
        if address:
            contact_data["address"] = address
        if note:
            contact_data["note"] = note
        if birthday:
            contact_data["birthday"] = birthday
        if url:
            contact_data["url"] = url

        contact = await nc.contacts.create(address_book_id, contact_data)
        return contact.id

    async def update_contact(
        contact_id: str,
        display_name: Optional[str] = None,
        given_name: Optional[str] = None,
        family_name: Optional[str] = None,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        organization: Optional[str] = None,
        title: Optional[str] = None,
        address: Optional[str] = None,
        note: Optional[str] = None,
        birthday: Optional[str] = None,
        url: Optional[str] = None,
    ) -> bool:
        """
        Update an existing contact
        :param contact_id: The ID of the contact to update
        :param display_name: New display name (optional)
        :param given_name: New given name (optional)
        :param family_name: New family name (optional)
        :param email: New email (optional)
        :param phone: New phone (optional)
        :param organization: New organization (optional)
        :param title: New title (optional)
        :param address: New address (optional)
        :param note: New note (optional)
        :param birthday: New birthday (optional)
        :param url: New URL (optional)
        :return: True if successful
        """
        # Get the contact to find its address book
        contacts = await nc.contacts.get_all(limit=100)
        contact = next((c for c in contacts if c.id == contact_id), None)
        if contact is None:
            raise ValueError(f"Contact not found: {contact_id}")

        address_book_id = getattr(contact, "address_book_id", None)
        if not address_book_id:
            raise ValueError("Cannot determine address book for contact")

        # Build update data
        update_data = {}
        if display_name is not None:
            update_data["displayName"] = display_name
        if given_name is not None:
            update_data["givenName"] = given_name
        if family_name is not None:
            update_data["familyName"] = family_name
        if email is not None:
            update_data["email"] = email
        if phone is not None:
            update_data["phone"] = phone
        if organization is not None:
            update_data["organization"] = organization
        if title is not None:
            update_data["title"] = title
        if address is not None:
            update_data["address"] = address
        if note is not None:
            update_data["note"] = note
        if birthday is not None:
            update_data["birthday"] = birthday
        if url is not None:
            update_data["url"] = url

        if update_data:
            return await nc.contacts.update(address_book_id, contact_id, update_data)
        return True

    async def delete_contact(contact_id: str) -> bool:
        """
        Delete a contact
        :param contact_id: The ID of the contact to delete
        :return: True if successful
        """
        # Get the contact to find its address book
        contacts = await nc.contacts.get_all(limit=100)
        contact = next((c for c in contacts if c.id == contact_id), None)
        if contact is None:
            raise ValueError(f"Contact not found: {contact_id}")

        address_book_id = getattr(contact, "address_book_id", None)
        if not address_book_id:
            raise ValueError("Cannot determine address book for contact")

        return await nc.contacts.delete(address_book_id, contact_id)

    return [
        list_address_books,
        list_all_contacts,
        find_person_in_contacts,
        get_contact_info,
        create_contact,
        update_contact,
        delete_contact,
    ]


def get_category_name():
    return "Contacts"


async def is_available(nc: AsyncNextcloudApp):
    try:
        await nc.contacts.get_all(limit=1)
        return True
    except Exception:
        return False
