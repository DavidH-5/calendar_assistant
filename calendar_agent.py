
# %%


import os

from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

import datetime
from zoneinfo import ZoneInfo
from pydantic import BaseModel, Field, EmailStr, ValidationError
from typing import List, Optional, Dict, Callable

from langchain_core.tools import tool
from langgraph.checkpoint.memory import InMemorySaver 
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langchain_core.messages import SystemMessage, AIMessage, HumanMessage, ToolMessage
from langgraph.types import Command
from langchain.agents.middleware import wrap_tool_call
from langchain.tools.tool_node import ToolCallRequest

from deepagents.backends import FilesystemBackend
from deepagents import create_deep_agent

from trustcall import create_extractor


# %%


model = ChatOpenAI(model = "gpt-4o-mini", temperature=0)


# %%


@tool(
    "get_time", 
    description="Get the current date and time in Australia/Melbourne timezone."
)
def get_time(days: int = 0) -> dict:

    """
    Get today's date or the date shifted from the current date

    Args:
        days: number of days from the current date
    """

    now = datetime.datetime.now(ZoneInfo("Australia/Melbourne"))
    shifted = now + datetime.timedelta(days=days)

    if days == 0:

         return {
            "current_datetime": now.isoformat(),
            "today_date": now.date().isoformat(),
            "today_day_of_week": now.strftime("%A"),

            "timezone": "Australia/Melbourne",
            "utc_offset": now.strftime("%z"),
        }

    else:

        return {
            "current_datetime": now.isoformat(),
            "today_date": now.date().isoformat(),
            "today_day_of_week": now.strftime("%A"),

            "shifted_datetime": shifted.isoformat(),
            "shifted_date": shifted.date().isoformat(),
            "shifted_day_of_week": shifted.strftime("%A"),

            "timezone": "Australia/Melbourne",
            "utc_offset": now.strftime("%z"),
        }


# %%


@tool(
    "get_events",
    description="Get calendar events between two RFC3339 timestamps from the user's Google Calendar."
)
def get_events(start_time: str, end_time: str) -> List[Dict]:
    
    """
    Get events from the user's Google Calendar.

    Args:
        start_time: RFC3339 timestamp (e.g. 2026-01-27T10:00:00+11:00)
        end_time: RFC3339 timestamp (e.g. 2026-01-27T12:00:00+11:00)
    """

    SCOPES = ["https://www.googleapis.com/auth/calendar"]
    if not os.path.exists("./auth/token.json"):
        raise RuntimeError("Google Calendar token not found. User needs to authenticate.")

    creds = Credentials.from_authorized_user_file("./auth/token.json", SCOPES)
    service = build("calendar", "v3", credentials=creds)

    events_result = (
            service.events()
            .list(
                calendarId = "primary",
                timeMin = start_time,
                timeMax = end_time,
                # maxResults = max_results,
                singleEvents = True,
                orderBy = "startTime",
            )
            .execute()
    )
    events = events_result.get("items", [])

    # Clean response for LLMs
    cleaned_events = []
    for e in events:
        cleaned_events.append({
            "id": e.get("id"),
            "title": e.get("summary"),
            "start": e.get("start", {}).get("dateTime") or e.get("start", {}).get("date"),
            "end": e.get("end", {}).get("dateTime") or e.get("end", {}).get("date"),
            "organizer": e.get("organizer", {}).get("email"),
            "attendees": [a.get("email") for a in e.get("attendees", [])],
            "status": e.get("status"),
        })
    
    return cleaned_events


# %%


@tool(
    "create_event",
    description="Add calendar events between two RFC3339 timestamps from the user's Google Calendar."
)
def create_event(title: str, start_time: str, end_time: str, attendees: List[str] = []) -> dict:
    
    """
    Add an event to the user's Google Calendar.

    Args:
        title: Title of the event.
        start_time: RFC3339 timestamp (e.g. 2026-01-27T10:00:00+11:00)
        end_time: RFC3339 timestamp (e.g. 2026-01-27T12:00:00+11:00)
        attendees: List of attendee email addresses.
    """
    
    SCOPES = ["https://www.googleapis.com/auth/calendar"]
    if not os.path.exists("./auth/token.json"):
        raise RuntimeError("Google Calendar token not found. User needs to authenticate.")
    
    creds = Credentials.from_authorized_user_file("./auth/token.json", SCOPES)
    service = build("calendar", "v3", credentials=creds)

    event = {
        "summary": title,
        "start": {
            "dateTime": start_time,
        },
        "end": {
            "dateTime": end_time,
        },
        "attendees": [{"email": email} for email in attendees],
    }

    created_event = (
       service.events()
        .insert(
            calendarId="primary",
            body=event,
            sendUpdates="all"
        )
        .execute()
    )

    return {
        "event_id": created_event.get("id"),
        "html_link": created_event.get("htmlLink"),
    }


# %%


import googleapiclient.errors
from langchain_core.tools import tool

@tool(
    "remove_event",
    description="Cancel calendar events by event id from the user's Google Calendar."
)
def remove_event(event_id: str) -> dict:
    """
    Cancel an event from the user's Google Calendar.

    Args:
        event_id: ID of the event to be cancelled.
    """

    SCOPES = ["https://www.googleapis.com/auth/calendar"]
    if not os.path.exists("./auth/token.json"):
        return {
            "event_id": event_id,
            "status": "error",
            "error": "auth_missing",
            "message": "Google Calendar token not found. User needs to authenticate.",
        }

    creds = Credentials.from_authorized_user_file("./auth/token.json", SCOPES)
    service = build("calendar", "v3", credentials=creds)

    try:
        # Optional: check existence first (gives nicer error messages)
        service.events().get(calendarId="primary", eventId=event_id).execute()

        # Delete event
        service.events().delete(
            calendarId="primary",
            eventId=event_id,
            sendUpdates="all"
        ).execute()

        return {
            "event_id": event_id,
            "status": "cancelled",
        }

    except googleapiclient.errors.HttpError as e:
        # 404 = event not found / already deleted
        status = getattr(e.resp, "status", None)

        if status == 404:
            return {
                "event_id": event_id,
                "status": "not_found",
                "message": "Event does not exist (already deleted or invalid event_id).",
            }

        # Other Google API errors
        return {
            "event_id": event_id,
            "status": "error",
            "error": "google_calendar_http_error",
            "http_status": status,
            "message": str(e),
        }

    except Exception as e:
        # Any unexpected runtime error
        return {
            "event_id": event_id,
            "status": "error",
            "error": "unexpected_error",
            "message": str(e),
        }


# %%


@tool(
    "update_event",
    description="Update calendar events by event id from the user's Google Calendar."
)
def update_event(event_id: str, title: str = None, start_time: str = None, end_time: str = None, attendees: List[str] = None) -> dict:  
    
    """
    Update an event in the user's Google Calendar.

    Args:
        event_id: ID of the event to be updated.
        title: New title of the event.
        start_time: New RFC3339 timestamp for start time.
        end_time: New RFC3339 timestamp for end time.
        attendees: New list of attendee email addresses.
    """
    
    SCOPES = ["https://www.googleapis.com/auth/calendar"]
    if not os.path.exists("./auth/token.json"):
        raise RuntimeError("Google Calendar token not found. User needs to authenticate.")
    
    creds = Credentials.from_authorized_user_file("./auth/token.json", SCOPES)
    service = build("calendar", "v3", credentials=creds)

    event = service.events().get(calendarId="primary", eventId=event_id).execute()

    if title:
        event["summary"] = title
    if start_time:
        event["start"] = {"dateTime": start_time}
    if end_time:
        event["end"] = {"dateTime": end_time}
    if attendees is not None:
        event["attendees"] = [{"email": email} for email in attendees]

    updated_event = service.events().update(calendarId="primary", eventId=event_id, body=event, sendUpdates="all").execute()

    return {
        "event_id": updated_event.get("id"),
        "html_link": updated_event.get("htmlLink"),
    }


# %%
##################################################
#   Conflict Guard Middleware
##################################################


def get_events_plain_tool(start_time: str, end_time: str) -> List[Dict]:
    
    """
    Get events from the user's Google Calendar.

    Args:
        start_time: RFC3339 timestamp (e.g. 2026-01-27T10:00:00+11:00)
        end_time: RFC3339 timestamp (e.g. 2026-01-27T12:00:00+11:00)
    """

    SCOPES = ["https://www.googleapis.com/auth/calendar"]
    if not os.path.exists("./auth/token.json"):
        raise RuntimeError("Google Calendar token not found. User needs to authenticate.")

    creds = Credentials.from_authorized_user_file("./auth/token.json", SCOPES)
    service = build("calendar", "v3", credentials=creds)

    events_result = (
            service.events()
            .list(
                calendarId = "primary",
                timeMin = start_time,
                timeMax = end_time,
                # maxResults = max_results,
                singleEvents = True,
                orderBy = "startTime",
            )
            .execute()
    )
    events = events_result.get("items", [])

    # Clean response for LLMs
    cleaned_events = []
    for e in events:
        cleaned_events.append({
            "id": e.get("id"),
            "title": e.get("summary"),
            "start": e.get("start", {}).get("dateTime") or e.get("start", {}).get("date"),
            "end": e.get("end", {}).get("dateTime") or e.get("end", {}).get("date"),
            "organizer": e.get("organizer", {}).get("email"),
            "attendees": [a.get("email") for a in e.get("attendees", [])],
            "status": e.get("status"),
        })
    
    return cleaned_events

@wrap_tool_call
def conflict_guard_tool(
    request: ToolCallRequest,
    handler: Callable[[ToolCallRequest], ToolMessage | Command],
) -> ToolMessage | Command:
    
    """
    Wrap calendar write tools to enforce conflict checking before execution.
    """

    tool_name = request.tool_call["name"]
    args = request.tool_call["args"]

    # Only intercept calendar write tools
    if tool_name not in ("create_event", "update_event"):
        return handler(request)

    start_time = args.get("start_time")
    end_time = args.get("end_time")

    if not start_time or not end_time:
        raise ValueError("Missing start_time or end_time for conflict check")

    existing_events = get_events_plain_tool(start_time=start_time, end_time=end_time)

    # Detect conflicts
    conflicts = []
    for e in existing_events:
        e_start = e["start"]
        e_end = e["end"]
        # Two events conflict if: new_start < existing_end AND new_end > existing_start
        if start_time < e_end and end_time > e_start:
            conflicts.append(e)

    if conflicts:
        # # Stop execution and return conflicts for agent/user decision
        return ToolMessage(
            content={
                "error": "Conflict detected",
                "message": "The requested time overlaps with existing events.",
                "conflicting_events": conflicts,
            },
            tool_call_id=request.tool_call.get("id") 
        )
    
    # No conflicts, proceed with the original tool call
    return handler(request)


# %%


base_dir = os.path.dirname(os.path.abspath(__file__))

model = ChatOpenAI(model="gpt-4o-mini", temperature=0)

checkpointer = InMemorySaver()

tools = [
    get_time,
    get_events,
    create_event,
    remove_event,
    update_event,
]

agent = create_deep_agent(
    model = model,                                  
    memory = ["./AGENT.md"],                       
    skills = ["./skills/"],                         
    tools = tools,                              
    subagents = [],                                 
    backend = FilesystemBackend(root_dir = base_dir),
    middleware = [conflict_guard_tool],
    checkpointer = checkpointer,
)


# %%
# agent invoke


config = {"configurable": {"thread_id": "3"}}
result = agent.invoke(
    {"messages": [{"role": "user", "content": "Book a meeting with David (dave@hotmail.com) next Monday 10am to 11am."}]},
    config
)


# %%
# print all messages


for i in result['messages']:
    i.pretty_print()


# %%
# ToDo Tracking


states = checkpointer.get(config = config)
states['channel_values']['todos']


# %%
