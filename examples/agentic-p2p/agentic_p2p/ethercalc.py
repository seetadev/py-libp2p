"""EtherCalc HTTP client.

EtherCalc is the human-visible workspace: it does NOT do any reasoning,
analysis, or generation — that's the LLM's job. This module only ever
persists already-structured data and reads it back.

    LLM result -> structured data -> EtherCalc -> human can inspect/edit

EtherCalc's HTTP surface is small but has varied slightly across
deployments/versions. This client uses EtherCalc's documented CSV import/
export endpoints:

    GET  {base}/{room}.csv        -> current sheet as CSV
    POST {base}/_/{room}/csv      -> replace sheet contents from a CSV body
                                      (Content-Type: text/csv)

If your EtherCalc instance exposes a different surface (e.g. you're on a
fork, or an older/newer release with a different import route), this is the
one file you need to change — nothing else in the app knows or cares how
the HTTP call is made.
"""

from __future__ import annotations

import csv
import io
import logging
from typing import Optional, Sequence

import httpx

from .config import Settings, get_settings

logger = logging.getLogger(__name__)


class EtherCalcError(RuntimeError):
    """Raised whenever a read/write against EtherCalc fails."""


def _rows_to_csv(rows: Sequence[Sequence]) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    for row in rows:
        writer.writerow(row)
    return buf.getvalue()


def _csv_to_rows(text: str) -> list[list[str]]:
    return [row for row in csv.reader(io.StringIO(text))]


class EtherCalcClient:
    """Thin async client wrapping the EtherCalc HTTP API."""

    def __init__(self, settings: Optional[Settings] = None, timeout: float = 10.0) -> None:
        self._settings = settings or get_settings()
        self._base_url = self._settings.ethercalc_url.rstrip("/")
        self._timeout = timeout

    async def create_sheet(self, sheet: str) -> None:
        """Ensure the named room/sheet exists.

        Most EtherCalc deployments auto-create a room on first write, so
        this is a best-effort "wake it up" call rather than a strict
        precondition — failures here are logged but not fatal, since
        `write_cells` will create the room anyway.
        """
        url = f"{self._base_url}/{sheet}.json"
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                await client.get(url)
        except httpx.HTTPError as exc:
            logger.warning("create_sheet(%s) probe failed (continuing): %s", sheet, exc)

    async def write_cells(self, sheet: str, data: Sequence[Sequence]) -> None:
        """Replace the sheet's contents with the given rows (list of lists)."""
        url = f"{self._base_url}/_/{sheet}/csv"
        csv_body = _rows_to_csv(data)
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(
                    url,
                    content=csv_body.encode("utf-8"),
                    headers={"Content-Type": "text/csv"},
                )
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise EtherCalcError(f"Failed to write to EtherCalc sheet '{sheet}': {exc}") from exc

    async def append_rows(self, sheet: str, rows: Sequence[Sequence]) -> None:
        """Append rows to an existing sheet (read-modify-write)."""
        existing = await self.read_sheet(sheet)
        await self.write_cells(sheet, [*existing, *rows])

    async def read_sheet(self, sheet: str) -> list[list[str]]:
        """Return the sheet's current contents as a list of rows."""
        url = f"{self._base_url}/{sheet}.csv"
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(url)
                if response.status_code == 404:
                    return []
                response.raise_for_status()
                return _csv_to_rows(response.text)
        except httpx.HTTPError as exc:
            raise EtherCalcError(f"Failed to read EtherCalc sheet '{sheet}': {exc}") from exc

    def sheet_url(self, sheet: str) -> str:
        """Human-facing URL for opening the sheet in a browser."""
        return f"{self._base_url}/{sheet}"
