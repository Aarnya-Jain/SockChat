"""
Domain models for Collaborative Canvas.
Encapsulates Room, User, and CanvasEvent state representations.
"""
import time
import uuid
from typing import Dict, List, Optional, Any
from server import config


USER_PALETTE = [
    "#E63946", "#457B9D", "#2A9D8F", "#E76F51",
    "#8338EC", "#3A86FF", "#FB8500", "#06D6A0"
]


class User:
    """Represents a connected participant in a room."""
    def __init__(self, name: str, conn_id: str, user_id: Optional[str] = None):
        self.user_id: str = user_id or uuid.uuid4().hex[:8]
        self.name: str = name
        self.conn_id: str = conn_id
        self.joined_at: float = time.time()
        # Deterministic or index-based user color for chat badge / cursors
        idx = abs(hash(self.user_id)) % len(USER_PALETTE)
        self.color: str = USER_PALETTE[idx]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "name": self.name,
            "color": self.color,
            "joined_at": self.joined_at
        }


class CanvasEvent:
    """Represents a discrete drawing segment or canvas operation."""
    def __init__(self, x1: float, y1: float, x2: float, y2: float,
                 color: str, width: int, mode: str = "pen", from_user: Optional[str] = None):
        self.x1 = x1
        self.y1 = y1
        self.x2 = x2
        self.y2 = y2
        self.color = color
        self.width = width
        self.mode = mode
        self.from_user = from_user
        self.timestamp = time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": "draw",
            "x1": self.x1,
            "y1": self.y1,
            "x2": self.x2,
            "y2": self.y2,
            "color": self.color,
            "width": self.width,
            "mode": self.mode,
            "from": self.from_user,
            "timestamp": self.timestamp
        }


class Room:
    """
    Represents an isolated collaboration space.
    Maintains active users, drawing history, and chat messages.
    """
    def __init__(self, key: str, max_users: int = config.DEFAULT_MAX_ROOM_USERS):
        self.key: str = key.upper()
        self.max_users: int = max_users
        self.created_at: float = time.time()
        self.users: Dict[str, User] = {}  # user_id -> User
        self.strokes: List[Dict[str, Any]] = []
        self.chat_history: List[Dict[str, Any]] = []

    def is_full(self) -> bool:
        return len(self.users) >= self.max_users

    def is_empty(self) -> bool:
        return len(self.users) == 0

    def add_user(self, user: User) -> bool:
        if self.is_full():
            return False
        self.users[user.user_id] = user
        return True

    def remove_user(self, user_id: str) -> Optional[User]:
        return self.users.pop(user_id, None)

    def get_user_by_conn(self, conn_id: str) -> Optional[User]:
        for u in self.users.values():
            if u.conn_id == conn_id:
                return u
        return None

    def add_stroke(self, stroke_dict: Dict[str, Any]) -> None:
        self.strokes.append(stroke_dict)
        if len(self.strokes) > config.MAX_STROKES_HISTORY:
            # Drop older strokes to conserve memory
            self.strokes.pop(0)

    def clear_strokes(self) -> None:
        self.strokes.clear()

    def add_chat(self, from_name: str, text: str, user_color: str) -> Dict[str, Any]:
        msg_obj = {
            "type": "chat",
            "from": from_name,
            "text": text,
            "color": user_color,
            "timestamp": time.time()
        }
        self.chat_history.append(msg_obj)
        if len(self.chat_history) > config.MAX_CHAT_HISTORY:
            self.chat_history.pop(0)
        return msg_obj

    def get_state(self) -> Dict[str, Any]:
        """Returns full room snapshot for new joiners."""
        return {
            "type": "room_state",
            "room": self.key,
            "max_users": self.max_users,
            "user_count": len(self.users),
            "users": [u.to_dict() for u in self.users.values()],
            "strokes": list(self.strokes),
            "chat": list(self.chat_history)
        }
