import os
from pathlib import Path

DEFAULT_PORT = 52001
HOST_IPC_PORT = 52002
JOIN_IPC_PORT = 52003
CODE_LENGTH = 6
DISCOVERY_TIMEOUT = 10.0
SERVICE_TYPE = "_claude-pair._tcp.local."
_DIR = Path(os.environ.get("CLAUDE_PAIR_DIR", str(Path.home() / ".claude-pair")))
SESSION_FILE = _DIR / "session.json"
STATE_FILE = _DIR / "state.json"
CONFIG_FILE = _DIR / "config.json"
PID_FILE = _DIR / "session.pid"
HUMAN_GATE_TIMEOUT = 120
EXCHANGE_GATE_THRESHOLD = 4
