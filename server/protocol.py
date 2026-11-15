"""
Protocol serialization, framing, and validation for Collaborative Canvas.
TCP provides a raw stream of bytes; this module provides newline-delimited
JSON framing and validates all message payloads against the system schema.
"""
import json
import re
from typing import List, Tuple, Optional, Any, Dict
from server import config


# Color hex regex pattern (e.g., #fff, #ffffff, #112233)
HEX_COLOR_PATTERN = re.compile(r"^#([A-Fa-f0-9]{3}|[A-Fa-f0-9]{6})$")


class ProtocolError(Exception):
    """Raised when framing or protocol validation fails."""
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def frame_message(data: Dict[str, Any]) -> bytes:
    """
    Serializes a dictionary to JSON and appends a newline delimiter.
    """
    json_bytes = json.dumps(data, separators=(",", ":")).encode("utf-8")
    return json_bytes + b"\n"


class StreamBuffer:
    """
    Maintains an in-memory byte buffer for a TCP socket connection.
    Splits raw byte streams on newline boundaries into complete JSON messages.
    """
    def __init__(self, max_message_bytes: int = config.MAX_MESSAGE_BYTES):
        self.buffer = bytearray()
        self.max_message_bytes = max_message_bytes

    def feed(self, chunk: bytes) -> List[Dict[str, Any]]:
        """
        Feeds incoming bytes from socket recv into buffer.
        Returns a list of parsed JSON message dicts.
        Raises ProtocolError if a frame exceeds max_message_bytes.
        """
        self.buffer.extend(chunk)
        messages: List[Dict[str, Any]] = []

        while True:
            newline_idx = self.buffer.find(b"\n")
            if newline_idx == -1:
                # No complete message boundary yet
                if len(self.buffer) > self.max_message_bytes:
                    self.buffer.clear()
                    raise ProtocolError("FRAME_TOO_LARGE", f"Message frame exceeded {self.max_message_bytes} bytes")
                break

            # Extract the complete line
            line = self.buffer[:newline_idx].strip()
            # Advance the buffer past the newline
            del self.buffer[:newline_idx + 1]

            if not line:
                continue

            try:
                decoded = line.decode("utf-8")
                parsed = json.loads(decoded)
                if not isinstance(parsed, dict):
                    raise ProtocolError("MALFORMED_JSON", "Payload must be a JSON object")
                messages.append(parsed)
            except UnicodeDecodeError as exc:
                raise ProtocolError("MALFORMED_ENCODING", "Invalid UTF-8 encoding in message") from exc
            except json.JSONDecodeError as exc:
                raise ProtocolError("MALFORMED_JSON", f"Malformed JSON: {exc.msg}") from exc

        return messages


def validate_client_message(msg: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validates client-to-server messages according to the protocol specification.
    Returns cleaned / sanitized message dictionary or raises ProtocolError.
    """
    if "type" not in msg or not isinstance(msg["type"], str):
        raise ProtocolError("MISSING_TYPE", "Message missing required string field 'type'")

    msg_type = msg["type"].strip()

    if msg_type == "create_room":
        name = _validate_name(msg.get("name"))
        return {"type": "create_room", "name": name}

    elif msg_type == "join_room":
        room = _validate_room_key(msg.get("room"))
        name = _validate_name(msg.get("name"))
        return {"type": "join_room", "room": room, "name": name}

    elif msg_type == "chat":
        text = msg.get("text")
        if not isinstance(text, str) or not text.strip():
            raise ProtocolError("INVALID_CHAT", "Chat text must be a non-empty string")
        text = text.strip()
        if len(text) > config.MAX_CHAT_LENGTH:
            raise ProtocolError("CHAT_TOO_LONG", f"Chat exceeds maximum length of {config.MAX_CHAT_LENGTH}")
        return {"type": "chat", "text": text}

    elif msg_type == "draw":
        return _validate_draw_segment(msg)

    elif msg_type == "draw_batch":
        raw_segments = msg.get("segments")
        if not isinstance(raw_segments, list) or not raw_segments:
            raise ProtocolError("INVALID_DRAW_BATCH", "Batch segments must be a non-empty list")
        if len(raw_segments) > 200:
            raw_segments = raw_segments[:200]
        cleaned_segments = []
        for seg in raw_segments:
            if isinstance(seg, dict):
                cleaned_segments.append(_validate_draw_segment(seg))
        if not cleaned_segments:
            raise ProtocolError("INVALID_DRAW_BATCH", "No valid segments in draw_batch")
        return {
            "type": "draw_batch",
            "segments": cleaned_segments
        }

    elif msg_type == "clear":
        return {"type": "clear"}

    elif msg_type == "leave":
        return {"type": "leave"}

    elif msg_type == "ping":
        return {"type": "ping"}

    else:
        raise ProtocolError("UNKNOWN_TYPE", f"Unknown message type '{msg_type}'")


def _validate_draw_segment(msg: Dict[str, Any]) -> Dict[str, Any]:
    for coord in ("x1", "y1", "x2", "y2"):
        val = msg.get(coord)
        if not isinstance(val, (int, float)):
            raise ProtocolError("INVALID_COORDINATES", f"Coordinate '{coord}' must be a number")

    color = msg.get("color", "#000000")
    if not isinstance(color, str) or not HEX_COLOR_PATTERN.match(color):
        color = "#000000"

    width = msg.get("width", 3)
    if not isinstance(width, (int, float)) or not (1 <= width <= 64):
        width = 3

    mode = msg.get("mode", "pen")
    if mode not in ("pen", "eraser"):
        mode = "pen"

    return {
        "type": "draw",
        "x1": round(float(msg["x1"]), 2),
        "y1": round(float(msg["y1"]), 2),
        "x2": round(float(msg["x2"]), 2),
        "y2": round(float(msg["y2"]), 2),
        "color": color,
        "width": int(width),
        "mode": mode
    }


def _validate_name(name: Any) -> str:
    if not isinstance(name, str) or not name.strip():
        raise ProtocolError("INVALID_NAME", "Display name cannot be empty")
    cleaned = name.strip()
    if len(cleaned) > config.MAX_NAME_LENGTH:
        raise ProtocolError("NAME_TOO_LONG", f"Display name exceeds {config.MAX_NAME_LENGTH} characters")
    return cleaned


def _validate_room_key(room: Any) -> str:
    if not isinstance(room, str) or not room.strip():
        raise ProtocolError("INVALID_ROOM_KEY", "Room key cannot be empty")
    cleaned = room.strip().upper()
    if not cleaned.isalnum() or len(cleaned) > 16:
        raise ProtocolError("INVALID_ROOM_KEY", "Room key must be alphanumeric")
    return cleaned


def make_error_message(code: str, message: str) -> Dict[str, Any]:
    """Helper to format standardized error message."""
    return {"type": "error", "code": code, "message": message}
