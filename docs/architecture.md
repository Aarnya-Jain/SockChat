# Collaborative Canvas - System Architecture

## 1. Overview & Constraint Analysis

### The Browser vs. Raw Socket Challenge
Web browsers operate under strict sandbox environments and security models. Standard browser JavaScript cannot instantiate arbitrary raw TCP sockets (`AF_INET`, `SOCK_STREAM`). While browsers natively support HTTP, HTTPS, and WebSockets (RFC 6455), the academic requirement for the **Computer Networks Lab (24B15CS313)** PBL is to demonstrably showcase Python's fundamental `socket` library.

### The Architectural Bridge Solution
To satisfy both constraints simultaneously:
1. The **End-User Experience** is accessible via any modern browser without installing custom desktop clients.
2. The **Core Networking Engine** is built strictly upon Python's standard `socket.socket(AF_INET, SOCK_STREAM)` TCP listener.
3. A **Python Web Bridge** acts as an internal protocol translation adapter. Each active browser session is allocated a dedicated raw TCP client socket connection to the TCP Socket Core.

---

## 2. Component Topology

```
+-------------------------------------------------------------+
|                        BROWSER CLIENT                       |
|   HTML5 Canvas  |  Chat Panel  |  Lobby UI  |  transport.js |
+-------------------------------------------------------------+
               |                                ^
     HTTP POST |                                | Server-Sent Events
   /api/action |                                | /api/stream
               v                                |
+-------------------------------------------------------------+
|                      PYTHON WEB BRIDGE                      |
|                  (server/app.py - Port 8080)                |
|  - Serves static assets (HTML/CSS/JS)                       |
|  - Manages session IDs & dedicated TCP client sockets       |
|  - Relays browser events into TCP streams                   |
|  - Streams TCP broadcast responses back to browser via SSE  |
+-------------------------------------------------------------+
               |                                ^
      Raw TCP  |                                | Raw TCP
  sendall(...) |                                | recv(...)
               v                                |
+-------------------------------------------------------------+
|                   RAW TCP SOCKET CORE                       |
|             (server/socket_server.py - Port 9999)           |
|                                                             |
|  - socket.socket(AF_INET, SOCK_STREAM)                      |
|  - SO_REUSEADDR, non-blocking / multi-threaded worker pool   |
|  - StreamBuffer: Newline-delimited JSON frame parser        |
|  - ConnectionManager: Active TCP socket tracking & broadcast|
|  - RoomManager: Isolated room state, capacity enforcement   |
|  - MessageRouter: Application dispatch & cross-room fencing |
+-------------------------------------------------------------+
            /                       |                       \
           v                        v                        v
     [ Room A ]               [ Room B ]               [ Room N ]
  - Max 4 members          - Max 4 members          - Max 4 members
  - Drawing strokes        - Drawing strokes        - Drawing strokes
  - Chat history           - Chat history           - Chat history
```

---

## 3. Data Flow & Event Sequences

### A. Room Creation & Joining
1. **Lobby Submission:** User submits display name and requests room creation.
2. **Bridge Connection:** Browser initiates `EventSource('/api/stream?session_id=...')`.
3. **TCP Connection Establishment:** Web Bridge executes `socket.socket(AF_INET, SOCK_STREAM)` and connects to `127.0.0.1:9999`.
4. **Action Relayed:** Browser posts `{"action": {"type": "create_room", "name": "Alice"}}`. The bridge sends `b'{"type":"create_room","name":"Alice"}\n'` across the raw TCP socket.
5. **Core Processing:** `SocketServer` parses the framed message, `RoomManager` generates an unguessable 5-character key (e.g. `A7K92`), and registers the user.
6. **State Broadcast:** TCP Core transmits `room_created` and `room_state` JSON packets over the socket.
7. **SSE Delivery:** Web Bridge receives TCP packets and flushes them as SSE messages to the browser.

### B. Real-Time Drawing Synchronization
1. User clicks and drags across the canvas.
2. `canvas.js` computes local canvas coordinates, immediately renders the vector segment locally (for 0ms perceived lag), and dispatches a compact `draw` payload:
   ```json
   {"type":"draw","x1":120.5,"y1":240.0,"x2":135.2,"y2":250.0,"color":"#ef4444","width":4,"mode":"pen"}
   ```
3. The Web Bridge pushes the newline-delimited bytes into the user's TCP socket.
4. `MessageRouter` appends the stroke to Room A's in-memory drawing history.
5. `ConnectionManager` iterates over active connection IDs in Room A and broadcasts the segment to all *other* peers in Room A.
6. Peers' SSE streams receive the payload; `canvas.js` executes `drawRemoteSegment()`.

### C. Room Boundary Isolation
- **Drawings, chat messages, and canvas clear operations are strictly scoped to the room.**
- Peers in Room B never receive packets or events emitted in Room A.
- Unit and integration tests verify complete isolation between simultaneous rooms.

---

## 4. Message Framing & Application Protocol

TCP is a connection-oriented byte stream with no intrinsic message boundaries. A single `recv()` can return a partial message or multiple combined messages.

To solve this, our protocol enforces **newline-delimited JSON (`\n`)**:
- Each serialized JSON payload terminates with `\n` (`0x0A`).
- `StreamBuffer` buffers incoming chunks until a newline byte is located.
- Protection against buffer bloat: Any single frame exceeding `MAX_MESSAGE_BYTES` (64 KB) triggers immediate truncation and a `FRAME_TOO_LARGE` error.
