from typing import Any

from libp2p.starknet_intents.intents import create_intent


def test_create_intent(monkeypatch: Any) -> None:
    monkeypatch.setenv(
        "STARKNET_PRIVATE_KEY",
        "0xabc123abc123abc123abc123abc123abc123abc123abc123abc123abc123abc",
    )
    intent = create_intent("0xSender", "0xContract", [1, 2], 1)
    assert intent["from"] == "0xSender"
    assert "signature" in intent
    assert "intent_metadata" in intent
