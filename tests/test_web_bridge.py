"""
Integration test for the Web Bridge HTTP & SSE server.
Verifies HTTP endpoints, static assets, and SSE to raw TCP socket translation.
"""
import unittest
import time
import json
import urllib.request
import urllib.error
from http.server import ThreadingHTTPServer
import threading

from server.socket_server import SocketServer
from server.app import WebBridgeHandler, ThreadingHTTPServerWithDaemons, registry
from server import config


class TestWebBridge(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Configure test ports
        cls.tcp_port = 19998
        cls.web_port = 18088

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

    def test_health_endpoint(self):
        url = f"http://127.0.0.1:{self.web_port}/api/health"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode())
            self.assertEqual(data["status"], "ok")

    def test_static_routes(self):
        # Index lobby
        url = f"http://127.0.0.1:{self.web_port}/"
        with urllib.request.urlopen(url) as resp:
            self.assertEqual(resp.status, 200)
            body = resp.read().decode()
            self.assertIn("Collaborative Canvas", body)

        # Room page
        url = f"http://127.0.0.1:{self.web_port}/room"
        with urllib.request.urlopen(url) as resp:
            self.assertEqual(resp.status, 200)
            body = resp.read().decode()
            self.assertIn("canvas", body.lower())

        # Style CSS
        url = f"http://127.0.0.1:{self.web_port}/css/style.css"
        with urllib.request.urlopen(url) as resp:
            self.assertEqual(resp.status, 200)
            self.assertEqual(resp.headers.get_content_type(), "text/css")

    def test_sse_bridge_and_post_action(self):
        import http.client
        session_id = "test_sess_123"

        # Connect to SSE stream via HTTPConnection
        conn = http.client.HTTPConnection("127.0.0.1", self.web_port, timeout=5)
        conn.request("GET", f"/api/stream?session_id={session_id}")
        resp = conn.getresponse()
        self.assertEqual(resp.status, 200)

        received_events = []
        stop_stream = threading.Event()

        def stream_reader():
            while not stop_stream.is_set():
                try:
                    line = resp.fp.readline().decode()
                    if not line:
                        break
                    if line.startswith("data: "):
                        data_str = line[6:].strip()
                        if data_str:
                            received_events.append(json.loads(data_str))
                except Exception:
                    break

        t = threading.Thread(target=stream_reader, daemon=True)
        t.start()

        # Wait for bridge_connected event
        start = time.time()
        while time.time() - start < 2.0:
            if any(e.get("type") == "bridge_connected" for e in received_events):
                break
            time.sleep(0.05)

        self.assertTrue(any(e.get("type") == "bridge_connected" for e in received_events))

        # Send POST action to create room via separate connection
        post_conn = http.client.HTTPConnection("127.0.0.1", self.web_port, timeout=5)
        post_data = json.dumps({
            "session_id": session_id,
            "action": {"type": "create_room", "name": "Tester"}
        })
        post_conn.request("POST", "/api/action", body=post_data, headers={"Content-Type": "application/json"})
        post_resp = post_conn.getresponse()
        self.assertEqual(post_resp.status, 200)
        res_json = json.loads(post_resp.read().decode())
        self.assertEqual(res_json["status"], "dispatched")
        post_conn.close()

        # Verify that SSE stream receives room_created and room_state from TCP core
        start = time.time()
        while time.time() - start < 2.0:
            if any(e.get("type") == "room_created" for e in received_events):
                break
            time.sleep(0.05)

        self.assertTrue(any(e.get("type") == "room_created" for e in received_events))
        self.assertTrue(any(e.get("type") == "room_state" for e in received_events))

        stop_stream.set()
        conn.close()
        registry.remove(session_id)
        t.join(timeout=1.0)


if __name__ == "__main__":
    unittest.main()
