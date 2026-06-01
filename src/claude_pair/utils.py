import secrets
import socket
import string
from claude_pair.constants import CODE_LENGTH

_ALPHABET = string.ascii_lowercase + string.digits


def gen_code() -> str:
    return "".join(secrets.choice(_ALPHABET) for _ in range(CODE_LENGTH))


def get_local_ip() -> str:
    # UDP connect never sends packets — just forces the OS to pick the right interface.
    # Try progressively more local targets so air-gapped LANs work too.
    for target in ("10.255.255.255", "192.168.255.255", "172.31.255.255", "8.8.8.8"):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect((target, 80))
                return s.getsockname()[0]
        except OSError:
            continue
    return socket.gethostbyname(socket.gethostname())
