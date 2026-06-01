import socket
import struct
import msgpack

PROTOCOL_VERSION = 1
RECV_TIMEOUT = 60


def send(sock: socket.socket, obj: dict) -> None:
    obj = {"v": PROTOCOL_VERSION, **obj}
    data = msgpack.packb(obj)
    sock.sendall(struct.pack(">I", len(data)) + data)


def recv(sock: socket.socket) -> dict | None:
    sock.settimeout(RECV_TIMEOUT)
    try:
        header = _recv_exact(sock, 4)
        if not header:
            return None
        n = struct.unpack(">I", header)[0]
        data = _recv_exact(sock, n)
        if not data:
            return None
        msg = msgpack.unpackb(data, raw=False)
        if msg.get("v") != PROTOCOL_VERSION:
            raise ValueError(f"protocol version mismatch: got {msg.get('v')}, want {PROTOCOL_VERSION}")
        return msg
    except TimeoutError:
        return None
    finally:
        sock.settimeout(None)


def _recv_exact(sock: socket.socket, n: int) -> bytes | None:
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            return None
        buf += chunk
    return buf
