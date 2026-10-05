#!/usr/bin/env python3
"""Simple file-based inbox for the depfix agent team.

Usage:
  python3 scripts/agent-msg.py send <to-role> '<json-body>'
  python3 scripts/agent-msg.py inbox <role>          # print unacked messages
  python3 scripts/agent-msg.py ack <role> <msg-id>   # mark message acked
  python3 scripts/agent-msg.py whoami                # print current role (from AGENT_ROLE env)
"""
from __future__ import annotations
import json, os, sys, uuid
from datetime import datetime, timezone
from pathlib import Path

INBOX_DIR = Path(__file__).resolve().parents[1] / "coordination" / "inbox"
VALID_ROLES = {"principal", "researcher", "implementer", "reviewer", "tester"}


def _inbox_path(role: str) -> Path:
    return INBOX_DIR / f"{role}.jsonl"


def send(to: str, body_json: str, from_role: str | None = None) -> None:
    if to not in VALID_ROLES:
        print(f"ERROR: unknown role '{to}'. Valid: {VALID_ROLES}", file=sys.stderr)
        sys.exit(1)
    from_role = from_role or os.environ.get("AGENT_ROLE", "unknown")
    msg = {
        "id": str(uuid.uuid4()),
        "from": from_role,
        "to": to,
        "ts": datetime.now(timezone.utc).isoformat(),
        "acked": False,
        "body": json.loads(body_json),
    }
    path = _inbox_path(to)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a") as f:
        f.write(json.dumps(msg) + "\n")
    print(f"sent {msg['id']} -> {to}")


def inbox(role: str) -> None:
    if role not in VALID_ROLES:
        print(f"ERROR: unknown role '{role}'", file=sys.stderr)
        sys.exit(1)
    path = _inbox_path(role)
    if not path.exists():
        print("[]")
        return
    msgs = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    unacked = [m for m in msgs if not m.get("acked")]
    print(json.dumps(unacked, indent=2))


def ack(role: str, msg_id: str) -> None:
    if role not in VALID_ROLES:
        print(f"ERROR: unknown role '{role}'", file=sys.stderr)
        sys.exit(1)
    path = _inbox_path(role)
    if not path.exists():
        print(f"inbox for {role} is empty")
        return
    lines = path.read_text().splitlines()
    updated = []
    found = False
    for line in lines:
        if not line.strip():
            continue
        msg = json.loads(line)
        if msg["id"] == msg_id:
            msg["acked"] = True
            found = True
        updated.append(json.dumps(msg))
    if not found:
        print(f"WARNING: message {msg_id} not found in {role} inbox", file=sys.stderr)
    path.write_text("\n".join(updated) + "\n")
    print(f"acked {msg_id}")


def whoami() -> None:
    role = os.environ.get("AGENT_ROLE", "unset")
    print(role)


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    cmd = sys.argv[1]
    if cmd == "send" and len(sys.argv) >= 4:
        send(sys.argv[2], sys.argv[3])
    elif cmd == "inbox" and len(sys.argv) >= 3:
        inbox(sys.argv[2])
    elif cmd == "ack" and len(sys.argv) >= 4:
        ack(sys.argv[2], sys.argv[3])
    elif cmd == "whoami":
        whoami()
    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
