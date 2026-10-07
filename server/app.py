"""
Web Bridge and HTTP Server for Collaborative Canvas.
Serves static UI files (HTML, CSS, JS) and acts as an HTTP/SSE bridge
that translates browser events into raw TCP socket interactions
with the Python Socket Network Core.
"""
import os
import sys
import json
import socket
import logging
import threading
import urllib.parse
from http import HTTPStatus
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from typing import Dict, Optional

from server import config
from server.protocol import frame_message, StreamBuffer
from server.socket_server import SocketServer

logger = logging.getLogger("SockChat.WebBridge")

# Directory paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLIENT_DIR = os.path.join(BASE_DIR, "client")


class BridgeSession:
    """Represents a bridge session mapping a browser client to a raw TCP socket."""
    def __init__(self, session_id: str, sock: socket.socket):
        self.session_id = session_id
        self.sock = sock
        self.lock = threading.Lock()
        self.is_active = True

    def send(self, data: dict) -> bool:
        """Sends framed JSON message across the raw TCP socket."""
        if not self.is_active:
            return False
        with self.lock:
            try:
                self.sock.sendall(frame_message(data))
                return True
            except (socket.error, BrokenPipeError) as exc:
                logger.warning("Error forwarding action to TCP socket for %s: %s", self.session_id, exc)
                self.close()
                return False

    def close(self) -> None:
        """Closes the TCP socket to trigger disconnection on the TCP core."""
        with self.lock:
            if self.is_active:
                self.is_active = False
                try:
                    self.sock.shutdown(socket.SHUT_RDWR)
                except Exception:
                    pass
                try:
                    self.sock.close()
                except Exception:
                    pass


class BridgeRegistry:
    """Thread-safe registry of active browser-to-socket bridge sessions."""
    def __init__(self):
        self._lock = threading.RLock()
        self.sessions: Dict[str, BridgeSession] = {}

    def get_or_create(self, session_id: str) -> Optional[BridgeSession]:
        with self._lock:
            session = self.sessions.get(session_id)
            if session and session.is_active:
                return session

            # Create a new raw TCP connection to the Socket Core
            try:
                tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                tcp_sock.connect((config.TCP_HOST, config.TCP_PORT))
                session = BridgeSession(session_id, tcp_sock)
                self.sessions[session_id] = session
                logger.info("Established new TCP socket connection for browser session %s", session_id)
                return session
            except Exception as exc:
                logger.error("Failed to connect TCP socket for session %s: %s", session_id, exc)
                return None

    def get(self, session_id: str) -> Optional[BridgeSession]:
        with self._lock:
            session = self.sessions.get(session_id)
            if session and session.is_active:
                return session
            return None

    def remove(self, session_id: str) -> None:
        with self._lock:
            session = self.sessions.pop(session_id, None)
            if session:
                session.close()


registry = BridgeRegistry()


class WebBridgeHandler(SimpleHTTPRequestHandler):
    """HTTP request handler serving UI and bridging SSE/POST requests to raw TCP sockets."""

    def __init__(self, *args, **kwargs):
        # Serve client directory
        super().__init__(*args, directory=CLIENT_DIR, **kwargs)

    def log_message(self, format, *args):
        logger.debug("%s - - [%s] %s", self.address_string(), self.log_date_time_string(), format % args)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/api/stream":
            self._handle_sse_stream(parsed.query)
        elif path == "/api/health":
            self._send_json(HTTPStatus.OK, {"status": "ok", "service": "collaborative-canvas"})
        elif path == "/" or path == "/lobby":
            self.path = "/index.html"
            super().do_GET()
        elif path == "/room":
            self.path = "/room.html"
            super().do_GET()
        else:
            super().do_GET()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/api/action":
            self._handle_post_action()
        else:
            self.send_error(HTTPStatus.NOT_FOUND, "Endpoint not found")

    def _handle_sse_stream(self, query_string: str):
        """
        Maintains persistent Server-Sent Events (SSE) connection with browser.
        Reads newline-delimited JSON from the raw TCP socket and pushes events to browser.
        """
        params = urllib.parse.parse_qs(query_string)
        session_id = params.get("session_id", [None])[0]

        if not session_id:
            self.send_error(HTTPStatus.BAD_REQUEST, "Missing session_id query parameter")
            return

        session = registry.get_or_create(session_id)
        if not session:
            self.send_error(HTTPStatus.SERVICE_UNAVAILABLE, "Could not establish TCP socket core connection")
            return

        # Send SSE Headers
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

        # Send initial connection confirmation
        try:
            self._send_sse_event({"type": "bridge_connected", "session_id": session_id})
        except Exception:
            registry.remove(session_id)
            return

        stream_buffer = StreamBuffer(max_message_bytes=config.MAX_MESSAGE_BYTES)
        logger.info("SSE client stream started for session %s", session_id)

        try:
            while session.is_active:
                # Read from raw TCP socket
                try:
                    chunk = session.sock.recv(config.RECV_BUFFER_SIZE)
                except (socket.error, ConnectionResetError):
                    break

                if not chunk:
                    # TCP socket closed
                    break

                try:
                    messages = stream_buffer.feed(chunk)
                except Exception as exc:
                    logger.warning("Stream buffer error on session %s: %s", session_id, exc)
                    continue

                for msg in messages:
                    self._send_sse_event(msg)

        except (BrokenPipeError, ConnectionResetError):
            logger.info("Browser disconnected SSE stream for session %s", session_id)
        except Exception as exc:
            logger.debug("Exception in SSE stream for session %s: %s", session_id, exc)
        finally:
            logger.info("Closing bridge session and TCP socket for session %s", session_id)
            registry.remove(session_id)

    def _send_sse_event(self, data: dict) -> None:
        """Encodes dict to SSE format: data: <json>\n\n and writes to HTTP stream."""
        payload = f"data: {json.dumps(data)}\n\n".encode("utf-8")
        self.wfile.write(payload)
        self.wfile.flush()

    def _handle_post_action(self):
        """Receives JSON action from browser and transmits it into the session's TCP socket."""
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length <= 0 or content_length > config.MAX_MESSAGE_BYTES:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": "Invalid payload size"})
                return

            body = self.rfile.read(content_length).decode("utf-8")
            data = json.loads(body)
        except Exception as exc:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": f"Invalid JSON payload: {exc}"})
            return

        session_id = data.get("session_id")
        action = data.get("action")

        if not session_id or not isinstance(action, dict):
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "Missing session_id or action"})
            return

        session = registry.get(session_id)
        if not session:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "Session not active. Please reconnect SSE stream."})
            return

        success = session.send(action)
        if success:
            self._send_json(HTTPStatus.OK, {"status": "dispatched"})
        else:
            self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "Failed to transmit into TCP socket"})

    def _send_json(self, status: HTTPStatus, data: dict):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)


class ThreadingHTTPServerWithDaemons(ThreadingHTTPServer):
    daemon_threads = True


def run_server(web_host: str = config.WEB_HOST, web_port: int = config.WEB_PORT,
               tcp_host: str = config.TCP_HOST, tcp_port: int = config.TCP_PORT):
    """
    Launches the complete Collaborative Canvas application:
    1. Starts the Raw TCP Socket Server Core on (tcp_host, tcp_port)
    2. Starts the Web Bridge & UI HTTP Server on (web_host, web_port)
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )

    # 1. Start raw TCP Socket Core
    socket_server = SocketServer(host=tcp_host, port=tcp_port)
    socket_server.start(background=True)
    print(f"=== [1/2] TCP Socket Core running on {tcp_host}:{tcp_port} (AF_INET, SOCK_STREAM) ===")

    # 2. Start Web Bridge & HTTP Server
    httpd = ThreadingHTTPServerWithDaemons((web_host, web_port), WebBridgeHandler)
    print(f"=== [2/2] Web Bridge & UI running on http://{web_host}:{web_port} ===")
    print(f"--> Open http://localhost:{web_port} in your browser to start collaborating!")

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server...")
    finally:
        httpd.server_close()
        socket_server.stop()
        print("Server shutdown complete.")


if __name__ == "__main__":
    run_server()
