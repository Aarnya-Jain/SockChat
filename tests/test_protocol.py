"""
Unit tests for application protocol framing, serialization, and schema validation.
"""
import unittest
from server.protocol import (
    frame_message, StreamBuffer, validate_client_message,
    ProtocolError, make_error_message
)


class TestProtocolFraming(unittest.TestCase):
    def test_frame_message(self):
        msg = {"type": "chat", "text": "hello world"}
        framed = frame_message(msg)
        self.assertTrue(framed.endswith(b"\n"))
        self.assertIn(b'"type":"chat"', framed)

    def test_stream_buffer_single_message(self):
        buf = StreamBuffer()
        raw = b'{"type":"ping"}\n'
        parsed = buf.feed(raw)
        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0]["type"], "ping")

    def test_stream_buffer_chunked_delivery(self):
        buf = StreamBuffer()
        # Feed partial chunk
        p1 = buf.feed(b'{"type":"ch')
        self.assertEqual(len(p1), 0)
        # Feed remainder with newline
        p2 = buf.feed(b'at","text":"hi"}\n')
        self.assertEqual(len(p2), 1)
        self.assertEqual(p2[0]["type"], "chat")
        self.assertEqual(p2[0]["text"], "hi")

    def test_stream_buffer_multiple_messages_in_one_chunk(self):
        buf = StreamBuffer()
        chunk = b'{"type":"ping"}\n{"type":"clear"}\n'
        parsed = buf.feed(chunk)
        self.assertEqual(len(parsed), 2)
        self.assertEqual(parsed[0]["type"], "ping")
        self.assertEqual(parsed[1]["type"], "clear")

    def test_stream_buffer_oversized_payload_protection(self):
        buf = StreamBuffer(max_message_bytes=50)
        oversized = b'A' * 100
        with self.assertRaises(ProtocolError) as ctx:
            buf.feed(oversized)
        self.assertEqual(ctx.exception.code, "FRAME_TOO_LARGE")


class TestProtocolValidation(unittest.TestCase):
    def test_validate_create_room(self):
        valid = {"type": "create_room", "name": "Alice"}
        res = validate_client_message(valid)
        self.assertEqual(res["type"], "create_room")
        self.assertEqual(res["name"], "Alice")

    def test_validate_create_room_empty_name(self):
        invalid = {"type": "create_room", "name": "   "}
        with self.assertRaises(ProtocolError) as ctx:
            validate_client_message(invalid)
        self.assertEqual(ctx.exception.code, "INVALID_NAME")

    def test_validate_join_room(self):
        valid = {"type": "join_room", "room": "A7K92", "name": "Bob"}
        res = validate_client_message(valid)
        self.assertEqual(res["room"], "A7K92")
        self.assertEqual(res["name"], "Bob")

    def test_validate_draw_segment(self):
        valid = {
            "type": "draw",
            "x1": 10.5,
            "y1": 20.0,
            "x2": 30.2,
            "y2": 40.8,
            "color": "#ff0000",
            "width": 4
        }
        res = validate_client_message(valid)
        self.assertEqual(res["type"], "draw")
        self.assertEqual(res["x1"], 10.5)
        self.assertEqual(res["color"], "#ff0000")
        self.assertEqual(res["width"], 4)

    def test_validate_draw_invalid_coords(self):
        invalid = {"type": "draw", "x1": "not-a-number", "y1": 0, "x2": 0, "y2": 0}
        with self.assertRaises(ProtocolError) as ctx:
            validate_client_message(invalid)
        self.assertEqual(ctx.exception.code, "INVALID_COORDINATES")

    def test_validate_chat_too_long(self):
        invalid = {"type": "chat", "text": "X" * 600}
        with self.assertRaises(ProtocolError) as ctx:
            validate_client_message(invalid)
        self.assertEqual(ctx.exception.code, "CHAT_TOO_LONG")

    def test_validate_unknown_type(self):
        invalid = {"type": "unknown_action"}
        with self.assertRaises(ProtocolError) as ctx:
            validate_client_message(invalid)
        self.assertEqual(ctx.exception.code, "UNKNOWN_TYPE")


if __name__ == "__main__":
    unittest.main()
