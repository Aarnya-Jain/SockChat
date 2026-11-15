"""
Message routing and room-isolated broadcasting for Collaborative Canvas.
Validates input, updates room state, and disseminates events exclusively
to sockets in the designated room.
"""
import logging
from typing import Dict, Any, Optional
from server.protocol import validate_client_message, make_error_message, ProtocolError
from server.room_manager import RoomManager
from server.connection_manager import ConnectionManager

logger = logging.getLogger("SockChat.Router")


class MessageRouter:
    """Dispatches application actions and enforces room boundary isolation."""
    def __init__(self, room_manager: RoomManager, connection_manager: ConnectionManager):
        self.room_mgr = room_manager
        self.conn_mgr = connection_manager

    def handle_message(self, conn_id: str, raw_msg: Dict[str, Any]) -> None:
        """Validates and routes an incoming JSON message from a client socket."""
        try:
            msg = validate_client_message(raw_msg)
        except ProtocolError as exc:
            logger.warning("Protocol validation error from %s: %s (%s)", conn_id, exc.message, exc.code)
            self.conn_mgr.send_to(conn_id, make_error_message(exc.code, exc.message))
            return
        except Exception as exc:
            logger.exception("Unexpected error validating message from %s: %s", conn_id, exc)
            self.conn_mgr.send_to(conn_id, make_error_message("INTERNAL_ERROR", "Internal processing error"))
            return

        msg_type = msg["type"]

        if msg_type == "create_room":
            self._handle_create_room(conn_id, msg)
        elif msg_type == "join_room":
            self._handle_join_room(conn_id, msg)
        elif msg_type == "chat":
            self._handle_chat(conn_id, msg)
        elif msg_type == "draw":
            self._handle_draw(conn_id, msg)
        elif msg_type == "draw_batch":
            self._handle_draw_batch(conn_id, msg)
        elif msg_type == "clear":
            self._handle_clear(conn_id, msg)
        elif msg_type == "leave":
            self._handle_leave(conn_id, msg)
        elif msg_type == "ping":
            self.conn_mgr.send_to(conn_id, {"type": "pong"})

    def _handle_create_room(self, conn_id: str, msg: Dict[str, Any]) -> None:
        name = msg["name"]
        try:
            room = self.room_mgr.create_room()
        except ValueError:
            self.conn_mgr.send_to(conn_id, make_error_message("MAX_ROOMS", "Server room capacity reached"))
            return

        room, user, err = self.room_mgr.join_room(room.key, name, conn_id)
        if err or not room or not user:
            self.conn_mgr.send_to(conn_id, make_error_message(err or "JOIN_FAILED", "Failed to initialize created room"))
            return

        logger.info("Room created: %s by user '%s' (%s)", room.key, user.name, conn_id)
        # Notify creator with room key and their identity
        self.conn_mgr.send_to(conn_id, {
            "type": "room_created",
            "room": room.key,
            "user": user.to_dict()
        })
        # Send full initial room state
        self.conn_mgr.send_to(conn_id, room.get_state())

    def _handle_join_room(self, conn_id: str, msg: Dict[str, Any]) -> None:
        room_key = msg["room"]
        name = msg["name"]

        room, user, err = self.room_mgr.join_room(room_key, name, conn_id)
        if err or not room or not user:
            logger.info("Join failed for %s to %s: %s", conn_id, room_key, err)
            self.conn_mgr.send_to(conn_id, make_error_message(err or "JOIN_FAILED", f"Could not join room {room_key}"))
            return

        logger.info("User '%s' joined room %s (%s)", user.name, room.key, conn_id)

        # Send full state to newly joined user (including strokes and chat history)
        self.conn_mgr.send_to(conn_id, {
            "type": "joined_success",
            "room": room.key,
            "user": user.to_dict()
        })
        self.conn_mgr.send_to(conn_id, room.get_state())

        # Broadcast user_joined event to all OTHER members in this room
        room_conn_ids = [u.conn_id for u in room.users.values()]
        self.conn_mgr.broadcast(
            room_conn_ids,
            {
                "type": "user_joined",
                "room": room.key,
                "user": user.to_dict(),
                "user_count": len(room.users),
                "users": [u.to_dict() for u in room.users.values()]
            },
            exclude_conn_id=conn_id
        )

    def _handle_chat(self, conn_id: str, msg: Dict[str, Any]) -> None:
        room = self.room_mgr.get_room_for_conn(conn_id)
        user = self.room_mgr.get_user_for_conn(conn_id)
        if not room or not user:
            self.conn_mgr.send_to(conn_id, make_error_message("NOT_IN_ROOM", "Must be inside a room to chat"))
            return

        text = msg["text"]
        chat_entry = room.add_chat(user.name, text, user.color, user.user_id)
        chat_payload = {
            "type": "chat",
            "room": room.key,
            "from": user.name,
            "user_id": user.user_id,
            "color": user.color,
            "text": text,
            "timestamp": chat_entry["timestamp"]
        }

        # Broadcast chat to all members of THIS room ONLY
        room_conn_ids = [u.conn_id for u in room.users.values()]
        self.conn_mgr.broadcast(room_conn_ids, chat_payload)

    def _handle_draw(self, conn_id: str, msg: Dict[str, Any]) -> None:
        room = self.room_mgr.get_room_for_conn(conn_id)
        user = self.room_mgr.get_user_for_conn(conn_id)
        if not room or not user:
            self.conn_mgr.send_to(conn_id, make_error_message("NOT_IN_ROOM", "Must be inside a room to draw"))
            return

        stroke = {
            "type": "draw",
            "x1": msg["x1"],
            "y1": msg["y1"],
            "x2": msg["x2"],
            "y2": msg["y2"],
            "color": msg["color"],
            "width": msg["width"],
            "mode": msg["mode"],
            "from": user.name,
            "user_id": user.user_id
        }
        room.add_stroke(stroke)

        # Broadcast drawing stroke to all other members in the room
        room_conn_ids = [u.conn_id for u in room.users.values()]
        self.conn_mgr.broadcast(room_conn_ids, stroke, exclude_conn_id=conn_id)

    def _handle_draw_batch(self, conn_id: str, msg: Dict[str, Any]) -> None:
        room = self.room_mgr.get_room_for_conn(conn_id)
        user = self.room_mgr.get_user_for_conn(conn_id)
        if not room or not user:
            self.conn_mgr.send_to(conn_id, make_error_message("NOT_IN_ROOM", "Must be inside a room to draw"))
            return

        segments = msg.get("segments", [])
        if not segments:
            return

        processed_segments = []
        for s in segments:
            stroke = {
                "type": "draw",
                "x1": s["x1"],
                "y1": s["y1"],
                "x2": s["x2"],
                "y2": s["y2"],
                "color": s["color"],
                "width": s["width"],
                "mode": s["mode"],
                "from": user.name,
                "user_id": user.user_id
            }
            room.add_stroke(stroke)
            processed_segments.append(stroke)

        batch_payload = {
            "type": "draw_batch",
            "from": user.name,
            "user_id": user.user_id,
            "segments": processed_segments
        }

        room_conn_ids = [u.conn_id for u in room.users.values()]
        self.conn_mgr.broadcast(room_conn_ids, batch_payload, exclude_conn_id=conn_id)

    def _handle_clear(self, conn_id: str, msg: Dict[str, Any]) -> None:
        room = self.room_mgr.get_room_for_conn(conn_id)
        user = self.room_mgr.get_user_for_conn(conn_id)
        if not room or not user:
            self.conn_mgr.send_to(conn_id, make_error_message("NOT_IN_ROOM", "Must be inside a room to clear canvas"))
            return

        room.clear_strokes()
        clear_payload = {
            "type": "clear",
            "room": room.key,
            "from": user.name,
            "user_id": user.user_id
        }

        # Broadcast clear to ALL members in this room (including sender to confirm clear)
        room_conn_ids = [u.conn_id for u in room.users.values()]
        self.conn_mgr.broadcast(room_conn_ids, clear_payload)

    def _handle_leave(self, conn_id: str, msg: Dict[str, Any]) -> None:
        self.handle_disconnect(conn_id)

    def handle_disconnect(self, conn_id: str) -> None:
        """Handles client disconnection, room cleanup, and user_left broadcast."""
        room, user = self.room_mgr.leave_room(conn_id)
        if room and user:
            logger.info("User '%s' left room %s", user.name, room.key)
            if not room.is_empty():
                room_conn_ids = [u.conn_id for u in room.users.values()]
                self.conn_mgr.broadcast(
                    room_conn_ids,
                    {
                        "type": "user_left",
                        "room": room.key,
                        "name": user.name,
                        "user_id": user.user_id,
                        "user_count": len(room.users),
                        "users": [u.to_dict() for u in room.users.values()]
                    }
                )
            else:
                logger.info("Room %s is now empty and cleaned up", room.key)
