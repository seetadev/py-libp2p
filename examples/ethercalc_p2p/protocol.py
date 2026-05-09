"""
Spreadsheet operation protocol for P2PCalc.

All cell edits and sheet commands are encoded as JSON messages that travel
over the libp2p GossipSub topic ``spreadsheet-updates``.  The schema is
intentionally minimal for the PoC; it will grow to support formulas,
row/column mutations, and CRDT vector clocks in follow-up work.
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class OpType(str, Enum):
    SET_CELL = "SET_CELL"
    SET_FORMULA = "SET_FORMULA"
    INSERT_ROW = "INSERT_ROW"
    DELETE_ROW = "DELETE_ROW"
    INSERT_COL = "INSERT_COL"
    DELETE_COL = "DELETE_COL"
    FORMAT_CELL = "FORMAT_CELL"
    # Sent by a new peer to request a state snapshot from existing peers
    REQUEST_STATE = "REQUEST_STATE"
    # Response carrying the full current state (JSON-encoded cell map)
    STATE_SNAPSHOT = "STATE_SNAPSHOT"


@dataclass
class SpreadsheetOp:
    op_id: str
    peer_id: str
    timestamp: float
    sheet_id: str
    op_type: str
    payload: dict[str, Any]

    # ---- helpers ----

    @staticmethod
    def make(
        peer_id: str,
        sheet_id: str,
        op_type: OpType,
        payload: dict[str, Any],
    ) -> "SpreadsheetOp":
        return SpreadsheetOp(
            op_id=str(uuid.uuid4()),
            peer_id=peer_id,
            timestamp=time.time(),
            sheet_id=sheet_id,
            op_type=op_type.value,
            payload=payload,
        )

    def encode(self) -> bytes:
        return json.dumps(asdict(self)).encode()

    @staticmethod
    def decode(data: bytes) -> "SpreadsheetOp":
        d = json.loads(data)
        return SpreadsheetOp(**d)


# ---- convenient constructors for each op type ----

def set_cell(peer_id: str, sheet_id: str, cell: str, value: str) -> SpreadsheetOp:
    return SpreadsheetOp.make(
        peer_id, sheet_id, OpType.SET_CELL, {"cell": cell, "value": value}
    )


def set_formula(peer_id: str, sheet_id: str, cell: str, formula: str) -> SpreadsheetOp:
    return SpreadsheetOp.make(
        peer_id, sheet_id, OpType.SET_FORMULA, {"cell": cell, "formula": formula}
    )


def format_cell(
    peer_id: str, sheet_id: str, cell: str, fmt: dict[str, Any]
) -> SpreadsheetOp:
    return SpreadsheetOp.make(
        peer_id, sheet_id, OpType.FORMAT_CELL, {"cell": cell, "format": fmt}
    )


def request_state(peer_id: str, sheet_id: str) -> SpreadsheetOp:
    return SpreadsheetOp.make(peer_id, sheet_id, OpType.REQUEST_STATE, {})


def state_snapshot(
    peer_id: str, sheet_id: str, cells: dict[str, str]
) -> SpreadsheetOp:
    return SpreadsheetOp.make(
        peer_id, sheet_id, OpType.STATE_SNAPSHOT, {"cells": cells}
    )
