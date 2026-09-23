#!/usr/bin/env python3
"""Connectivity + facts check across all three platforms in the lab, one
mechanism per group:

  frr     -> `docker exec <container> vtysh -c "..."` (no SSH daemon in
             the image; this is the same access method containerlab's
             own FRR example uses)
  eos     -> nornir_scrapli (arista_eos is a scrapli CORE platform, no
             extra community driver needed)
  srlinux -> raw JSON-RPC via `requests` (SR Linux's native automation
             interface - see the nokia.srlinux Ansible playbooks for the
             collection-based equivalent)

Run from the nornir/ directory:
    python scripts/01_get_facts.py
"""
import subprocess

import requests
# from nornir import InitNornir
from nornir.core.task import Result, Task
from nornir_scrapli.tasks import send_command
from nornir_utils.plugins.functions import print_result

from common import init_nornir, check_jsonrpc

def frr_show(task: Task, command: str) -> Result:
    proc = subprocess.run(
        ["docker", "exec", task.host.hostname, "vtysh", "-c", command],
        capture_output=True,
        text=True,
        timeout=10,
    )
    if proc.returncode != 0:
        return Result(host=task.host, result=proc.stderr, failed=True)
    return Result(host=task.host, result=proc.stdout)


def srl_get(task: Task, path: str) -> Result:
    url = f"http://{task.host.hostname}/jsonrpc"
    payload = {
        "jsonrpc": "2.0",
        "id": 0,
        "method": "get",
        "params": {"commands": [{"path": path, "datastore": "state"}]},
    }
    resp = requests.post(
        url,
        json=payload,
        auth=(task.host.username, task.host.password),
        timeout=10,
    )
    data = check_jsonrpc(resp)
    return Result(host=task.host, result=data["result"])


def get_facts(task: Task) -> None:
    if "frr" in task.host.groups:
        task.run(task=frr_show, command="show version", name="show version")
    elif "eos" in task.host.groups:
        task.run(task=send_command, command="show version", name="show version")
    elif "srlinux" in task.host.groups:
        task.run(
            task=srl_get,
            path="/system/information/version",
            name="get /system/information/version",
        )


def main() -> None:
    nr = init_nornir(config_file="config.yaml")
    result = nr.run(task=get_facts)
    print_result(result)

    failed = [host for host, r in result.items() if r.failed]
    if failed:
        print(f"\nFailed on: {failed}")
    else:
        print(f"\nAll {len(result)} hosts reachable.")


if __name__ == "__main__":
    main()
