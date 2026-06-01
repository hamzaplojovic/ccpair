import socket
import time
from zeroconf import ServiceBrowser, ServiceInfo, ServiceListener, Zeroconf
from claude_pair.constants import DISCOVERY_TIMEOUT, SERVICE_TYPE
from claude_pair.utils import get_local_ip


def advertise(code: str, port: int) -> tuple[Zeroconf, ServiceInfo]:
    zc = Zeroconf(interfaces=[get_local_ip()])
    info = ServiceInfo(
        SERVICE_TYPE,
        f"{code}.{SERVICE_TYPE}",
        addresses=[socket.inet_aton(get_local_ip())],
        port=port,
        properties={"code": code},
    )
    zc.register_service(info)
    return zc, info


def find(code: str, timeout: float = DISCOVERY_TIMEOUT) -> tuple[str, int] | None:
    found = {}

    class Listener(ServiceListener):
        def add_service(self, zc, svc_type, name):
            info = zc.get_service_info(svc_type, name)
            if info and info.properties.get(b"code", b"").decode() == code:
                found["ip"] = socket.inet_ntoa(info.addresses[0])
                found["port"] = info.port

        def update_service(self, zc, svc_type, name): pass
        def remove_service(self, zc, svc_type, name): pass

    zc = Zeroconf(interfaces=[get_local_ip()])
    ServiceBrowser(zc, SERVICE_TYPE, Listener())
    deadline = time.time() + timeout
    while time.time() < deadline:
        if "ip" in found:
            zc.close()
            return found["ip"], found["port"]
        time.sleep(0.1)
    zc.close()
    return None
