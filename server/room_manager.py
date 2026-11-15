"""
Room manager handling creation, lookup, membership, capacity, and cleanup.
Thread-safe using re-entrant locks.
"""
import secrets
import threading
from typing import Dict, Optional, Tuple, List
from server import config
from server.models import Room, User


class RoomManager:
    """Manages active rooms and enforces concurrency/capacity constraints."""
    def __init__(self):
        self._lock = threading.RLock()
        self.rooms: Dict[str, Room] = {}
        # Mapping from conn_id -> room_key for quick disconnect lookups
        self._conn_to_room: Dict[str, str] = {}

    def _generate_unique_key(self) -> str:
        """Generates an unguessable alphanumeric room key."""
        charset = config.ROOM_KEY_CHARSET
        k_len = config.ROOM_KEY_LENGTH
        for _ in range(100):
            key = "".join(secrets.choice(charset) for _ in range(k_len))
            if key not in self.rooms:
                return key
        # Fallback to longer key if collision space is tight
        return secrets.token_hex(4).upper()

    def create_room(self, max_users: int = config.DEFAULT_MAX_ROOM_USERS) -> Room:
        """Creates and registers a new room."""
        with self._lock:
            if len(self.rooms) >= config.MAX_ACTIVE_ROOMS:
                raise ValueError("MAX_ROOMS_REACHED")

            key = self._generate_unique_key()
            room = Room(key=key, max_users=max_users)
            self.rooms[key] = room
            return room

    def get_room(self, room_key: str) -> Optional[Room]:
        with self._lock:
            return self.rooms.get(room_key.upper())

    def join_room(self, room_key: str, name: str, conn_id: str) -> Tuple[Optional[Room], Optional[User], Optional[str]]:
        """
        Attempts to join an existing room.
        Returns (Room, User, None) on success, or (None, None, error_code) on failure.
        """
        room_key = room_key.upper()
        with self._lock:
            room = self.rooms.get(room_key)
            if not room:
                return None, None, "ROOM_NOT_FOUND"

            if room.is_full():
                return None, None, "ROOM_FULL"

            # Check if this connection was already registered in a room
            if conn_id in self._conn_to_room:
                prev_room_key = self._conn_to_room[conn_id]
                prev_room = self.rooms.get(prev_room_key)
                if prev_room:
                    user_to_remove = prev_room.get_user_by_conn(conn_id)
                    if user_to_remove:
                        prev_room.remove_user(user_to_remove.user_id)

            # If an existing user has the same display name in this room, clean up the stale session
            stale_users = [u for u in room.users.values() if u.name.lower() == name.lower()]
            for su in stale_users:
                room.remove_user(su.user_id)
                self._conn_to_room.pop(su.conn_id, None)

            user = User(name=name, conn_id=conn_id)
            if not room.add_user(user):
                return None, None, "ROOM_FULL"

            self._conn_to_room[conn_id] = room_key
            return room, user, None

    def leave_room(self, conn_id: str) -> Tuple[Optional[Room], Optional[User]]:
        """
        Removes the user associated with conn_id from their room.
        Cleans up empty rooms automatically.
        Returns (Room, User) if removed, else (None, None).
        """
        with self._lock:
            room_key = self._conn_to_room.pop(conn_id, None)
            if not room_key:
                return None, None

            room = self.rooms.get(room_key)
            if not room:
                return None, None

            user = room.get_user_by_conn(conn_id)
            if user:
                room.remove_user(user.user_id)

            # Cleanup room if empty
            if room.is_empty():
                self.rooms.pop(room_key, None)

            return room, user

    def get_room_for_conn(self, conn_id: str) -> Optional[Room]:
        with self._lock:
            room_key = self._conn_to_room.get(conn_id)
            if room_key:
                return self.rooms.get(room_key)
            return None

    def get_user_for_conn(self, conn_id: str) -> Optional[User]:
        with self._lock:
            room = self.get_room_for_conn(conn_id)
            if room:
                return room.get_user_by_conn(conn_id)
            return None
