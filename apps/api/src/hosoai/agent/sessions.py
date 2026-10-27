"""In-memory agent sessions (dev/demo). Answers live only in this process; nothing is logged."""

from collections import OrderedDict
from functools import lru_cache

from hosoai.agent.loop import Session

MAX_SESSIONS = 500


class SessionStore:
    def __init__(self) -> None:
        self._items: OrderedDict[str, Session] = OrderedDict()

    def put(self, session: Session) -> None:
        self._items[session.id] = session
        self._items.move_to_end(session.id)
        while len(self._items) > MAX_SESSIONS:
            self._items.popitem(last=False)

    def get(self, session_id: str) -> Session | None:
        return self._items.get(session_id)


@lru_cache
def get_sessions() -> SessionStore:
    return SessionStore()
