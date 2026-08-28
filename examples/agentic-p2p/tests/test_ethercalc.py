import httpx
import pytest

from agentic_p2p.config import Settings
from agentic_p2p.ethercalc import EtherCalcClient, EtherCalcError


class _FakeResponse:
    def __init__(self, status_code=200, text=""):
        self.status_code = status_code
        self.text = text

    def raise_for_status(self):
        if self.status_code >= 400:
            request = httpx.Request("GET", "http://testserver")
            raise httpx.HTTPStatusError(
                "error", request=request, response=httpx.Response(self.status_code, request=request)
            )


class _FakeAsyncClient:
    """Records calls and returns pre-programmed responses."""

    responses: dict[str, _FakeResponse] = {}
    calls: list[tuple[str, str, bytes | None]] = []

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def get(self, url, **kwargs):
        _FakeAsyncClient.calls.append(("GET", url, None))
        return _FakeAsyncClient.responses.get(url, _FakeResponse(200, ""))

    async def post(self, url, content=None, **kwargs):
        _FakeAsyncClient.calls.append(("POST", url, content))
        return _FakeAsyncClient.responses.get(url, _FakeResponse(200, ""))


@pytest.fixture(autouse=True)
def _reset_fake_client():
    _FakeAsyncClient.responses = {}
    _FakeAsyncClient.calls = []
    yield


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr("agentic_p2p.ethercalc.httpx.AsyncClient", _FakeAsyncClient)
    settings = Settings(ethercalc_url="http://ethercalc.test", ethercalc_sheet="demo")
    return EtherCalcClient(settings=settings)


async def test_write_cells_posts_csv(client):
    await client.write_cells("demo", [["Product", "Total"], ["Laptop", 1200000]])
    assert _FakeAsyncClient.calls[0][0] == "POST"
    assert _FakeAsyncClient.calls[0][1] == "http://ethercalc.test/_/demo/csv"
    body = _FakeAsyncClient.calls[0][2].decode("utf-8")
    assert "Product,Total" in body
    assert "Laptop,1200000" in body


async def test_read_sheet_parses_csv(client):
    _FakeAsyncClient.responses["http://ethercalc.test/demo.csv"] = _FakeResponse(
        200, "Product,Total\r\nLaptop,1200000\r\n"
    )
    rows = await client.read_sheet("demo")
    assert rows == [["Product", "Total"], ["Laptop", "1200000"]]


async def test_read_sheet_returns_empty_on_404(client):
    _FakeAsyncClient.responses["http://ethercalc.test/demo.csv"] = _FakeResponse(404, "")
    rows = await client.read_sheet("demo")
    assert rows == []


async def test_write_cells_raises_ethercalc_error_on_failure(client):
    _FakeAsyncClient.responses["http://ethercalc.test/_/demo/csv"] = _FakeResponse(500, "")
    with pytest.raises(EtherCalcError):
        await client.write_cells("demo", [["a", "b"]])


async def test_append_rows_reads_then_writes(client):
    _FakeAsyncClient.responses["http://ethercalc.test/demo.csv"] = _FakeResponse(
        200, "Product,Total\r\nLaptop,1200000\r\n"
    )
    await client.append_rows("demo", [["Phone", 1000000]])

    write_call = [c for c in _FakeAsyncClient.calls if c[0] == "POST"][0]
    body = write_call[2].decode("utf-8")
    assert "Laptop,1200000" in body
    assert "Phone,1000000" in body


def test_sheet_url(client):
    assert client.sheet_url("demo") == "http://ethercalc.test/demo"
