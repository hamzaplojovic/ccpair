import json
import os
import socket
import sys
import threading
import time
from pathlib import Path

from claude_pair import discovery, transport
from claude_pair.constants import DEFAULT_PORT, DISCOVERY_TIMEOUT
from claude_pair.utils import gen_code


class Daemon:
    def __init__(self, pair_dir: Path):
        self.dir = pair_dir
        self.sock_path = pair_dir / "daemon.sock"
        self.pid_path = pair_dir / "daemon.pid"
        self.status_path = pair_dir / "status.json"
        self.state = {"connected": False, "code": None, "peer": None, "role": None, "my_name": None}
        self.peer_conn: socket.socket | None = None
        self.tcp_server: socket.socket | None = None
        self.zc_handle = None
        self.peer_event = threading.Event()
        self.peer_replied = threading.Event()
        self.interrupt_event = threading.Event()
        self.inbox: dict | None = None
        self.lock = threading.Lock()

    def _write_status(self) -> None:
        try:
            if self.state.get("connected"):
                self.status_path.write_text(json.dumps({
                    "status": "connected",
                    "peer": self.state["peer"],
                    "role": self.state["role"],
                }))
            elif self.state.get("code"):
                self.status_path.write_text(json.dumps({
                    "status": "waiting",
                    "code": self.state["code"],
                }))
            else:
                self.status_path.unlink(missing_ok=True)
        except Exception:
            pass

    def start(self) -> None:
        self.dir.mkdir(exist_ok=True)
        self.pid_path.write_text(str(os.getpid()))
        self.sock_path.unlink(missing_ok=True)
        srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        srv.bind(str(self.sock_path))
        srv.listen(8)
        sys.stderr.write(f"[ccpair daemon] listening on {self.sock_path}\n")
        sys.stderr.flush()
        try:
            while True:
                client, _ = srv.accept()
                threading.Thread(target=self._handle_client, args=(client,), daemon=True).start()
        finally:
            srv.close()
            self.sock_path.unlink(missing_ok=True)
            self.pid_path.unlink(missing_ok=True)
            self.status_path.unlink(missing_ok=True)

    def _handle_client(self, client: socket.socket) -> None:
        try:
            while True:
                msg = transport.recv(client)
                if msg is None:
                    return
                try:
                    resp = self._handle_cmd(msg)
                except Exception as e:
                    resp = {"error": f"daemon exception: {e}"}
                transport.send(client, resp)
        finally:
            try:
                client.close()
            except Exception:
                pass

    def _handle_cmd(self, msg: dict) -> dict:
        cmd = msg.get("cmd")
        handler = getattr(self, f"_cmd_{cmd}", None)
        if not handler:
            return {"error": f"unknown cmd: {cmd}"}
        return handler(msg)

    def _cmd_host(self, msg: dict) -> dict:
        if self.tcp_server or self.peer_conn:
            return {"error": "session already active; stop first"}
        name = msg["name"]
        code = gen_code()
        try:
            srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            srv.bind(("0.0.0.0", DEFAULT_PORT))
            srv.listen(1)
        except OSError as e:
            return {"error": f"bind :{DEFAULT_PORT} failed: {e}"}
        self.tcp_server = srv
        self.state.update(role="host", code=code, my_name=name, connected=False, peer=None)
        try:
            zc, info = discovery.advertise(code, DEFAULT_PORT)
            self.zc_handle = (zc, info)
        except Exception as e:
            srv.close()
            self.tcp_server = None
            self.state.update(code=None, role=None)
            return {"error": f"mDNS advertise failed: {e}"}
        self.peer_event.clear()
        self._write_status()
        threading.Thread(target=self._accept_peer, daemon=True).start()
        return {"code": code}

    def _accept_peer(self) -> None:
        try:
            srv = self.tcp_server
            conn, _ = srv.accept()
            srv.close()
            self.tcp_server = None
            msg = transport.recv(conn)
            peer_name = msg["name"] if msg else "guest"
            transport.send(conn, {"name": self.state["my_name"]})
            self.peer_conn = conn
            self.state.update(connected=True, peer=peer_name)
            if self.zc_handle:
                zc, info = self.zc_handle
                try:
                    zc.unregister_service(info)
                    zc.close()
                except Exception:
                    pass
                self.zc_handle = None
            self._write_status()
            self.peer_event.set()
            threading.Thread(target=self._relay_loop, daemon=True).start()
        except Exception as e:
            sys.stderr.write(f"[ccpair daemon] accept_peer failed: {e}\n")

    def _cmd_wait_peer(self, msg: dict) -> dict:
        timeout = msg.get("timeout", 90)
        if self.peer_event.wait(timeout):
            return {"connected": self.state["peer"]}
        return {"timeout": True}

    def _cmd_join(self, msg: dict) -> dict:
        if self.peer_conn or self.tcp_server:
            return {"error": "session already active; stop first"}
        code = msg["code"]
        name = msg["name"]
        result = discovery.find(code, DISCOVERY_TIMEOUT)
        if not result:
            return {"error": f"session '{code}' not found on this network"}
        ip, port = result
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.connect((ip, port))
        except Exception as e:
            return {"error": f"connect to {ip}:{port} failed: {e}"}
        transport.send(sock, {"name": name})
        reply = transport.recv(sock)
        host_name = reply["name"] if reply else "host"
        self.peer_conn = sock
        self.state.update(role="join", connected=True, peer=host_name, my_name=name)
        self._write_status()
        threading.Thread(target=self._relay_loop, daemon=True).start()
        return {"connected": host_name}

    def _relay_loop(self) -> None:
        while True:
            try:
                msg = transport.recv(self.peer_conn)
            except Exception:
                msg = None
            if msg is None:
                with self.lock:
                    self.state.update(connected=False)
                    self.peer_conn = None
                self._write_status()
                return
            with self.lock:
                self.inbox = msg
            self.peer_replied.set()

    def _cmd_send(self, msg: dict) -> dict:
        if not self.peer_conn:
            return {"error": "no active session"}
        try:
            transport.send(self.peer_conn, msg["msg"])
        except Exception as e:
            return {"error": f"send failed: {e}"}
        return {"sent": True}

    def _cmd_await_peer(self, msg: dict) -> dict:
        timeout = msg.get("timeout", 120)
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.interrupt_event.is_set():
                self.interrupt_event.clear()
                return {"interrupted": True}
            if self.peer_replied.is_set():
                self.peer_replied.clear()
                with self.lock:
                    action = (self.inbox or {}).get("type", "message")
                return {"peer_replied": action}
            time.sleep(0.2)
        return {"timeout": True}

    def _cmd_read_inbox(self, msg: dict) -> dict:
        with self.lock:
            if self.inbox is None:
                return {"empty": True}
            inbox = self.inbox
            self.inbox = None
        return {"inbox": inbox}

    def _cmd_interrupt(self, msg: dict) -> dict:
        self.interrupt_event.set()
        return {"ok": True}

    def _cmd_status(self, msg: dict) -> dict:
        return dict(self.state)

    def _cmd_stop(self, msg: dict) -> dict:
        if self.peer_conn:
            try:
                self.peer_conn.close()
            except Exception:
                pass
            self.peer_conn = None
        if self.tcp_server:
            try:
                self.tcp_server.close()
            except Exception:
                pass
            self.tcp_server = None
        if self.zc_handle:
            zc, info = self.zc_handle
            try:
                zc.unregister_service(info)
                zc.close()
            except Exception:
                pass
            self.zc_handle = None
        self.state = {"connected": False, "code": None, "peer": None, "role": None, "my_name": None}
        self.peer_event.clear()
        self.peer_replied.clear()
        self.interrupt_event.clear()
        self.inbox = None
        self._write_status()
        return {"stopped": True}

    def _cmd_shutdown(self, msg: dict) -> dict:
        self._cmd_stop(msg)
        threading.Thread(target=lambda: (time.sleep(0.1), os._exit(0)), daemon=True).start()
        return {"shutting_down": True}


def run_daemon(pair_dir: Path) -> None:
    Daemon(pair_dir).start()
