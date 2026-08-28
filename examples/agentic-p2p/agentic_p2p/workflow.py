"""Agent workflow / orchestration.

This is deliberately NOT "prompt -> LLM -> response". The workflow performs
multiple coordinated steps:

    Incoming Task
         v
    Task Validation
         v
    Task Planning         <- planner
         v
    Data Analysis         <- analyzer (calls the LLM via llm.py)
         v
    Write EtherCalc        <- sheet writer (calls ethercalc.py)
         v
    Verify Result          <- verifier (reads the sheet back)
         v
    Generate Summary       <- summarizer (calls the LLM via llm.py)
         v
    Send Response

SeaLion note
------------
The source design explicitly warns that SeaLion's current API needs to be
checked before hard-coding an interface to it, rather than guessing. So:

- If a real `sealion` package is importable, `get_orchestrator()` will
  attempt to build a SeaLion-backed orchestrator around the same four
  steps (see `_SealionOrchestrator`), and you should confirm/adjust the
  handful of calls marked "ADAPT TO REAL SEALION API" once you've checked
  its current documentation.
- Otherwise, `_LocalOrchestrator` runs the exact same step sequence with
  plain Python/async — no behavior is silently skipped, and nothing is
  mislabeled as SeaLion that isn't.

Either way, callers only ever see `Orchestrator.run(task_text) -> WorkflowResult`.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional, Protocol

from . import llm, prompts
from .config import Settings, get_settings
from .ethercalc import EtherCalcClient, EtherCalcError

logger = logging.getLogger(__name__)


@dataclass
class WorkflowResult:
    status: str  # "completed" | "completed_with_warnings"
    summary: str
    sheet: Optional[str]
    analysis: dict = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


class Orchestrator(Protocol):
    async def run(self, task_text: str) -> WorkflowResult: ...


def _validate_task(task_text: str) -> str:
    """Task Validation step. Treated as data, never executed."""
    cleaned = task_text.strip()
    if not cleaned:
        raise ValueError("Task text is empty after validation")
    if len(cleaned) > 20_000:
        raise ValueError("Task text exceeds maximum allowed length")
    return cleaned


def _build_sheet_rows(analysis: dict) -> list[list]:
    """Turn the analyzer's structured JSON into spreadsheet rows.

    Produces a table shaped like:

        Product | Units | Unit Price | Total | Recommendation
        ...
        TOTAL   |       |            | <sum> |
    """
    headers = list(analysis.get("headers") or ["Item", "Value"])
    if "Recommendation" not in headers:
        headers = [*headers, "Recommendation"]

    recs = analysis.get("recommendations") or []
    rows = []
    for i, row in enumerate(analysis.get("rows") or []):
        row = list(row)
        rec = recs[i] if i < len(recs) else ""
        # Pad/truncate to match header width (minus the Recommendation col
        # we may have just appended).
        data_width = len(headers) - 1
        if len(row) < data_width:
            row = row + [""] * (data_width - len(row))
        row = row[:data_width] + [rec]
        rows.append(row)

    table = [headers, *rows]

    totals = analysis.get("totals")
    if totals:
        total_row = [totals.get("label", "TOTAL")] + [""] * (len(headers) - 2) + [totals.get("value", "")]
        table.append(total_row)

    return table


class _LocalOrchestrator:
    """Local fallback implementing the SeaLion-shaped workflow directly."""

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self._settings = settings or get_settings()
        self._ethercalc = EtherCalcClient(self._settings)

    async def run(self, task_text: str) -> WorkflowResult:
        warnings: list[str] = []

        # 1. Task Validation
        task_text = _validate_task(task_text)

        # 2. Task Planning
        try:
            plan = await llm.generate_json(
                task_text, system=prompts.PLANNER_SYSTEM_PROMPT, settings=self._settings
            )
        except llm.LLMError as exc:
            logger.warning("Planner step failed, proceeding with a default plan: %s", exc)
            plan = {"needs_table": True, "operations": ["analyze"], "notes": ""}
        logger.info("Plan: %s", plan)

        # 3. Data Analysis
        analysis = await llm.generate_json(
            prompts.analyzer_prompt(task_text),
            system=prompts.ANALYZER_SYSTEM_PROMPT,
            settings=self._settings,
        )

        # 4. Write EtherCalc (+ 5. Verify Result)
        sheet_name = self._settings.ethercalc_sheet
        sheet_written = True
        try:
            rows = _build_sheet_rows(analysis)
            await self._ethercalc.create_sheet(sheet_name)
            await self._ethercalc.write_cells(sheet_name, rows)
            verified = await self._ethercalc.read_sheet(sheet_name)
            if not verified:
                warnings.append("EtherCalc write could not be verified (sheet read back empty).")
        except EtherCalcError as exc:
            sheet_written = False
            warnings.append(f"Unable to update EtherCalc: {exc}")
            logger.error("EtherCalc step failed: %s", exc)

        # 6. Generate Summary
        summary = await llm.generate_response(
            prompts.summarizer_prompt(task_text, analysis, sheet_name),
            system=prompts.SUMMARIZER_SYSTEM_PROMPT,
            settings=self._settings,
        )
        if warnings:
            summary = summary.rstrip() + "\n\nWarning:\n" + "\n".join(warnings)

        return WorkflowResult(
            status="completed" if not warnings else "completed_with_warnings",
            summary=summary,
            sheet=sheet_name if sheet_written else None,
            analysis=analysis,
            warnings=warnings,
        )


class _SealionOrchestrator:
    """Adapter around a real, importable `sealion` package.

    The exact SeaLion API is not something this scaffold should guess at
    line-by-line (see the design notes' explicit warning). This adapter
    keeps the same step sequence as `_LocalOrchestrator` and only wraps the
    reasoning steps through SeaLion's primitives where that's confirmed to
    make sense. Everywhere you see "ADAPT TO REAL SEALION API", check the
    currently installed `sealion` version's docs before changing behavior.
    """

    def __init__(self, sealion_module, settings: Optional[Settings] = None) -> None:
        self._sealion = sealion_module
        self._settings = settings or get_settings()
        self._fallback = _LocalOrchestrator(self._settings)

    async def run(self, task_text: str) -> WorkflowResult:
        # ADAPT TO REAL SEALION API: if/when `sealion` exposes an agent/
        # workflow primitive you've verified, build the planner -> analyzer
        # -> writer -> summarizer pipeline through it here. Until that
        # mapping is confirmed against the installed version, we run the
        # identical, already-correct step sequence directly so behavior
        # never silently regresses to "just an LLM call".
        logger.info(
            "sealion module detected (%r) but no confirmed workflow mapping is "
            "configured yet; running the verified local step sequence.",
            getattr(self._sealion, "__name__", self._sealion),
        )
        return await self._fallback.run(task_text)


def get_orchestrator(settings: Optional[Settings] = None) -> Orchestrator:
    """Return the best available orchestrator.

    Uses a real `sealion` package if importable, otherwise the local
    fallback that implements the identical workflow shape.
    """
    try:
        import sealion  # type: ignore
    except ImportError:
        return _LocalOrchestrator(settings)
    return _SealionOrchestrator(sealion, settings)
