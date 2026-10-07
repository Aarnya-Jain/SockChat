"""
Standalone CLI Client for testing the Raw TCP Socket Core directly.
Demonstrates direct socket.socket(AF_INET, SOCK_STREAM) usage without a browser.
"""
import socket
import threading
import sys
import json
from server.protocol import frame_message, StreamBuffer
from server import config


def listen_server(sock: socket.socket):
    buf = StreamBuffer()
    while True:
        try:
            chunk = sock.recv(4096)
            if not chunk:
                print("\n[Disconnected from server]")
                break
            messages = buf.feed(chunk)
            for msg in messages:
                mtype = msg.get("type")
                if mtype == "chat":
                    print(f"\n💬 [{msg.get('from', 'anon')}]: {msg.get('text')}")
                elif mtype == "draw":
                    print(f"\n🎨 [Draw by {msg.get('from')}]: ({msg.get('x1')},{msg.get('y1')}) -> ({msg.get('x2')},{msg.get('y2')}) [{msg.get('color')}]")
                elif mtype == "user_joined":
                    print(f"\n👋 User joined: {msg.get('user', {}).get('name')} (Total: {msg.get('user_count')})")
                elif mtype == "user_left":
                    print(f"\n🚶 User left: {msg.get('name')} (Total: {msg.get('user_count')})")
                elif mtype == "clear":
                    print(f"\n🧹 Canvas cleared by {msg.get('from')}")
                elif mtype == "error":
                    print(f"\n❌ Error [{msg.get('code')}]: {msg.get('message')}")
                elif mtype == "room_created":
                    print(f"\n🎉 Room created with key: {msg.get('room')}")
                elif mtype == "room_state":
                    print(f"\n📋 Room {msg.get('room')} state: {msg.get('user_count')} users online.")
                print("> ", end="", flush=True)
        except Exception:
            break


def main():
    host = sys.argv[1] if len(sys.argv) > 1 else config.TCP_HOST
    port = int(sys.argv[2]) if len(sys.argv) > 2 else config.TCP_PORT

    print(f"Connecting to TCP Socket Core at {host}:{port}...")
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((host, port))
        print(" Connected via raw TCP socket!")
    except Exception as exc:
        print(f"❌ Connection failed: {exc}")
        return

    threading.Thread(target=listen_server, args=(sock,), daemon=True).start()

    name = input("Enter your display name: ").strip() or "TerminalUser"
    choice = input("1: Create Room, 2: Join Room [1/2]: ").strip()

    if choice == "2":
        room_key = input("Enter room key: ").strip().upper()
        sock.sendall(frame_message({"type": "join_room", "room": room_key, "name": name}))
    else:
        sock.sendall(frame_message({"type": "create_room", "name": name}))

    print("\nCommands: /chat <message>, /draw <x1> <y1> <x2> <y2> <color>, /clear, /quit\n")
    try:
        while True:
            line = input("> ").strip()
            if not line:
                continue
            if line == "/quit":
                sock.sendall(frame_message({"type": "leave"}))
                break
            elif line == "/clear":
                sock.sendall(frame_message({"type": "clear"}))
            elif line.startswith("/chat "):
                text = line[6:].strip()
                sock.sendall(frame_message({"type": "chat", "text": text}))
            elif line.startswith("/draw "):
                parts = line.split()
                if len(parts) >= 6:
                    sock.sendall(frame_message({
                        "type": "draw",
                        "x1": float(parts[1]),
                        "y1": float(parts[2]),
                        "x2": float(parts[3]),
                        "y2": float(parts[4]),
                        "color": parts[5],
                        "width": 3
                    }))
                else:
                    print("Usage: /draw <x1> <y1> <x2> <y2> <#hexcolor>")
            else:
                # Default is chat
                sock.sendall(frame_message({"type": "chat", "text": line}))
    except (KeyboardInterrupt, EOFError):
        pass
    finally:
        sock.close()
        print("\nExiting.")


if __name__ == "__main__":
    main()
