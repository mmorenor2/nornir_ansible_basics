#!/usr/bin/env python3
"""SR Linux only (r6) - pulls the full running config (as JSON) over
JSON-RPC and writes it under backups/. Handy building block for a
git-tracked config backup job later - extend to the frr group with
`vtysh -c "show running-config"` and to eos with `show running-config`
over scrapli when you're ready to generalize this.

Run from the nornir/ directory:
    python scripts/03_backup_configs.py
"""
import json
from pathlib import Path

import requests
from nornir.core.task import Result, Task
from nornir_utils.plugins.functions import print_result

from common import init_nornir, check_jsonrpc

BACKUP_DIR = Path(__file__).parent.parent / "backups"


def srl_backup(task: Task) -> Result:
    url = f"http://{task.host.hostname}/jsonrpc"
    payload = {
        "jsonrpc": "2.0",
        "id": 0,
        "method": "get",
        "params": {"commands": [{"path": "/", "datastore": "running"}]},
    }
    resp = requests.post(
        url,
        json=payload,
        auth=(task.host.username, task.host.password),
        timeout=15,
    )
    data = check_jsonrpc(resp)
    return Result(host=task.host, result=data["result"][0])


def main() -> None:
    nr = init_nornir(config_file="config.yaml").filter(platform="nokia_srlinux")

    result = nr.run(task=srl_backup)
    print_result(result, severity_level=40)  # only print errors here

    BACKUP_DIR.mkdir(exist_ok=True)
    for host, host_result in result.items():
        if host_result.failed:
            continue
        out_file = BACKUP_DIR / f"{host}.json"
        out_file.write_text(json.dumps(host_result[0].result, indent=2))
        print(f"Wrote {out_file}")


if __name__ == "__main__":
    main()
