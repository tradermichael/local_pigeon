"""WireGuard mesh bootstrap stubs for BOTF enterprise networking."""

from __future__ import annotations

import base64
import secrets
import subprocess
from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass
class WireGuardKeyPair:
    private_key: str
    public_key: str


def _botf_config_path() -> Path:
    return Path.home() / ".botf" / "config.yaml"


def generate_wireguard_keypair() -> WireGuardKeyPair:
    """Generate WireGuard key pair using wg CLI (with fallback)."""
    try:
        private_key = subprocess.check_output(["wg", "genkey"], text=True).strip()
        public_key = subprocess.check_output(
            ["wg", "pubkey"],
            input=private_key,
            text=True,
        ).strip()
        if private_key and public_key:
            return WireGuardKeyPair(private_key=private_key, public_key=public_key)
    except Exception:
        pass

    # Fallback stub key generation if wg is unavailable.
    # This keeps plumbing functional until system package is installed.
    private_key = base64.b64encode(secrets.token_bytes(32)).decode("utf-8")
    public_key = base64.b64encode((private_key + "-pub").encode("utf-8")).decode("utf-8")[:44]
    return WireGuardKeyPair(private_key=private_key, public_key=public_key)


def ensure_wireguard_identity(enable_mesh: bool = False) -> dict[str, str]:
    """Create/read WireGuard identity and persist state in ~/.botf/config.yaml."""
    config_path = _botf_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)

    config: dict = {}
    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f) or {}
        except Exception:
            config = {}

    mesh = config.get("mesh", {})
    if not isinstance(mesh, dict):
        mesh = {}

    if not mesh.get("public_key") or not mesh.get("private_key"):
        keypair = generate_wireguard_keypair()
        mesh["public_key"] = keypair.public_key
        mesh["private_key"] = keypair.private_key

    mesh["enabled"] = bool(enable_mesh)
    config["mesh"] = mesh

    with open(config_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(config, f, sort_keys=False)

    return {
        "config_path": str(config_path),
        "public_key": str(mesh.get("public_key", "")),
        "enabled": str(bool(mesh.get("enabled", False))).lower(),
    }
