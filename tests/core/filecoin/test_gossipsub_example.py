def test_gossipsub_example_importable() -> None:
    from examples.filecoin import filecoin_gossipsub_example

    assert hasattr(filecoin_gossipsub_example, "run")
    assert hasattr(filecoin_gossipsub_example, "build_parser")
