---
name: manage-calendar-events
description: Retrieve, create, update, and delete events in the user's calendar based on user instructions.
---

# Manage Calendar Events Skill

## Purpose
This skill enables the agent to manage the user's calendar by reading existing events, creating new events, updating existing events, or removing events safely and accurately.

---

## Available Tools
- `get_time`: Get the current datetime or event date.
- `get_events`: Retrieve calendar events within a given timeframe.
- `create_event`: Create a new calendar event.
- `update_event`: Update an existing calendar event.
- `remove_event`: Delete an existing calendar event.
- `write_todos`: Break down a complex calendar request into steps.

---

## When to Use This Skill
Use this skill whenever the user asks to:
- **View** events (e.g., “What meetings do I have tomorrow?”)
- **Create** events (e.g., “Book a meeting with Pete next week”)
- **Update** events (e.g., “Move my 2pm meeting to 3pm”)
- **Delete** events (e.g., “Cancel my dentist appointment”)

---

## General Operating Rules
1. **Always confirm timeframe interpretation**
   - If the user gives a relative time (“tomorrow afternoon”), convert it using `get_time` by passing the number of days it is from today's date.
   - If timezone is unclear, ask the user or default to the user’s local timezone if known.

2. **Never execute a write action with missing required slots**
   - If required slots are missing, do **NOT** call `create_event`, `update_event`, or `remove_event`.
   - Ask a clarification question for the missing slots.

3. **Prefer minimal disruption**
   - When scheduling, avoid moving or deleting existing events unless the user explicitly requests it.

4. **Be explicit when ambiguity exists**
   - If multiple events match a request (“Move my meeting with Alex”), list candidates and ask which one.

---

## Required Slots (Minimum Fields)

### Create Event (Required)
- `title` (or purpose/summary)
- `start_time`
- `end_time` (or duration)

Conditional
- attendees (emails are required if any attendee is mentioned)

### Update Event (Required)
- event identifier (or uniquely identifiable event from `get_events`)
- the fields to change (time/title/location/etc.)

### Remove Event (Required)
- event identifier (or uniquely identifiable event from `get_events`)

---

# Workflows

## 1) Read Events Workflow (Retrieval)

### When to Use
Use when user asks to view availability, schedule, or event details.

### Steps
1. **Identify timeframe**
   - Determine `start_time` and `end_time`.
   - If missing: ask user (“Which day or date range should I check?”)

2. **Retrieve events**
   - Call `get_events(start_time, end_time)`

3. **Summarize results**
   - Provide a concise list including:
     - title
     - start/end time
     - location (if available)
   - If no events: clearly say “You’re free in this period.”

---

## 2) Create Event Workflow

### When to Use
User wants to schedule something new.

### Steps
1. **Plan**
   - Use `write_todos` for multi-step requests and tool planning

2. **Identify timeframe**
   - Determine `start_time` and `end_time`.
   - If missing: ask user (“Which day or date range should I check?”)

3. **Conflict check**
   - Call `get_events(start_time, end_time)` for the target window.
   - If conflict exists:
     - show the conflicting event(s)
     - ask user what to do:
       - choose a different time
       - keep both (if acceptable)
       - reschedule/cancel existing event (only if user approves)

4. **Validate required slots**
   - If any required slot is missing → ask targeted follow-up questions.
   - Do not call `create_event` yet.

5. **Create**
   - Call `create_event(...)` once confirmed and conflict policy is resolved.

6. **Confirm outcome**
   - Return final details: title, time, and any attendees/location.

---

## 3) Update Event Workflow

### When to Use
User wants to modify an existing event.

### Steps
1. **Identify the target event**
   - If the user provides a unique event reference → proceed.
   - Otherwise:
     - infer timeframe from the request
     - call `get_events(...)`
     - list candidates and ask user to confirm which one

2. **Validate**
   - Ensure the updated schedule is valid (start < end).
   - If updating time, run a conflict check using `get_events(new_start, new_end)`.
   - Ensure validate email for each attendee is provided

3. **Update**
   - Call `update_event(...)`

4. **Confirm outcome**
   - Provide updated event details.

---

## 4) Remove Event Workflow

### When to Use
User asks to cancel/delete an event.

### Steps
1. **Identify the event**
   - If ambiguous:
     - call `get_events(...)`
     - list matching events
     - ask user to confirm which to delete

2. **Delete**
   - Call `remove_event(...)`

3. **Confirm outcome**
   - Confirm deletion with event title + time.

---

# Conflict Handling Policy
An event is considered a conflict if time ranges overlap.

If conflict is detected:
- Always show the conflict clearly
- Ask user for a decision:
  1) choose a different time
  2) keep both
  3) reschedule/cancel the conflicting event (only with explicit approval)

---

# Clarification Questions (Examples)
- “What date should I schedule it for?”
- “What time should it start, and how long is the meeting?”
- “Which timezone should I use?”
- “I found 2 events that match — which one do you mean?”
- “This overlaps with another meeting. Do you want to move it or pick another time?”

---
