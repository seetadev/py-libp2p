import os
from typing import Any

from starkware.crypto.signature.signature import sign


def get_private_key() -> int:
    """
    Fetch the Starknet private key from environment variable for security.
    Raises error if not set.
    """
    key_str = os.getenv("STARKNET_PRIVATE_KEY")
    if key_str is None:
        raise OSError("STARKNET_PRIVATE_KEY environment variable not set.")
    return int(key_str)


def create_intent(
    sender: str,
    contract_address: str,
    calldata: list[int],
    nonce: int,
    private_key: int | None = None,
    chain_id: str = "SN_GOERLI",
) -> dict[str, Any]:
    """
    Creates a Starknet transaction intent with a signature.

    Args:
        sender (str): Address of the sender.
        contract_address (str): Address of the target contract.
        calldata (List[int]): Call data for the transaction.
        nonce (int): Transaction nonce.
        private_key (Optional[int]): Starknet private key.
        If not provided, will be fetched from env.
        chain_id (str): Starknet chain ID. Default is "SN_GOERLI".

    Returns:
        Dict[str, Any]: The signed intent dictionary.

    """
    if private_key is None:
        private_key = get_private_key()

    msg_hash = sum(calldata) + nonce
    signature = sign(msg_hash, private_key)

    return {
        "from": sender,
        "to": contract_address,
        "calldata": calldata,
        "nonce": nonce,
        "signature": {"r": signature[0], "s": signature[1]},
        "chain_id": chain_id,
    }
