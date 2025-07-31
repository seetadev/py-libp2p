from starkware.crypto.signature.signature import sign

# For demo purposes — replace in real apps
PRIVATE_KEY = 123456789987654321


def create_intent(sender: str, contract_address: str, calldata: list, nonce: int):
    """
    Creates a mock Starknet transaction intent with a signature.
    """
    msg_hash = sum(map(int, calldata)) + nonce  # Simplified hash
    signature = sign(msg_hash, PRIVATE_KEY)

    return {
        "from": sender,
        "to": contract_address,
        "calldata": calldata,
        "nonce": nonce,
        "signature": {"r": signature[0], "s": signature[1]},
        "chain_id": "SN_GOERLI",
    }
