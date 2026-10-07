"""
Unit tests for cross-room isolation and broadcast encapsulation.
Verifies that drawing and chat events in Room A never leak to Room B.
"""
import unittest
from typing import Dict, List, Any
from server.room_manager import RoomManager
from server.router import MessageRouter


class MockConnectionManager:
    """Mock connection manager tracking sent messages per conn_id."""
    def __init__(self):
        self.sent_messages: Dict[str, List[Dict[str, Any]]] = {}

    def send_to(self, conn_id: str, data: Dict[str, Any]) -> bool:
        if conn_id not in self.sent_messages:
            self.sent_messages[conn_id] = []
        self.sent_messages[conn_id].append(data)
        return True

    def broadcast(self, conn_ids: List[str], data: Dict[str, Any], exclude_conn_id: str = None) -> None:
        for cid in conn_ids:
            if exclude_conn_id and cid == exclude_conn_id:
                continue
            self.send_to(cid, data)


class TestRoomIsolation(unittest.TestCase):
    def setUp(self):
        self.room_mgr = RoomManager()
        self.conn_mgr = MockConnectionManager()
        self.router = MessageRouter(self.room_mgr, self.conn_mgr)

        # Create Room A with Alice (c1) and Bob (c2)
        self.router.handle_message("c1", {"type": "create_room", "name": "Alice"})
        # Retrieve room A key from sent message
        room_a_key = self.conn_mgr.sent_messages["c1"][0]["room"]
        self.room_a_key = room_a_key
        self.router.handle_message("c2", {"type": "join_room", "room": room_a_key, "name": "Bob"})

        # Create Room B with Charlie (c3)
        self.router.handle_message("c3", {"type": "create_room", "name": "Charlie"})
        self.room_b_key = self.conn_mgr.sent_messages["c3"][0]["room"]

        # Clear message queues for isolated testing
        self.conn_mgr.sent_messages.clear()

    def test_drawing_isolation(self):
        # Alice draws in Room A
        stroke = {
            "type": "draw",
            "x1": 10, "y1": 20, "x2": 30, "y2": 40,
            "color": "#112233", "width": 5, "mode": "pen"
        }
        self.router.handle_message("c1", stroke)

        # Bob (c2, in Room A) should receive the drawing event
        bob_msgs = self.conn_mgr.sent_messages.get("c2", [])
        self.assertTrue(any(m.get("type") == "draw" and m.get("color") == "#112233" for m in bob_msgs))

        # Charlie (c3, in Room B) must NOT receive the drawing event
        charlie_msgs = self.conn_mgr.sent_messages.get("c3", [])
        self.assertFalse(any(m.get("type") == "draw" for m in charlie_msgs))

    def test_chat_isolation(self):
        # Alice chats in Room A
        self.router.handle_message("c1", {"type": "chat", "text": "Secret meeting in Room A"})

        # Bob should receive the chat
        bob_msgs = self.conn_mgr.sent_messages.get("c2", [])
        self.assertTrue(any(m.get("type") == "chat" and "Secret meeting" in m.get("text", "") for m in bob_msgs))

        # Charlie in Room B must NOT receive it
        charlie_msgs = self.conn_mgr.sent_messages.get("c3", [])
        self.assertFalse(any(m.get("type") == "chat" for m in charlie_msgs))

    def test_clear_canvas_isolation(self):
        # Add stroke to Room B first
        self.router.handle_message("c3", {"type": "draw", "x1": 1, "y1": 1, "x2": 2, "y2": 2, "color": "#000", "width": 2})
        room_b = self.room_mgr.get_room(self.room_b_key)
        self.assertEqual(len(room_b.strokes), 1)

        # Alice clears Room A
        self.router.handle_message("c1", {"type": "clear"})

        # Room B strokes must still remain intact
        self.assertEqual(len(room_b.strokes), 1)

    def test_malformed_message_handling(self):
        # Send garbage message
        self.router.handle_message("c1", {"invalid_garbage": True})

        # Alice should get an error message back
        alice_msgs = self.conn_mgr.sent_messages.get("c1", [])
        self.assertTrue(any(m.get("type") == "error" for m in alice_msgs))

        # Other users shouldn't receive anything or crash
        bob_msgs = self.conn_mgr.sent_messages.get("c2", [])
        self.assertEqual(len(bob_msgs), 0)


if __name__ == "__main__":
    unittest.main()
