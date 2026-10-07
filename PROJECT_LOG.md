# SockChat - Project & Chat Activity Log

This log file tracks the summary of development chats and actions taken across project iterations.

---

## 📝 Session Entry: 2026-10-07 | Initial Project Kickoff & Complete MVP Implementation

### 1. User Request Summary
- **Input:** Received specification PDF (`Collaborative_Canvas_CN_PBL_Project_Specification_v2.pdf`) for Computer Networks Lab PBL (Course Code: `24B15CS313`, Semester: 5th).
- **Core Directives:**
  - Start the implementation covering all specification requirements.
  - Deliver a browser-accessible URL application backed visibly and demonstrably by Python's raw `socket.socket(AF_INET, SOCK_STREAM)` TCP library.
  - Create and maintain a persistent log file (`PROJECT_LOG.md`) documenting chat summaries and progress.

### 2. Specification Analysis & Architectural Decisions
- **Browser vs. Socket Constraint:** Browsers cannot directly open arbitrary raw TCP sockets using JavaScript. To satisfy both "browser opens URL" and "demonstrable Python raw TCP socket networking", implemented a Python Web Bridge pattern:
  - The browser interacts with the web bridge via standard HTTP POST and Server-Sent Events (SSE).
  - The bridge maintains a dedicated 1:1 raw TCP socket connection (`socket.socket(AF_INET, SOCK_STREAM)`) to the Socket Core for each connected client.
  - All collaboration events flow through raw TCP sockets, fully capturable in Wireshark on port 9999.
- **Message Protocol:** Newline-delimited (`\n`) JSON framing over TCP streams to solve TCP byte stream boundaries and packet fragmentation.
- **Dependency Choice:** 100% Python 3 standard library (`socket`, `http.server`, `threading`, `json`, `secrets`). Zero external pip package dependencies required.

### 3. Deliverables Implemented

#### Backend Architecture (`server/`):
- [`config.py`](file:///home/aarnya-jain/Documents/projects/SockChat/server/config.py): Ports (TCP 9999, Web 8080), room limits (max 4 users), payload size constraints (64 KB).
- [`models.py`](file:///home/aarnya-jain/Documents/projects/SockChat/server/models.py): OOP abstractions for `Room`, `User`, and `CanvasEvent`.
- [`protocol.py`](file:///home/aarnya-jain/Documents/projects/SockChat/server/protocol.py): `StreamBuffer` chunk assembly, newline framing, and payload validation.
- [`room_manager.py`](file:///home/aarnya-jain/Documents/projects/SockChat/server/room_manager.py): Cryptographic room key generation, capacity bounds, and empty room cleanup.
- [`connection_manager.py`](file:///home/aarnya-jain/Documents/projects/SockChat/server/connection_manager.py): Active client socket registry, thread-safe transmission, and room broadcasting.
- [`router.py`](file:///home/aarnya-jain/Documents/projects/SockChat/server/router.py): Event dispatching, drawing/chat history storage, and cross-room boundary isolation.
- [`socket_server.py`](file:///home/aarnya-jain/Documents/projects/SockChat/server/socket_server.py): Raw TCP socket server (`AF_INET`, `SOCK_STREAM`), multi-threaded connection handling.
- [`app.py`](file:///home/aarnya-jain/Documents/projects/SockChat/server/app.py): Unified entrypoint, HTTP static file server, and SSE-to-TCP socket bridge.

#### Frontend UI & Engines (`client/`):
- [`index.html`](file:///home/aarnya-jain/Documents/projects/SockChat/client/index.html) & [`js/lobby.js`](file:///home/aarnya-jain/Documents/projects/SockChat/client/js/lobby.js): Sleek landing page with room creation and room joining tabs.
- [`room.html`](file:///home/aarnya-jain/Documents/projects/SockChat/client/room.html): Split-view workspace featuring drawing canvas and sidebar chat.
- [`css/style.css`](file:///home/aarnya-jain/Documents/projects/SockChat/client/css/style.css): Modern responsive dark UI styling.
- [`js/transport.js`](file:///home/aarnya-jain/Documents/projects/SockChat/client/js/transport.js): Persistent SSE listener and HTTP POST action dispatcher.
- [`js/canvas.js`](file:///home/aarnya-jain/Documents/projects/SockChat/client/js/canvas.js): Vector drawing engine with mouse/touch support, stroke history reconstruction, pen/eraser/palette controls.
- [`js/chat.js`](file:///home/aarnya-jain/Documents/projects/SockChat/client/js/chat.js): Real-time chat feed with sender color tagging and system notification banners.
- [`cli_client.py`](file:///home/aarnya-jain/Documents/projects/SockChat/client/cli_client.py): Terminal client communicating directly over raw TCP sockets without a browser.

#### Test Suite (`tests/`):
- [`test_protocol.py`](file:///home/aarnya-jain/Documents/projects/SockChat/tests/test_protocol.py): Buffer chunking, frame limits, schema checks.
- [`test_rooms.py`](file:///home/aarnya-jain/Documents/projects/SockChat/tests/test_rooms.py): Unique keys, join/leave lifecycle, auto-cleanup.
- [`test_capacity.py`](file:///home/aarnya-jain/Documents/projects/SockChat/tests/test_capacity.py): Rejection on room capacity breach (`ROOM_FULL`).
- [`test_isolation.py`](file:///home/aarnya-jain/Documents/projects/SockChat/tests/test_isolation.py): Ensures drawing, chat, and clear events in Room A never reach Room B.
- [`test_socket_server.py`](file:///home/aarnya-jain/Documents/projects/SockChat/tests/test_socket_server.py): End-to-end TCP socket loopback integration test.
- [`test_web_bridge.py`](file:///home/aarnya-jain/Documents/projects/SockChat/tests/test_web_bridge.py): HTTP static assets and SSE-to-TCP translation tests.
- **Result:** All 27 tests passing.

#### Documentation (`docs/` & Project Root):
- [`README.md`](file:///home/aarnya-jain/Documents/projects/SockChat/README.md): Quickstart guide, architectural breakdown, and course outcome mapping.
- [`docs/architecture.md`](file:///home/aarnya-jain/Documents/projects/SockChat/docs/architecture.md): In-depth topology diagrams and event flow sequences.
- [`docs/wireshark/guide.md`](file:///home/aarnya-jain/Documents/projects/SockChat/docs/wireshark/guide.md): Viva step-by-step packet inspection checklist and display filters.

### 4. Git Repository Initialization
- Initialized local Git repository (`git init`).
- Added [`.gitignore`](file:///home/aarnya-jain/Documents/projects/SockChat/.gitignore) for Python caches, OS files, and virtual environments.

### 5. Next Steps / Current Readiness
- Project is fully ready to run locally: `python3 server/app.py`.
- Wireshark captures can be performed immediately on port `9999`.
