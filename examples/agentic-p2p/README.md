# Decentralized Agentic AI with py-libp2p

A minimal, honest implementation of a **decentralized multi-agent application**:
two agents talk to each other directly over **py-libp2p** (no central HTTP
server coordinates them), one agent runs an **agentic workflow** (planner →
analyzer → spreadsheet writer → summarizer, in the spirit of a "SeaLion"
orchestration layer), calls an LLM through **LiteLLM**, and writes the
structured result into **EtherCalc**, a collaborative spreadsheet.

> **Read this before you run anything:** the source document behind this
> project explicitly calls out that SeaLion's exact API and EtherCalc's exact
> write mechanism must be verified against the versions you actually deploy.
> This repo ships with a **pluggable, honest abstraction** for both:
> - `agentic_p2p/workflow.py` defines the orchestration *shape* (Planner →
>   Analyzer → SheetWriter → Summarizer) and will use the real `sealion`
>   package if it is importable, otherwise it falls back to a local
>   orchestrator that implements the exact same interface. Nothing is faked
>   as "SeaLion" that isn't actually SeaLion.
> - `agentic_p2p/ethercalc.py` talks to EtherCalc over its documented HTTP
>   JSON API (`/_/<room>` for create, `/_/<room>/save` for bulk cell writes).
>   If your EtherCalc instance exposes a different surface, this is the one
>   file you need to touch.
>
> Treat this as a **version-correct MVP scaffold**, not a black box.

## Overview

Two independent OS processes ("Agent A" and "Agent B") are each a full
libp2p peer with their own Peer ID. Agent A takes a task from a human (CLI
argument or stdin) and ships it to Agent B over a custom libp2p protocol,
`/agent/task/1.0.0`. Agent B runs the task through its agent workflow, calls
an LLM via LiteLLM, writes the structured result to EtherCalc, and streams a
summary back to Agent A over the same libp2p connection.

There is no FastAPI/Flask server sitting between the agents. The stream *is*
the transport.

## Architecture

```
   USER
    │ task
    ▼
 AGENT A ──── /agent/task/1.0.0 (py-libp2p) ────► AGENT B
    ▲                                                  │
    │                                            workflow.py (planner →
    │                                            analyzer → writer →
    │                                            summarizer)
    │                                                  │
    │                                            llm.py (LiteLLM) ─► LLM
    │                                                  │
    │                                            ethercalc.py ─► EtherCalc
    │                                                  │
    └──────────────── Result message ◄────────────────┘
```

## Features

- Real peer-to-peer messaging over py-libp2p (custom protocol ID, no relay
  server, no central broker).
- A genuinely multi-step agent workflow (validate → plan → analyze → write
  spreadsheet → verify → summarize), not a single prompt-in/response-out call.
- LLM access abstracted behind LiteLLM so the backing model/provider is a
  config value, not a code change.
- Results persisted to a human-editable EtherCalc spreadsheet.
- Schema-validated messages (Pydantic), structured error responses, and
  retry/failure handling for LLM, EtherCalc, and network failures.
- Unit, protocol, agent, and (optional) integration tests with the LLM
  mocked out — no test hits a real model API.

## Technology Stack

| Technology | Responsibility |
|---|---|
| py-libp2p  | Agent-to-agent transport |
| SeaLion (or local fallback orchestrator with an identical interface) | Agent workflow/orchestration |
| LiteLLM    | LLM access abstraction |
| EtherCalc  | Spreadsheet UI / data collaboration |
| Python + Trio | Application logic / async execution |
| pytest + pytest-trio | Testing |

## Requirements

- Python 3.11+
- A running EtherCalc instance (local is easiest — see below)
- An API key for whatever LLM provider you point LiteLLM at (OpenAI,
  Anthropic, a local Ollama model, etc.)

## Installation

```bash
git clone <your-repo>
cd agentic-p2p

python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/macOS
source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env
# edit .env with your LLM provider/key and EtherCalc URL
```

## Environment Variables

See `.env.example`. Key ones:

| Variable | Meaning |
|---|---|
| `LIBP2P_PORT` | TCP port this peer listens on |
| `LLM_MODEL` | LiteLLM model string, e.g. `gpt-4o-mini`, `claude-sonnet-4-6`, `ollama/llama3` |
| `LLM_API_KEY` | API key for that provider |
| `LLM_API_BASE` | Optional custom base URL (e.g. local Ollama server) |
| `ETHERCALC_URL` | Base URL of your EtherCalc instance, e.g. `http://localhost:8000` |
| `ETHERCALC_SHEET` | Room/sheet name to write to |

## Running EtherCalc

The fastest path is Docker:

```bash
docker run -p 8000:8000 audreyt/ethercalc
```

Or from source, following the instructions in the
[EtherCalc repository](https://github.com/audreyt/ethercalc). Confirm the
instance is reachable at `http://localhost:8000` before starting the agents.

## Running Agent A / Agent B

Start the listener first (Agent B — the "worker"):

```bash
python run_agent.py --role responder --port 8001
```

It prints its multiaddress, e.g.:

```
Agent B listening at: /ip4/127.0.0.1/tcp/8001/p2p/12D3KooW...
```

Then start Agent A (the "requester"), pointing it at Agent B's printed
address:

```bash
python run_agent.py --role requester --port 8000 \
  --peer /ip4/127.0.0.1/tcp/8001/p2p/12D3KooW... \
  --task "Analyze this inventory: Laptop 20 units at ₹60,000, Phone 50 units at ₹20,000, Tablet 30 units at ₹30,000. Calculate total value, the highest-value product, and give recommendations."
```

## Sending a Task

You can also pipe a task in or load one from `examples/demo_task.json`:

```bash
python run_agent.py --role requester --port 8000 --peer <addr> \
  --task-file examples/demo_task.json
```

## Example Output

```
Task completed.

Total inventory value: ₹31,00,000.
Laptop has the highest inventory value.

Results were written to EtherCalc: inventory-analysis
```

EtherCalc ends up with:

| Product | Units | Unit Price | Total |
|---|---|---|---|
| Laptop | 20 | ₹60,000 | ₹12,00,000 |
| Phone | 50 | ₹20,000 | ₹10,00,000 |
| Tablet | 30 | ₹30,000 | ₹9,00,000 |
| **TOTAL** |  |  | **₹31,00,000** |

## Architecture Diagram

See `Architecture` above and the full lifecycle diagram in the original
design notes reproduced in `docs/` (if present) — or regenerate it from
`agentic_p2p/workflow.py`, which is the single source of truth for the
step order.

## Protocol Specification

- Protocol ID: `/agent/task/1.0.0`
- Wire format: newline-free, length-prefixed UTF-8 JSON (py-libp2p streams
  are byte streams — `protocol.py` handles framing).
- Message types: `task`, `result`, `error` — schemas in `messages.py`.

## Testing

```bash
pip install -r requirements.txt
pytest -q
```

- `tests/test_messages.py` — message schema validation
- `tests/test_protocol.py` — framing/encoding/decoding
- `tests/test_agent.py` — agent workflow with a mocked LLM and a mocked
  EtherCalc client (no network calls)
- `tests/test_ethercalc.py` — EtherCalc client against a mocked HTTP layer
- `tests/test_integration.py` — two in-process libp2p peers exchanging a
  real task/result over a real stream, with the LLM and EtherCalc mocked

## Security Considerations

- Incoming task payloads are treated strictly as **data**: they are
  JSON-decoded and passed through Pydantic validation before anything else
  touches them. Nothing received from the network is ever `eval`'d or
  executed.
- Oversized or malformed messages are rejected before they reach the agent
  workflow.
- LLM prompts are built from validated fields only, not raw attacker input
  concatenated unchecked into system prompts (see `prompts.py`).

## Limitations

- MVP is a single Agent A ↔ Agent B exchange. Multi-agent (A ↔ B ↔ C),
  PubSub-based task broadcasting, capability-based routing, CRDT-backed
  shared state, and QUIC transport are all deliberately out of scope (see
  Future Work) — matching the phased plan this repo was built from.
- The "SeaLion" orchestration layer ships a local fallback with the same
  interface if the real `sealion` package isn't installed/importable in
  your environment; swap it in once you've confirmed its current API.
- EtherCalc's HTTP surface varies by version/deployment; `ethercalc.py`
  isolates all of that so only one file needs to change if yours differs.

## Future Work

- PubSub topic (`agent-tasks`) so any capable agent can claim a task.
- Capability advertisement (`{"capabilities": ["data_analysis", ...]}`) and
  capability-matched routing.
- CRDT-backed shared state once agents move beyond one shared spreadsheet.
- QUIC transport once it's stable in py-libp2p (currently WIP upstream).
- Docker Compose for one-command EtherCalc + two agents.

## Demo

1. Start EtherCalc (empty spreadsheet).
2. Start Agent B (responder) — note its Peer ID / multiaddress.
3. Start Agent A (requester) pointed at Agent B, send the inventory task.
4. Watch Agent B's logs: task received → workflow running → LLM called →
   EtherCalc updated → summary sent.
5. Refresh EtherCalc — see the populated sheet.
6. Agent A prints the final summary, including the sheet name.

## Contributing

Issues and PRs welcome. Please run `pytest -q` and keep the module
boundaries in `agentic_p2p/` intact (networking code should never import
`llm.py`, and vice versa).

## License

See `LICENSE`.
