#!/usr/bin/env python3
"""SR Linux only (r6) - push a config change (system0 description) via
JSON-RPC 'set', then read it back to confirm. The raw-API equivalent of
the Ansible 03_configure_interface.yml playbook.

Config-push for the frr/eos groups isn't built out yet - a natural next
exercise once the read-only facts scripts are working end to end.

Run from the nornir/ directory:
    python scripts/02_configure_interface.py
"""
from nornir.core.task import Result, Task
from nornir_utils.plugins.functions import print_result

import requests
from common import init_nornir, check_jsonrpc

def set_description(task: Task) -> Result:
    url = f"http://{task.host.hostname}/jsonrpc"
    auth = (task.host.username, task.host.password)
    as_number = task.host["as_number"]

    set_payload = {
        "jsonrpc": "2.0",
        "id": 0,
        "method": "set",
        "params": {
            "commands": [
                {
                    "action": "update",
                    "path": "/interface[name=system0]/description",
                    "value": f"managed by nornir - AS{as_number}",
                }
            ]
        },
    }
    check_jsonrpc(requests.post(url, json=set_payload, auth=auth, timeout=10))

    get_payload = {
        "jsonrpc": "2.0",
        "id": 0,
        "method": "get",
        "params": {
            "commands": [
                {"path": "/interface[name=system0]/description", "datastore": "state"}
            ]
        },
    }
    resp = requests.post(url, json=get_payload, auth=auth, timeout=10)
    data = check_jsonrpc(resp)
    return Result(host=task.host, result=data["result"])


def main() -> None:
    nr = init_nornir(config_file="config.yaml").filter(platform="nokia_srlinux")
    result = nr.run(task=set_description)
    print_result(result)


if __name__ == "__main__":
    main()
