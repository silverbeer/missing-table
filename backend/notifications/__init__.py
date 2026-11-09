"""Live-match notification subsystem.

Dispatches chat messages (see notifications/registry.py) when match events (kickoff, goal,
card, halftime, fulltime) happen during a live match. Routes each match
to the home + away clubs' configured channels.
"""

from notifications.dispatcher import Notifier, get_notifier
from notifications.tasks import notify_event_task

__all__ = ["Notifier", "get_notifier", "notify_event_task"]
