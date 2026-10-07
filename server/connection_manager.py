"""
Manages active raw TCP socket connections.
Provides thread-safe sending, tracking, and disconnection handling.
"""
import socket
import threading
import logging
from typing import Dict, Optional, List, Any
from server.protocol import frame_message

logger = logging.getLogger("SockChat.ConnectionManager")


class Connection:
    """Wraps a raw TCP client socket with locking and metadata."""
    def __init__(self, conn_id: str, sock: socket.socket, addr: tuple):
        self.conn_id = conn_id
        self.sock = sock
        self.addr = addr
        self.lock = threading.Lock()
        self.is_closed = False

    def send(self, data: Dict[str, Any]) -> bool:
        """Serializes and sends a message framed by newline."""
        if self.is_closed:
            return False
        raw_bytes = frame_message(data)
        return self.send_bytes(raw_bytes)

    def send_bytes(self, raw_bytes: bytes) -> bool:
        """Thread-safe transmission of raw bytes over socket."""
        if self.is_closed:
            return False
        with self.lock:
            try:
                self.sock.sendall(raw_bytes)
                return True
            except (socket.error, BrokenPipeError, ConnectionResetError) as exc:
                logger.warning("Socket error sending to %s: %s", self.conn_id, exc)
                self.close()
                return False

    def close(self) -> None:
        """Safely closes the underlying socket."""
        with self.lock:
            if not self.is_closed:
                self.is_closed = True
                try:
                    self.sock.shutdown(socket.SHUT_RDWR)
                except Exception:
                    pass
                try:
                    self.sock.close()
                except Exception:
                    pass


class ConnectionManager:
    """Thread-safe registry of active TCP client connections."""
    def __init__(self):
        self._lock = threading.RLock()
        self.connections: Dict[str, Connection] = {}

    def register(self, conn_id: str, sock: socket.socket, addr: tuple) -> Connection:
        with self._lock:
            conn = Connection(conn_id, sock, addr)
            self.connections[conn_id] = conn
            return conn

    def unregister(self, conn_id: str) -> Optional[Connection]:
        with self._lock:
            conn = self.connections.pop(conn_id, None)
            if conn:
                conn.close()
            return conn

    def get(self, conn_id: str) -> Optional[Connection]:
        with self._lock:
            return self.connections.get(conn_id)

    def send_to(self, conn_id: str, data: Dict[str, Any]) -> bool:
        conn = self.get(conn_id)
        if conn:
            return conn.send(data)
        return False

    def broadcast(self, conn_ids: List[str], data: Dict[str, Any], exclude_conn_id: Optional[str] = None) -> None:
        """Broadcasts a framed message to all specified connection IDs."""
        raw_bytes = frame_message(data)
        for cid in conn_ids:
            if exclude_conn_id and cid == exclude_conn_id:
                continue
            conn = self.get(cid)
            if conn:
                conn.send_bytes(raw_bytes)

    def close_all(self) -> None:
        with self._lock:
            for conn in list(self.connections.values()):
                conn.close()
            self.connections.clear()
