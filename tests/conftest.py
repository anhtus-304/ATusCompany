import pytest


@pytest.fixture(autouse=True)
def _isolated_delivery(tmp_path, monkeypatch):
    """Deploys, outbox and pushes never touch the real workspace or network during tests."""
    monkeypatch.setenv("VTD_DEPLOYS", str(tmp_path / "deploys"))
    monkeypatch.setenv("VTD_OUTBOX", str(tmp_path / "outbox"))
    monkeypatch.delenv("VTD_SMTP_HOST", raising=False)
    monkeypatch.delenv("VTD_GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("VTD_GITHUB_URL", raising=False)
