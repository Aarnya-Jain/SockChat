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

---

## 📝 Session Entry: 2026-11-15 | Bug Fixes & Stability Optimization (BUGS Folder)

### 1. User Request Summary
- **Input:** Received bug reports and screenshots in `BUGS/` (`bugs.txt` and `image.png`).
- **Reported Issues:**
  1. *Both are not connected properly* (desynced rooms, phantom leaves).
  2. *Session times out early* (inactivity disconnection after 1-2 minutes).
  3. *Chat section with history not visible in both the clients* (missing chat messages upon reload/reconnect).
  4. *It is not synced (showing 1/4 in one and 2/4 in other)* (user count mismatch, desynced states).
  5. *UI is buggy and not Responsive* (toolbar clipped on side-by-side screens, cut-off clear button, rigid sidebar).

### 2. Root Cause Analysis
- **Inactivity Timeout & Idle Connection Drops:** The TCP socket server had a hard 120s inactivity timeout without keep-alive probes. Similarly, the HTTP/SSE bridge lacked heartbeats, prompting browsers and operating systems to close idle SSE connections after 30-60 seconds.
- **Race Condition in Bridge Registry:** `BridgeRegistry.remove()` popped sessions unconditionally by string ID. When an SSE stream reconnected quickly, the previous thread's `finally` block closed the newly established socket.
- **Drawing Stroke HTTP Flooding:** Every single `mousemove` event fired an independent asynchronous `fetch('/api/action')` call. A few seconds of drawing generated hundreds of concurrent HTTP requests, exhausting browser per-host connection pools (limit: 6), causing socket broken pipes and connection resets.
- **Missing `user_id` in Chat History:** `Room.add_chat()` did not record `user_id`, causing reloaded/reconnected clients to misclassify message origins.
- **UI Overflow & Sizing on Split Screens:** Fixed 360px sidebar squeezed the canvas area to ~600px in half-screen layouts. The floating toolbar exceeded 650px, causing the right edge ("Clear" button) to be clipped. The mobile media query broke split-screen desktops (< 900px).

### 3. Solutions Implemented
- **Heartbeat & Keep-Alive:**
  - Added 15s SSE heartbeat comments (`: heartbeat\n\n`) and TCP `ping`/`pong` probes in `server/app.py` and `server/socket_server.py`.
  - Replaced blocking timeouts with a 1.0s loop polling mechanism in `_client_handler` so thread shutdowns exit cleanly within 1s.
- **Safe Session Cleanup & Reconnect:**
  - Implemented `registry.remove_session(session)` in `server/app.py` to prevent race conditions during reconnections.
  - Generates unique instance session IDs in `client/js/transport.js` to prevent collisions across browser tab reloads.
  - In `server/room_manager.py`, automatically evicts stale duplicate user sessions when a user rejoins with the same display name.
  - Updated `client/room.html` to track `hasJoined` and `currentRoom`, ensuring reconnects rejoin the active room instead of re-creating a new one.
- **Client & Server Stroke Batching:**
  - Added vector segment buffering in `client/js/canvas.js` with a 25ms flush cycle and `mouseup` flush.
  - Added `draw_batch` schema validation in `server/protocol.py` and batch broadcasting in `server/router.py`.
  - Reduced HTTP requests by 85-90% during fast drawing, eliminating browser queue congestion and connection resets.
- **Chat History & User Ownership:**
  - `server/models.py` now preserves `user_id` in room chat history.
  - `client/js/chat.js` dynamically updates message classes (`my-msg`) when the current user identity is received.
- **Responsive & Modernized UI:**
  - Redesigned `.toolbar` with responsive wrapping, compact sizing, and smaller padding so it never overflows.
  - Added a collapsible sidebar toggle (`#toggleSidebarBtn`) to give users full canvas focus when needed.
  - Added "(You)" indicator for the local user in the participant chips list.
  - Refined mobile breakpoint from 900px down to 768px to ensure side-by-side split screens maintain a spacious desktop layout.

### 4. Verification & Testing
- Added regression test suite in `tests/test_bugs_fixed.py` covering multi-user chat history, stroke batching, and synchronized join/leave events.
- All 31 unit and integration tests passing cleanly (`python3 -m unittest discover tests`).

---

## Session 4 — 2026-11-15

### Summary
- Reviewed deployment requirements; user requested steps only (no code changes).
- Confirmed zero external dependencies — pure Python 3.10+ stdlib.
- Documented all configurable environment variables (`TCP_HOST`, `TCP_PORT`, `WEB_HOST`, `WEB_PORT`).
- Produced full deployment guide covering:
  - Local / LAN run (`python3 server/app.py`)
  - VPS / Cloud VM setup (Ubuntu + SCP/git clone)
  - Background process options: `screen`, `tmux`, `systemd` with auto-restart
  - Custom port overrides via env vars (no code edits)
  - Nginx reverse proxy config with SSE-safe headers (`proxy_buffering off`, `X-Accel-Buffering: no`)
  - Quick verification commands for web + TCP health check
- No code files were modified this session.
- Git state: clean at `c5c3123`.
