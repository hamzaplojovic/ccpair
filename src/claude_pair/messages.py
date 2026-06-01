LABELS = {
    "propose_task": "proposed a task",
    "share_context": "shared context",
    "request_review": "requested a review",
    "unblock": "sent an unblock",
}

FIELDS = {
    "propose_task": ["task", "context"],
    "share_context": ["summary", "files"],
    "request_review": ["diff", "question"],
    "unblock": ["message"],
}

OUTGOING_LABELS = {
    "propose_task": "propose a task",
    "share_context": "share context",
    "request_review": "request a review",
    "unblock": "send an unblock",
}


def format_incoming(peer_name: str, msg: dict) -> str:
    msg_type = msg.get("type", "unknown")
    label = LABELS.get(msg_type, msg_type)
    lines = [f"[{peer_name}] {label}:"]
    for field in FIELDS.get(msg_type, []):
        if field in msg:
            lines.append(f"  {field}: {msg[field]}")
    return "\n".join(lines)


def format_outgoing(msg: dict) -> str:
    msg_type = msg.get("type", "unknown")
    label = OUTGOING_LABELS.get(msg_type, msg_type)
    lines = [f"Your Claude wants to {label}:"]
    for field in FIELDS.get(msg_type, []):
        if field in msg:
            lines.append(f"  {field}: {msg[field]}")
    return "\n".join(lines)
