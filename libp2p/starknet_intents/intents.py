import hashlib
import os
import time
from typing import Any

from starkware.crypto.signature.signature import sign


def get_private_key() -> int:
    key_str = os.getenv("STARKNET_PRIVATE_KEY")
    if key_str is None:
        raise OSError("STARKNET_PRIVATE_KEY environment variable not set.")
    return int(key_str, 16)


def generate_hashlock_secret() -> tuple[int, str]:
    """
    Generates a preimage and its hash for atomic swap coordination.
    Returns both the preimage as int and its SHA-256 hash as hex string.
    """
    secret = os.urandom(32)
    preimage = int.from_bytes(secret, "big")
    hashlock = hashlib.sha256(secret).hexdigest()
    return preimage, hashlock


def create_intent(
    sender: str,
    contract_address: str,
    calldata: list[int],
    nonce: int,
    chain_id: str = "SN_GOERLI",
    timelock_seconds: int = 3600,
    private_key: int | None = None,
    hashlock: str | None = None,
) -> dict[str, Any]:
    """
    Creates a Starknet transaction intent with signature, plus atomic swap metadata.

    Args:
        sender: Sender address
        contract_address: Target contract
        calldata: Calldata for transaction
        nonce: Starknet transaction nonce
        chain_id: Network chain ID
        timelock_seconds: Time until refund allowed
        private_key: Signing key, optional
        hashlock: Optional external hashlock

    Returns:
        Structured intent dict.

    """
    if private_key is None:
        private_key = get_private_key()

    if hashlock is None:
        _, hashlock = generate_hashlock_secret()

    msg_hash = sum(calldata) + nonce
    r, s = sign(msg_hash, private_key)

    return {
        "from": sender,
        "to": contract_address,
        "calldata": calldata,
        "nonce": nonce,
        "signature": {"r": r, "s": s},
        "chain_id": chain_id,
        "intent_metadata": {
            "type": "cross_chain_swap",
            "hashlock": hashlock,
            "timelock": int(time.time()) + timelock_seconds,
            "created_at": int(time.time()),
        },
    }
