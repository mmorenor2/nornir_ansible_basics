"""Shared Nornir bootstrap - loads credentials from environment
variables (via a git-ignored .env file, see ../.env.example) instead of
having them sit in inventory/*.yaml where they'd get committed.

Every script imports init_nornir() from here instead of calling
InitNornir() directly, so the credential-injection logic lives in one
place instead of being copy-pasted three times.
"""
import os
import requests
from pathlib import Path
from dotenv import load_dotenv
from nornir import InitNornir
from nornir.core import Nornir

# Load nornir/.env if present. Real env vars already set in the shell
# (e.g. by CI) take precedence and are never overwritten by the file.
load_dotenv(Path(__file__).parent.parent / ".env")


def init_nornir(config_file: str = "config.yaml") -> Nornir:
    nr = InitNornir(config_file=config_file)

    # eos and srlinux each need their own username/password (different
    # creds per platform); frr needs none (docker exec, no login).
    if "eos" in nr.inventory.groups:
        nr.inventory.groups["eos"].username = os.environ["NORNIR_EOS_USERNAME"]
        nr.inventory.groups["eos"].password = os.environ["NORNIR_EOS_PASSWORD"]

    if "srlinux" in nr.inventory.groups:
        nr.inventory.groups["srlinux"].username = os.environ["NORNIR_SRLINUX_USERNAME"]
        nr.inventory.groups["srlinux"].password = os.environ["NORNIR_SRLINUX_PASSWORD"]

    return nr


def check_jsonrpc(resp: requests.Response) -> dict:
    """Validate an SR Linux JSON-RPC response and return its parsed body.

    resp.raise_for_status() alone is NOT enough here. JSON-RPC (per the
    2.0 spec, and that's what SR Linux implements) reports success/failure
    inside the JSON body, not via the HTTP status code
    """
    resp.raise_for_status()  # still worth keeping - catches auth/network/server failures
    data = resp.json()
    if "error" in data:
        raise RuntimeError(f"SR Linux JSON-RPC error: {data['error']}")
    return data
