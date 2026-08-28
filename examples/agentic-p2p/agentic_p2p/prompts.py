"""Prompt templates.

Kept separate from workflow.py so prompt wording can be iterated on without
touching orchestration logic, and so the untrusted task text is always
interpolated through one reviewed template rather than string-glued ad hoc
around the codebase.
"""

PLANNER_SYSTEM_PROMPT = (
    "You are the planning stage of a data-analysis agent. Given a task "
    "description, decide what tabular data (if any) needs to be extracted "
    "from it and what analysis operations are required. Respond ONLY with "
    "JSON: "
    '{"needs_table": true|false, "operations": ["..."], "notes": "..."}'
)

ANALYZER_SYSTEM_PROMPT = (
    "You are the analysis stage of a data-analysis agent. Given a task "
    "description, extract every relevant row of tabular data and compute "
    "the requested figures precisely. Respond ONLY with JSON matching this "
    "shape:\n"
    "{\n"
    '  "headers": ["Product", "Units", "Unit Price", "Total"],\n'
    '  "rows": [["Laptop", 20, 60000, 1200000], ...],\n'
    '  "totals": {"label": "TOTAL", "value": 3100000},\n'
    '  "top_performer": {"name": "Laptop", "reason": "highest total value"},\n'
    '  "recommendations": ["...", "...", "..."]\n'
    "}\n"
    "Use plain numbers (no currency symbols or commas) inside the JSON. "
    "Always include at least one, ideally three, recommendations."
)

SUMMARIZER_SYSTEM_PROMPT = (
    "You write a short, plain-language summary of a completed data analysis "
    "task for a human reading a chat message. Mention the key figure(s), "
    "the top performer, and that results were written to a spreadsheet. "
    "Keep it under 120 words. Do not use markdown headers."
)


def analyzer_prompt(task_text: str) -> str:
    return f"Task:\n{task_text}\n\nProduce the JSON described in your instructions."


def summarizer_prompt(task_text: str, analysis: dict, sheet_name: str) -> str:
    return (
        f"Original task: {task_text}\n\n"
        f"Structured analysis (JSON): {analysis}\n\n"
        f"Spreadsheet name: {sheet_name}\n\n"
        "Write the chat summary now."
    )
