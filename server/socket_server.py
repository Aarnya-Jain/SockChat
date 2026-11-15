"""
Raw TCP Socket Core for Collaborative Canvas.
Demonstrably implements TCP networking via Python's socket library
(socket.socket(AF_INET, SOCK_STREAM)) with multi-threaded connection handling.
"""
import socket
import threading
import uuid
import logging
import sys
from typing import Optional
from server import config
from server.protocol import StreamBuffer, ProtocolError
from server.room_manager import RoomManager
from server.connection_manager import ConnectionManager
from server.router import MessageRouter

logger = logging.getLogger("SockChat.SocketServer")


class SocketServer:
    """
    Core TCP Socket Server handling direct client/bridge TCP connections.
    Explicitly uses socket.socket(socket.AF_INET, socket.SOCK_STREAM).
    """
    def __init__(self, host: str = config.TCP_HOST, port: int = config.TCP_PORT,
                 room_manager: Optional[RoomManager] = None,
                 connection_manager: Optional[ConnectionManager] = None):
        self.host = host
        self.port = port
        self.room_mgr = room_manager or RoomManager()
        self.conn_mgr = connection_manager or ConnectionManager()
        self.router = MessageRouter(self.room_mgr, self.conn_mgr)
        self.server_sock: Optional[socket.socket] = None
        self.is_running = False
        self._accept_thread: Optional[threading.Thread] = None

    def start(self, background: bool = True) -> None:
        """
        Binds and listens on the configured TCP host/port.
        Starts the accept loop either in background thread or blocking.
        """
        self.server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_sock.bind((self.host, self.port))
        self.server_sock.listen(128)
        self.server_sock.settimeout(0.5)
        self.is_running = True
        logger.info("TCP Socket Core listening on %s:%d (AF_INET, SOCK_STREAM)", self.host, self.port)

        if background:
            self._accept_thread = threading.Thread(target=self._accept_loop, daemon=True, name="TCPAcceptThread")
            self._accept_thread.start()
        else:
            self._accept_loop()

    def _accept_loop(self) -> None:
        """Continuously accepts incoming raw TCP connections."""
        while self.is_running and self.server_sock:
            try:
                client_sock, addr = self.server_sock.accept()
            except socket.timeout:
                continue
            except socket.error:
                if not self.is_running:
                    break
                logger.exception("Error in TCP accept loop")
                break

            conn_id = f"tcp_{uuid.uuid4().hex[:8]}"
            logger.info("Accepted raw TCP connection from %s:%s (id: %s)", addr[0], addr[1], conn_id)

            self.conn_mgr.register(conn_id, client_sock, addr)
            client_thread = threading.Thread(
                target=self._client_handler,
                args=(conn_id, client_sock, addr),
                daemon=True,
                name=f"ClientHandler-{conn_id}"
            )
            client_thread.start()

    def _client_handler(self, conn_id: str, client_sock: socket.socket, addr: tuple) -> None:
        """
        Dedicated thread handling an active TCP client stream.
        Buffers bytes, parses newline-delimited JSON, and feeds into MessageRouter.
        """
        stream_buf = StreamBuffer(max_message_bytes=config.MAX_MESSAGE_BYTES)
        try:
            # Periodic timeout allows checking self.is_running cleanly on shutdown
            client_sock.settimeout(1.0)

            while self.is_running:
                try:
                    chunk = client_sock.recv(config.RECV_BUFFER_SIZE)
                except socket.timeout:
                    continue
                except (socket.error, ConnectionResetError) as exc:
                    logger.debug("Socket read error on %s: %s", conn_id, exc)
                    break

                if not chunk:
                    # Peer closed socket cleanly (EOF)
                    logger.info("TCP client %s disconnected (EOF)", conn_id)
                    break

                try:
                    messages = stream_buf.feed(chunk)
                except ProtocolError as exc:
                    logger.warning("Protocol error reading from %s: %s", conn_id, exc)
                    self.conn_mgr.send_to(conn_id, {"type": "error", "code": exc.code, "message": exc.message})
                    continue

                for msg in messages:
                    self.router.handle_message(conn_id, msg)

        except Exception as exc:
            logger.exception("Unhandled error in client handler for %s: %s", conn_id, exc)
        finally:
            logger.info("Cleaning up connection %s", conn_id)
            self.router.handle_disconnect(conn_id)
            self.conn_mgr.unregister(conn_id)

    def stop(self) -> None:
        """Shuts down listener and active client sockets."""
        self.is_running = False
        if self.server_sock:
            try:
                self.server_sock.close()
            except Exception:
                pass
            self.server_sock = None
        self.conn_mgr.close_all()
        if self._accept_thread and self._accept_thread.is_alive():
            self._accept_thread.join(timeout=1.0)
        logger.info("TCP Socket Core stopped")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    srv = SocketServer()
    print(f"Starting TCP Socket Core on {config.TCP_HOST}:{config.TCP_PORT}...")
    try:
        srv.start(background=False)
    except KeyboardInterrupt:
        print("\nShutting down TCP Socket Core...")
        srv.stop()
