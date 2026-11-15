"""
Configuration settings for Collaborative Canvas & Chat.
Centralizes network addresses, room limits, and protocol constraints.
"""
import os

# Network settings for Raw TCP Socket Core
TCP_HOST = os.environ.get("TCP_HOST", "127.0.0.1")
TCP_PORT = int(os.environ.get("TCP_PORT", 9999))

# Network settings for Web HTTP / SSE Bridge
WEB_HOST = os.environ.get("WEB_HOST", "0.0.0.0")
WEB_PORT = int(os.environ.get("WEB_PORT", 8080))

# Room constraints
DEFAULT_MAX_ROOM_USERS = 4
MAX_ACTIVE_ROOMS = 100
ROOM_KEY_LENGTH = 5
ROOM_KEY_CHARSET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # Disambiguated alphanumerics

# Protocol and message safety constraints
MAX_MESSAGE_BYTES = 64 * 1024  # 64 KB maximum single message frame
MAX_CHAT_LENGTH = 500          # Maximum characters per chat message
MAX_NAME_LENGTH = 32           # Maximum username length
MAX_STROKES_HISTORY = 2000     # Maximum strokes preserved for canvas reconstruction
MAX_CHAT_HISTORY = 100         # Maximum chat messages preserved for room history
SOCKET_TIMEOUT = 300.0         # Socket inactivity timeout in seconds (5 minutes)
HEARTBEAT_INTERVAL = 15.0      # Heartbeat ping interval in seconds
RECV_BUFFER_SIZE = 4096        # TCP receive buffer chunk size
