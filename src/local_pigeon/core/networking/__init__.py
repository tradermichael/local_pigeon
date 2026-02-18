"""Networking primitives for optional mesh/federation features."""

from local_pigeon.core.networking.wireguard import (
    WireGuardKeyPair,
    ensure_wireguard_identity,
    generate_wireguard_keypair,
)

__all__ = [
    "WireGuardKeyPair",
    "generate_wireguard_keypair",
    "ensure_wireguard_identity",
]
