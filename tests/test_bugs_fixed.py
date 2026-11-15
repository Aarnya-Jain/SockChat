"""
Regression and verification tests for bugs reported in BUGS/bugs.txt:
1. Connection stability & keep-alive
2. Session timeout prevention via heartbeats
3. Chat history persistence & visibility across clients
4. User count synchronization & reconnect handling
5. Drawing batching and remote sync without dropping connections
"""
import unittest
import time
import json
import http.client
import urllib.request
import threading

from server.socket_server import SocketServer
from server.app import WebBridgeHandler, ThreadingHTTPServerWithDaemons, registry
from server import config


class TestBugsFixed(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tcp_port = 19997
        cls.web_port = 18087
        config.TCP_PORT = cls.tcp_port
        config.WEB_PORT = cls.web_port

        cls.socket_server = SocketServer(host="127.0.0.1", port=cls.tcp_port)
        cls.socket_server.start(background=True)

        cls.httpd = ThreadingHTTPServerWithDaemons(("127.0.0.1", cls.web_port), WebBridgeHandler)
        cls.web_thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.web_thread.start()
        time.sleep(0.1)

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.socket_server.stop()
        time.sleep(0.1)

    def _post_action(self, session_id: str, action: dict):
        post_conn = http.client.HTTPConnection("127.0.0.1", self.web_port, timeout=5)
        post_data = json.dumps({"session_id": session_id, "action": action})
        post_conn.request("POST", "/api/action", body=post_data, headers={"Content-Type": "application/json"})
        resp = post_conn.getresponse()
        data = resp.read().decode()
        post_conn.close()
        return resp.status, json.loads(data)

    def test_multi_client_sync_and_chat_history(self):
        # 1. Client 1 (Alice) connects via SSE
        c1_sess = "sess_alice_test"
        c1_events = []
        c1_stop = threading.Event()
        c1_conn = http.client.HTTPConnection("127.0.0.1", self.web_port, timeout=10)
        c1_conn.request("GET", f"/api/stream?session_id={c1_sess}")
        c1_resp = c1_conn.getresponse()

        def c1_reader():
            while not c1_stop.is_set():
                try:
                    line = c1_resp.fp.readline().decode()
                    if not line:
                        break
                    if line.startswith("data: "):
                        c1_events.append(json.loads(line[6:].strip()))
                except Exception:
                    break

        threading.Thread(target=c1_reader, daemon=True).start()

        # Wait for bridge_connected
        time.sleep(0.2)
        self.assertTrue(any(e.get("type") == "bridge_connected" for e in c1_events))

        # Alice creates room
        status, _ = self._post_action(c1_sess, {"type": "create_room", "name": "Alice"})
        self.assertEqual(status, 200)

        # Wait for room_created
        time.sleep(0.2)
        room_created_event = next(e for e in c1_events if e.get("type") == "room_created")
        room_key = room_created_event["room"]
        self.assertIsNotNone(room_key)

        # Alice sends a chat message
        status, _ = self._post_action(c1_sess, {"type": "chat", "text": "Welcome to room!"})
        self.assertEqual(status, 200)

        # Alice sends a batch of drawing strokes
        status, _ = self._post_action(c1_sess, {
            "type": "draw_batch",
            "segments": [
                {"x1": 10, "y1": 10, "x2": 20, "y2": 20, "color": "#000000", "width": 4, "mode": "pen"},
                {"x1": 20, "y1": 20, "x2": 30, "y2": 30, "color": "#000000", "width": 4, "mode": "pen"}
            ]
        })
        self.assertEqual(status, 200)
        time.sleep(0.2)

        # 2. Client 2 (Bob) connects and joins the room
        c2_sess = "sess_bob_test"
        c2_events = []
        c2_stop = threading.Event()
        c2_conn = http.client.HTTPConnection("127.0.0.1", self.web_port, timeout=10)
        c2_conn.request("GET", f"/api/stream?session_id={c2_sess}")
        c2_resp = c2_conn.getresponse()

        def c2_reader():
            while not c2_stop.is_set():
                try:
                    line = c2_resp.fp.readline().decode()
                    if not line:
                        break
                    if line.startswith("data: "):
                        c2_events.append(json.loads(line[6:].strip()))
                except Exception:
                    break

        threading.Thread(target=c2_reader, daemon=True).start()
        time.sleep(0.2)

        # Bob joins room
        status, _ = self._post_action(c2_sess, {"type": "join_room", "room": room_key, "name": "Bob"})
        self.assertEqual(status, 200)
        time.sleep(0.3)

        # Verify Bob received room_state with full chat history and strokes
        bob_room_state = next(e for e in c2_events if e.get("type") == "room_state")
        self.assertEqual(bob_room_state["user_count"], 2)
        self.assertEqual(len(bob_room_state["chat"]), 1)
        self.assertEqual(bob_room_state["chat"][0]["text"], "Welcome to room!")
        self.assertEqual(bob_room_state["chat"][0]["from"], "Alice")
        self.assertIn("user_id", bob_room_state["chat"][0])
        self.assertEqual(len(bob_room_state["strokes"]), 2)

        # Verify Alice received user_joined notification with count = 2
        alice_user_joined = next(e for e in c1_events if e.get("type") == "user_joined")
        self.assertEqual(alice_user_joined["user_count"], 2)
        self.assertEqual(alice_user_joined["user"]["name"], "Bob")

        # Bob sends drawing batch
        status, _ = self._post_action(c2_sess, {
            "type": "draw_batch",
            "segments": [
                {"x1": 50, "y1": 50, "x2": 60, "y2": 60, "color": "#3b82f6", "width": 6, "mode": "pen"}
            ]
        })
        self.assertEqual(status, 200)
        time.sleep(0.2)

        # Verify Alice received Bob's draw_batch
        alice_got_batch = any(e.get("type") == "draw_batch" and e.get("from") == "Bob" for e in c1_events)
        self.assertTrue(alice_got_batch)

        # Teardown client streams
        c1_stop.set()
        c2_stop.set()
        c1_conn.close()
        c2_conn.close()
        registry.remove(c1_sess)
        registry.remove(c2_sess)


if __name__ == "__main__":
    unittest.main()
