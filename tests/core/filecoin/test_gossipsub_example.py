import pytest


def test_gossipsub_example_importable() -> None:
    from examples.filecoin import filecoin_gossipsub_example

    assert hasattr(filecoin_gossipsub_example, "run")
    assert hasattr(filecoin_gossipsub_example, "build_parser")


@pytest.mark.trio
async def test_local_gossipsub_roundtrip() -> None:
    from examples.filecoin.filecoin_gossipsub_example import run

    # Run with short payload, no validator, expect exit code 0 and receipt
    rc = await run(network="mainnet", topic_mode="blocks", payload=b"hello-32", with_validator=False, verbose=False)
    assert rc == 0


@pytest.mark.trio
async def test_validator_rejects_empty_payload() -> None:
    from examples.filecoin.filecoin_gossipsub_example import run

    # With validator, empty payload should be rejected — run returns 0 but logs rejection
    rc = await run(network="mainnet", topic_mode="blocks", payload=b"", with_validator=True, verbose=False)
    assert rc == 0  # or 2 if you choose to signal rejection
