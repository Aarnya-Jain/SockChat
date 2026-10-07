"""
Unit tests for room capacity limits and backpressure enforcement.
"""
import unittest
from server.room_manager import RoomManager


class TestRoomCapacity(unittest.TestCase):
    def setUp(self):
        self.mgr = RoomManager()

    def test_room_capacity_enforced(self):
        # Create room with max 3 users
        room = self.mgr.create_room(max_users=3)
        self.assertEqual(room.max_users, 3)

        # Join 3 users
        for i in range(1, 4):
            r, u, err = self.mgr.join_room(room.key, f"User_{i}", f"conn_{i}")
            self.assertIsNone(err)
            self.assertIsNotNone(u)

        self.assertTrue(room.is_full())

        # Attempt to join 4th user
        r4, u4, err4 = self.mgr.join_room(room.key, "User_4", "conn_4")
        self.assertEqual(err4, "ROOM_FULL")
        self.assertIsNone(u4)
        self.assertEqual(len(room.users), 3)

    def test_room_allows_join_after_user_leaves(self):
        room = self.mgr.create_room(max_users=2)
        self.mgr.join_room(room.key, "Alice", "conn_1")
        self.mgr.join_room(room.key, "Bob", "conn_2")
        self.assertTrue(room.is_full())

        # Charlie cannot join
        _, _, err = self.mgr.join_room(room.key, "Charlie", "conn_3")
        self.assertEqual(err, "ROOM_FULL")

        # Alice leaves
        self.mgr.leave_room("conn_1")
        self.assertFalse(room.is_full())

        # Charlie can now join
        r, u, err = self.mgr.join_room(room.key, "Charlie", "conn_3")
        self.assertIsNone(err)
        self.assertIsNotNone(u)
        self.assertEqual(len(room.users), 2)


if __name__ == "__main__":
    unittest.main()
