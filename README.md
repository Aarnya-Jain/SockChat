# Real-Time Collaborative Canvas (with Chat)

> **Computer Networks Lab PBL (Project-Based Learning)**  
> **Course Code:** `24B15CS313` | **Semester:** 5th  
> **Core Networking Engine:** Demonstrable Python Raw TCP Sockets (`socket.socket(AF_INET, SOCK_STREAM)`)

---

## 📌 Project Overview

**Collaborative Canvas** is a lightweight, real-time shared drawing and instant messaging web application. A user opens a hosted URL in any standard browser, creates or joins an ephemeral room using a unique 5-character room key, and collaborates on a shared canvas while chatting with peers in real time.

### 🌐 Key Architectural Concept: Browser UI + Python TCP Socket Core
Standard web browsers cannot open arbitrary raw TCP sockets due to JavaScript sandbox restrictions. To satisfy the academic requirement of demonstrating Python's raw TCP socket layer while maintaining a frictionless browser user experience:
- The **Frontend** runs modern HTML5 Canvas + CSS + JavaScript.
- A **Python Web Bridge** (`server/app.py`) serves the static web UI and provides an HTTP/SSE interface.
- Each browser session is assigned a **dedicated raw TCP socket connection** (`socket.socket(AF_INET, SOCK_STREAM)`) to the **Socket Network Core** (`server/socket_server.py`).
- Application events (drawing vectors, chat messages, room state updates) are framed using **newline-delimited JSON** over raw TCP.
- Network traffic can be directly captured and inspected in **Wireshark** on loopback (`lo`) or LAN interfaces.

---

## 🚀 Quick Start

### 1. Requirements
- Python 3.10+ (Standard library only; zero external dependencies required!)

### 2. Launch the Application
Run the unified server entrypoint:
```bash
python3 server/app.py
```
This concurrently starts:
1. **Raw TCP Socket Core** on `127.0.0.1:9999`
2. **Web Bridge & UI Server** on `http://localhost:8080`

### 3. Open in Browser
Open your browser and navigate to:
```
http://localhost:8080
```
1. Enter your display name.
2. Click **Create New Room** (generates a unique room code, e.g. `A7K92`).
3. Open a second browser tab (or incognito window), enter another name, and join room `A7K92`.
4. Draw on the canvas and send chat messages in real time!

---

## 💻 Standalone Terminal CLI Client

To test or demonstrate the raw TCP socket layer directly without any web browser, use the CLI client:
```bash
python3 client/cli_client.py 127.0.0.1 9999
```
Supports commands:
- `/chat <message>`
- `/draw <x1> <y1> <x2> <y2> <#color>`
- `/clear`
- `/quit`

---

## 🧪 Running the Test Suite

The project includes unit and end-to-end integration tests covering protocol framing, room management, capacity enforcement, cross-room isolation, raw TCP socket streams, and the HTTP/SSE bridge:

```bash
python3 -m unittest discover tests -v
```

All 27 test cases execute in ~3 seconds.

---

## 📂 Project Structure

```
SockChat/
├── server/
│   ├── app.py                # Web entry point, HTTP server & SSE bridge
│   ├── socket_server.py      # Raw TCP socket core (AF_INET, SOCK_STREAM)
│   ├── connection_manager.py # Active TCP client socket tracking & broadcasts
│   ├── room_manager.py       # Room lifecycle, capacity limits, cleanup
│   ├── router.py             # Message dispatching & room boundary isolation
│   ├── protocol.py           # Newline-delimited JSON framing & validation
│   ├── models.py             # Room, User, and CanvasEvent OOP abstractions
│   └── config.py             # Ports, limits, and timing configuration
│
├── client/
│   ├── index.html            # Modern lobby / landing page
│   ├── room.html             # Collaborative canvas & chat interface
│   ├── css/
│   │   └── style.css         # Responsive glassmorphism styling
│   ├── js/
│   │   ├── lobby.js          # Lobby form handling and navigation
│   │   ├── transport.js      # SSE stream & HTTP POST abstraction
│   │   ├── canvas.js         # HTML5 Canvas vector sync & rendering engine
│   │   └── chat.js           # Real-time room chat manager
│   └── cli_client.py         # Direct raw TCP socket CLI client
│
├── tests/
│   ├── test_protocol.py      # Framing, buffer boundaries, payload schema
│   ├── test_rooms.py         # Room creation, joining, member tracking
│   ├── test_capacity.py      # Max 4 user enforcement, backpressure
│   ├── test_isolation.py     # Cross-room message isolation verification
│   ├── test_socket_server.py # E2E raw TCP socket networking tests
│   └── test_web_bridge.py    # HTTP routes and SSE stream translation tests
│
├── docs/
│   ├── architecture.md       # Full architecture and sequence flows
│   └── wireshark/
│       └── guide.md          # Wireshark filter and viva demonstration guide
│
├── requirements.txt
├── .gitignore
├── PROJECT_LOG.md            # Interaction and development session log
└── README.md
```

---

## 🔍 Wireshark Demonstration (Viva Checklist)

1. Open Wireshark on interface `lo` (Loopback).
2. Set filter:
   ```wireshark
   tcp.port == 9999
   ```
3. Demonstrate:
   - **Three-way Handshake:** `SYN` -> `SYN, ACK` -> `ACK`.
   - **Application Framing:** Inspect `PSH, ACK` frames containing newline-terminated JSON payloads.
   - **Vector Optimization:** Discuss how compact line segments (`x1, y1, x2, y2`) reduce network bandwidth compared to sending full bitmap snapshots.
   - **Graceful Teardown:** Inspect `FIN, ACK` sequence when leaving a room.

For the complete guide, see [`docs/wireshark/guide.md`](file:///home/aarnya-jain/Documents/projects/SockChat/docs/wireshark/guide.md).

---

## 🎓 Course Outcome Mapping

| Outcome Code | Description & Project Evidence |
| :--- | :--- |
| **C3701** | Client/server topology, IP/port configuration, TCP connections, and socket lifecycle. |
| **C3702** | Python TCP socket implementation, concurrent multi-threading, room broadcasting, message framing protocol. |
| **C3704** | Wireshark packet capture analysis, TCP sequence numbers, SYN/ACK handshake, connection teardown. |
| **C3705** | Threat model, secure room key entropy, schema validation, room capacity boundaries, cross-room isolation. |

---

## 🌍 UN Sustainable Development Goals (SDG) Alignment

- **SDG 9 (Industry, Innovation & Infrastructure):** Real-time networked communication, distributed client-server systems.
- **SDG 4 (Quality Education):** Practical application of computer networking concepts in distributed interactive computing.
- **SDG 8 (Decent Work & Economic Growth):** Professional software engineering practices with robust automated testing.
