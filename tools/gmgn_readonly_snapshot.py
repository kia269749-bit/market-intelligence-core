"""Read-only GMGN market snapshot adapter. Never imports swap/order skills."""
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

DEMO_KEY = "gmgn_solbscbaseethmonadtron"
COMMAND = ["gmgn-cli", "market", "trending", "--chain", "sol", "--interval", "1h", "--limit", "10"]
OUT = Path("signal_lab/live")

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc)
    if now.date().isoformat() > "2026-12-01":
        print("Signal Lab window expired; no request sent.")
        return 0
    env = os.environ.copy()
    env["GMGN_API_KEY"] = DEMO_KEY
    # Explicitly no wallet, swap, order, or private-key variables are read.
    p = subprocess.run(COMMAND, env=env, text=True, capture_output=True, timeout=90)
    record = {
        "schema_version": 1,
        "source_id": "gmgn_skills",
        "fetched_at_utc": now.isoformat(),
        "mode": "read_only_public_demo_key",
        "command": COMMAND,
        "returncode": p.returncode,
        "stderr": p.stderr[-4000:],
        "raw_stdout": p.stdout,
        "live_orders": False,
    }
    try:
        record["payload"] = json.loads(p.stdout)
        record["payload_parse_status"] = "json"
    except Exception:
        record["payload_parse_status"] = "non_json"
    path = OUT / ("gmgn_sol_trending_" + now.strftime("%Y%m%dT%H%M%SZ") + ".json")
    path.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"snapshot": str(path), "returncode": p.returncode,
                      "payload_parse_status": record["payload_parse_status"],
                      "stdout_chars": len(p.stdout), "stderr_tail": record["stderr"]},
                     indent=2, ensure_ascii=False))
    return p.returncode

if __name__ == "__main__":
    sys.exit(main())
