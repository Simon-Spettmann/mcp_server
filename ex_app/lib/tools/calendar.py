# SPDX-FileCopyrightText: 2025 Nextcloud GmbH and Nextcloud contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Optional

import pytz
from ics import Calendar, Event
from nc_py_api import AsyncNextcloudApp
from niquests import ConnectionError, Timeout


async def get_tools(nc: AsyncNextcloudApp):
    async def list_calendars():
        """
        List all calendars of the current user
        :return: list of calendars with their ids and display names
        """
        calendars = await nc.calendar.get_calendars()
        return [{"id": cal.id, "displayName": cal.display_name} for cal in calendars]

    async def get_calendar_info(calendar_id: str) -> dict:
        """
        Get information about a specific calendar
        :param calendar_id: The ID of the calendar
        :return: Calendar information
        """
        calendars = await nc.calendar.get_calendars()
        for cal in calendars:
            if cal.id == calendar_id:
                return {
                    "id": cal.id,
                    "displayName": cal.display_name,
                    "color": getattr(cal, "color", None),
                    "timezone": getattr(cal, "timezone", None),
                    "components": getattr(cal, "components", None),
                }
        raise ValueError(f"Calendar not found: {calendar_id}")

    async def list_calendar_events(
        calendar_id: str, start_date: Optional[str] = None, end_date: Optional[str] = None, limit: Optional[int] = None
    ) -> list[dict]:
        """
        List all events in a calendar
        :param calendar_id: The id of the calendar to list events from
        :param start_date: The start date for the query (format: YYYY-MM-DD or ISO datetime)
        :param end_date: The end date for the query (format: YYYY-MM-DD or ISO datetime)
        :param limit: Maximum number of events to return
        :return: list of events
        """
        if start_date is None:
            start_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if end_date is None:
            end_date = (datetime.now(timezone.utc) + timedelta(days=365)).strftime("%Y-%m-%d")

        events = await nc.calendar.get_events(calendar_id, start_date, end_date)

        # Limit results if requested
        if limit is not None:
            events = events[:limit]

        return [
            {
                "id": event.uid,
                "summary": event.summary,
                "start": event.begin,
                "end": event.end,
                "description": event.description,
                "location": event.location,
                "allDay": getattr(event, "all_day", False),
                "recurring": getattr(event, "recurring", False),
                "organizer": getattr(event, "organizer", None),
                "attendees": getattr(event, "attendees", []),
            }
            for event in events
        ]

    async def get_event_info(calendar_id: str, event_uid: str) -> dict:
        """
        Get detailed information about a specific event
        :param calendar_id: The ID of the calendar containing the event
        :param event_uid: The UID of the event
        :return: Event information
        """
        events = await nc.calendar.get_events(calendar_id)
        for event in events:
            if event.uid == event_uid:
                return {
                    "id": event.uid,
                    "summary": event.summary,
                    "start": event.begin,
                    "end": event.end,
                    "description": event.description,
                    "location": event.location,
                    "allDay": getattr(event, "all_day", False),
                    "recurring": getattr(event, "recurring", False),
                    "organizer": getattr(event, "organizer", None),
                    "attendees": getattr(event, "attendees", []),
                    "categories": getattr(event, "categories", []),
                    "status": getattr(event, "status", None),
                    "transparency": getattr(event, "transparency", None),
                }
        raise ValueError(f"Event not found: {event_uid}")

    async def create_calendar_event(
        calendar_id: str,
        summary: str,
        start_date: str,
        end_date: str,
        description: str = "",
        location: str = "",
        attendees: Optional[list[str]] = None,
        all_day: bool = False,
        categories: Optional[list[str]] = None,
    ) -> str:
        """
        Create a new event in a calendar
        :param calendar_id: The id of the calendar to create the event in
        :param summary: The summary of the event
        :param start_date: The start date of the event (format: YYYY-MM-DD or ISO datetime)
        :param end_date: The end date of the event (format: YYYY-MM-DD or ISO datetime)
        :param description: The description of the event
        :param location: The location of the event
        :param attendees: List of attendee email addresses
        :param all_day: Whether this is an all-day event
        :param categories: List of categories/tags for the event
        :return: The UID of the created event
        """
        i = 0
        while i < 20:
            try:
                event = await nc.calendar.create_event(
                    calendar_id,
                    summary=summary,
                    begin=start_date,
                    end=end_date,
                    description=description,
                    location=location,
                    all_day=all_day,
                )
                if attendees:
                    for attendee in attendees:
                        await nc.calendar.add_attendee(calendar_id, event.uid, attendee)
                if categories:
                    # Categories would need to be set via PROPPATCH, which nc-py-api might not support
                    pass
                return event.uid
            except (ConnectionError, Timeout) as e:
                await asyncio.sleep(1)
                i += 1
                continue
        raise Exception("Failed to create calendar event")

    async def update_calendar_event(
        calendar_id: str,
        event_uid: str,
        summary: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        description: Optional[str] = None,
        location: Optional[str] = None,
    ) -> bool:
        """
        Update an existing event in a calendar
        :param calendar_id: The ID of the calendar containing the event
        :param event_uid: The UID of the event to update
        :param summary: New summary (optional)
        :param start_date: New start date (optional)
        :param end_date: New end date (optional)
        :param description: New description (optional)
        :param location: New location (optional)
        :return: True if successful
        """
        i = 0
        while i < 20:
            try:
                # Build update data
                update_data = {}
                if summary is not None:
                    update_data["summary"] = summary
                if start_date is not None:
                    update_data["begin"] = start_date
                if end_date is not None:
                    update_data["end"] = end_date
                if description is not None:
                    update_data["description"] = description
                if location is not None:
                    update_data["location"] = location

                if update_data:
                    await nc.calendar.update_event(calendar_id, event_uid, **update_data)
                return True
            except (ConnectionError, Timeout) as e:
                await asyncio.sleep(1)
                i += 1
                continue
        return False

    async def delete_calendar_event(calendar_id: str, event_uid: str) -> bool:
        """
        Delete an event from a calendar
        :param calendar_id: The id of the calendar containing the event
        :param event_uid: The UID of the event to delete
        """
        i = 0
        while i < 20:
            try:
                await nc.calendar.delete_event(calendar_id, event_uid)
                return True
            except (ConnectionError, Timeout) as e:
                await asyncio.sleep(1)
                i += 1
                continue
        raise Exception("Failed to delete calendar event")

    async def list_todos(calendar_id: str) -> list[dict]:
        """
        List all todos/tasks from a calendar
        :param calendar_id: The ID of the calendar to list todos from
        :return: List of todos
        """
        try:
            todos = await nc.calendar.get_todos(calendar_id)
            return [
                {
                    "id": todo.uid,
                    "summary": todo.summary,
                    "description": todo.description,
                    "due": getattr(todo, "due", None),
                    "completed": getattr(todo, "completed", False),
                    "priority": getattr(todo, "priority", None),
                    "categories": getattr(todo, "categories", []),
                }
                for todo in todos
            ]
        except Exception as e:
            # Some Nextcloud versions might not support todos
            return []

    async def create_todo(
        calendar_id: str,
        summary: str,
        description: str = "",
        due: Optional[str] = None,
        priority: Optional[int] = None,
        categories: Optional[list[str]] = None,
    ) -> str:
        """
        Create a new todo/task in a calendar
        :param calendar_id: The ID of the calendar to create the todo in
        :param summary: The summary of the todo
        :param description: The description of the todo
        :param due: Due date for the todo (format: YYYY-MM-DD or ISO datetime)
        :param priority: Priority level (1-9, where 1 is highest)
        :param categories: List of categories/tags for the todo
        :return: The UID of the created todo
        """
        i = 0
        while i < 20:
            try:
                todo = await nc.calendar.create_todo(
                    calendar_id,
                    summary=summary,
                    description=description,
                    due=due,
                    priority=priority,
                )
                return todo.uid
            except (ConnectionError, Timeout):
                await asyncio.sleep(1)
                i += 1
                continue
            except Exception:
                pass
                break

        raise Exception("Failed to create todo - todos may not be supported")

    return [
        list_calendars,
        get_calendar_info,
        list_calendar_events,
        get_event_info,
        create_calendar_event,
        update_calendar_event,
        delete_calendar_event,
        list_todos,
        create_todo,
    ]


def get_category_name():
    return "Calendar"


async def is_available(nc: AsyncNextcloudApp):
    try:
        await nc.calendar.get_calendars()
        return True
    except Exception:
        return False
