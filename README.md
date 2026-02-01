📅 DeepAgent Google Calendar Assistant (with Conflict Guard)
This project implements a personal calendar assistant using:
LangChain Deep Agent (deepagents)
LangGraph middleware (wrap_tool_call)
Google Calendar API
In-memory checkpointing for conversation state + TODO tracking
It can:
✅ Get current time in Australia/Melbourne
✅ List calendar events in a time range
✅ Create events
✅ Update events
✅ Remove events
✅ Block event creation/update if a conflict is detected (middleware guard)
