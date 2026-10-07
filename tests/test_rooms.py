"""
Unit tests for RoomManager lifecycle, membership, and cleanup.
"""
import unittest
from server.room_manager import RoomManager


class TestRoomManager(unittest.TestCase):
    def setUp(self):
        self.mgr = RoomManager()

    def test_create_room_generates_unique_key(self):
        room1 = self.mgr.create_room()
        room2 = self.mgr.create_room()
        self.assertIsNotNone(room1.key)
        self.assertIsNotNone(room2.key)
        self.assertNotEqual(room1.key, room2.key)
        self.assertEqual(len(room1.key), 5)

    def test_join_valid_room(self):
        room = self.mgr.create_room()
        joined_room, user, err = self.mgr.join_room(room.key, "Alice", "conn_1")
        self.assertIsNone(err)
        self.assertIsNotNone(joined_room)
        self.assertIsNotNone(user)
        self.assertEqual(user.name, "Alice")
        self.assertEqual(len(room.users), 1)

    def test_join_invalid_room(self):
        joined_room, user, err = self.mgr.join_room("NONEXISTENT", "Bob", "conn_2")
        self.assertEqual(err, "ROOM_NOT_FOUND")
        self.assertIsNone(joined_room)
        self.assertIsNone(user)

    def test_leave_room_and_cleanup(self):
        room = self.mgr.create_room()
        room_key = room.key
        self.mgr.join_room(room_key, "Alice", "conn_1")
        self.assertEqual(len(self.mgr.rooms), 1)

        left_room, left_user = self.mgr.leave_room("conn_1")
        self.assertIsNotNone(left_room)
        self.assertEqual(left_user.name, "Alice")
        # Empty room should be cleaned up automatically
        self.assertNotIn(room_key, self.mgr.rooms)
        self.assertEqual(len(self.mgr.rooms), 0)

    def test_multiple_users_in_room(self):
        room = self.mgr.create_room()
        self.mgr.join_room(room.key, "Alice", "conn_1")
        self.mgr.join_room(room.key, "Bob", "conn_2")
        self.assertEqual(len(room.users), 2)

        # Alice leaves, Bob remains
        self.mgr.leave_room("conn_1")
        self.assertEqual(len(room.users), 1)
        self.assertIn(room.key, self.mgr.rooms)

        # Bob leaves, room destroyed
        self.mgr.leave_room("conn_2")
        self.assertNotIn(room.key, self.mgr.rooms)


if __name__ == "__main__":
    unittest.main()
