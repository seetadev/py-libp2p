"""
In-memory spreadsheet state with last-write-wins conflict resolution.

Each peer maintains its own ``SheetState``.  When a remote ``SET_CELL``
arrives with a newer timestamp the local value is overwritten; older
messages are silently dropped, preventing causal inversions.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from .protocol import OpType, SpreadsheetOp

logger = logging.getLogger(__name__)


@dataclass
class CellEntry:
    value: str
    timestamp: float
    peer_id: str


class SheetState:
    def __init__(self, sheet_id: str) -> None:
        self.sheet_id = sheet_id
        # cell address → CellEntry
        self._cells: dict[str, CellEntry] = {}
        # op_ids we have already applied (dedup guard)
        self._seen: set[str] = set()

    # ---- public API ----

    def apply(self, op: SpreadsheetOp) -> bool:
        """
        Apply an incoming operation.  Returns True when the state changed,
        False when the message was a duplicate or was lost to LWW.
        """
        if op.op_id in self._seen:
            return False
        self._seen.add(op.op_id)

        if op.op_type == OpType.SET_CELL:
            return self._apply_set_cell(op)
        if op.op_type == OpType.SET_FORMULA:
            return self._apply_set_cell(op, key="formula")
        if op.op_type == OpType.STATE_SNAPSHOT:
            return self._apply_snapshot(op)

        logger.debug("Unhandled op type %s — skipping", op.op_type)
        return False

    def snapshot(self) -> dict[str, str]:
        """Return the current cell map as {address: value}."""
        return {addr: e.value for addr, e in self._cells.items()}

    def get(self, cell: str) -> str | None:
        entry = self._cells.get(cell)
        return entry.value if entry else None

    # ---- internals ----

    def _apply_set_cell(self, op: SpreadsheetOp, key: str = "value") -> bool:
        cell = op.payload.get("cell", "")
        value = op.payload.get(key, op.payload.get("value", ""))
        existing = self._cells.get(cell)
        if existing and existing.timestamp >= op.timestamp:
            logger.debug(
                "LWW: dropping stale %s for %s (remote ts=%.3f local ts=%.3f)",
                op.op_type,
                cell,
                op.timestamp,
                existing.timestamp,
            )
            return False
        self._cells[cell] = CellEntry(
            value=value, timestamp=op.timestamp, peer_id=op.peer_id
        )
        logger.info("Applied %s: %s = %r (from %s)", op.op_type, cell, value, op.peer_id[:8])
        return True

    def _apply_snapshot(self, op: SpreadsheetOp) -> bool:
        cells: dict[str, str] = op.payload.get("cells", {})
        changed = False
        for cell, value in cells.items():
            fake_entry = CellEntry(value=value, timestamp=op.timestamp, peer_id=op.peer_id)
            existing = self._cells.get(cell)
            if not existing or existing.timestamp < op.timestamp:
                self._cells[cell] = fake_entry
                changed = True
        logger.info("Applied STATE_SNAPSHOT: %d cells from %s", len(cells), op.peer_id[:8])
        return changed
