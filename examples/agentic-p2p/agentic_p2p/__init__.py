"""agentic_p2p: decentralized multi-agent app over py-libp2p.

Modules are deliberately kept single-responsibility:

- config.py     — env/config loading, nothing else
- messages.py   — wire message schemas (Pydantic)
- protocol.py   — byte framing + decode/validate/route
- peer.py       — libp2p host lifecycle, connect/send/receive (no AI code)
- llm.py        — LiteLLM access (no networking, no spreadsheet code)
- workflow.py   — SeaLion-style orchestration (planner/analyzer/writer/summarizer)
- ethercalc.py  — EtherCalc HTTP client (no AI code)
- prompts.py    — prompt templates
- agent.py      — glues the above together into Agent A / Agent B behavior
"""

__version__ = "0.1.0"
