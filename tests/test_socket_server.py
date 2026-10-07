"""
Integration test for raw TCP Socket Core over actual network loopback sockets.
Verifies AF_INET / SOCK_STREAM handshake, newline-delimited framing, and broadcast.
"""
import socket
import time
import unittest
from server.socket_server import SocketServer
from server.protocol import frame_message, StreamBuffer


class TestSocketServerE2E(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Bind to a dedicated test port
        cls.test_port = 19999
        cls.server = SocketServer(host="127.0.0.1", port=cls.test_port)
        cls.server.start(background=True)
        time.sleep(0.1)

    @classmethod
    def tearDownClass(cls):
        cls.server.stop()
        time.sleep(0.1)

    def _create_client_socket(self) -> socket.socket:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(2.0)
        s.connect(("127.0.0.1", self.test_port))
        return s

    def test_e2e_create_and_join_room_over_tcp(self):
        c1 = self._create_client_socket()
        buf1 = StreamBuffer()

        # Alice creates a room
        c1.sendall(frame_message({"type": "create_room", "name": "Alice"}))
        
        # Read until we get room_created
        room_key = None
        while not room_key:
            chunk = c1.recv(1024)
            msgs = buf1.feed(chunk)
            for m in msgs:
                if m.get("type") == "room_created":
                    room_key = m.get("room")
                    break

        self.assertIsNotNone(room_key)

        # Bob connects and joins the room over a separate TCP socket
        c2 = self._create_client_socket()
        buf2 = StreamBuffer()
        c2.sendall(frame_message({"type": "join_room", "room": room_key, "name": "Bob"}))

        # Check Bob receives joined_success and room_state
        joined = False
        while not joined:
            chunk = c2.recv(1024)
            msgs = buf2.feed(chunk)
            for m in msgs:
                if m.get("type") == "joined_success":
                    joined = True
                    break

        self.assertTrue(joined)

        # Check Alice gets user_joined notification
        alice_got_notification = False
        start = time.time()
        while time.time() - start < 2.0:
            try:
                chunk = c1.recv(1024)
                msgs = buf1.feed(chunk)
                for m in msgs:
                    if m.get("type") == "user_joined" and m.get("user", {}).get("name") == "Bob":
                        alice_got_notification = True
                        break
            except socket.timeout:
                pass
            if alice_got_notification:
                break

        self.assertTrue(alice_got_notification)

        # Bob sends a chat message
        c2.sendall(frame_message({"type": "chat", "text": "Hello Alice!"}))

        # Alice receives chat over her TCP socket
        alice_got_chat = False
        start = time.time()
        while time.time() - start < 2.0:
            try:
                chunk = c1.recv(1024)
                msgs = buf1.feed(chunk)
                for m in msgs:
                    if m.get("type") == "chat" and m.get("text") == "Hello Alice!":
                        alice_got_chat = True
                        break
            except socket.timeout:
                pass
            if alice_got_chat:
                break

        self.assertTrue(alice_got_chat)

        # Teardown sockets
        c1.close()
        c2.close()


if __name__ == "__main__":
    unittest.main()
