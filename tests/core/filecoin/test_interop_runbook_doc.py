from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
DOC_PATH = REPO_ROOT / "docs" / "filecoin_interop_runbook.rst"


def test_interop_runbook_covers_required_commands() -> None:
    content = DOC_PATH.read_text(encoding="utf-8")

    assert "filecoin-ping-identify-demo" in content
    assert "filecoin-pubsub-demo" in content
    assert "filecoin-dx bootstrap" in content


def test_interop_runbook_tracks_failure_modes() -> None:
    content = DOC_PATH.read_text(encoding="utf-8")

    for term in (
        "Address resolution",
        "Transport/security",
        "Identify",
        "Ping",
        "Pubsub",
    ):
        assert term in content

    assert "Failure mode:" in content
