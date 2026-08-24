# Agentic AI Application with py-libp2p, SeaLion, LiteLLM, and EtherCalc Integration

A Peer-to-Peer multi-agent AI application that combines **py-libp2p**, **SEA-LION**, **LiteLLM**, **Ollama/Gemma 3:1B**, and **EtherCalc**.

## Project Structure

The Python modules provide reusable components for building P2P multi-agent AI system with decentralized agent communication. 

`main.py` is a sample implementation that demonstrates how these components can be composed into a three-agent workflow using SEA-LION, libp2p, LiteLLM, and EtherCalc.

```text
project/
├── agent.py
├── config.py
├── ethercalc.py
├── llm.py
├── orchestrator.py
├── p2p_network.py
├── protocol.py
├── state.py
├── requirements.txt
└── main.py
```

## Goals

This project demonstrates:

* Setting up `py-libp2p` nodes for P2P messaging between AI agents.
* Integrating SEA-LION for AI-agent orchestration.
* Using LiteLLM as the LLM interface.
* Running local models through Ollama.
* Using Gemma 3:1B to power the individual agents.
* Using EtherCalc for spreadsheet-based logging and visualization of agent activity.
* Sharing agent operations and workflow results between peers using py-libp2p.
* Implementing a sample P2P agent-to-agent request.
* Running a multi-agent workflow consisting of risk analysis, implementation, and validation.


## What Each Technology Contributes

| Technology         | Role in this project                                             |
| ------------------ | ---------------------------------------------------------------- |
| **py-libp2p**      | Provides P2P networking and communication between agents         |
| **SEA-LION**       | Acts as the orchestration controller that selects the next agent |
| **LiteLLM**        | Provides the unified LLM API used by the application             |
| **Ollama**         | Runs the models locally                                          |
| **SEA-LION model** | Provides orchestration/routing decisions                         |
| **Gemma 3:1B**     | Provides reasoning/generation for all worker agents              |
| **EtherCalc**      | Provides a shared spreadsheet for recording agent activity       |
| **Trio**           | Provides asynchronous execution and concurrency                  |
| **Multiaddr**      | Represents libp2p network addresses                              |
| **HTTPX**          | Sends HTTP requests to EtherCalc                                 |


# Example Agent Configuration: 

The sample implementation runs three AI agents as independent `py-libp2p` peers. A SEA-LION LLM-based orchestration controller decides which agent should act next, while LiteLLM provides a common interface to the locally hosted LLMs through Ollama. Agent outputs are synchronized between peers using libp2p and recorded in an EtherCalc spreadsheet.

## Part 1: Architecture

```text
                         ┌─────────────────────────┐
                         │    SEA-LION Controller  │
                         │                         │
                         │    Selects next agent   │
                         │   based on workflow     │
                         │          state          │
                         └────────────┬────────────┘
                                      │
                                      ▼
                              Selected Agent
                                      │
                           ┌──────────┴──────────┐
                           │                     │
                          P2P                   P2P
                           │                     │
                           ▼         P2P         ▼
                       Other Agent <────────> Other Agent
                           │                     │
                           │                     │
                           └──────────┬──────────┘
                                      │
                           Agent operations/results
                                      │
                                      ▼
                               ┌─────────────┐
                               │  EtherCalc  │
                               │   Shared    │
                               │ Spreadsheet │
                               └─────────────┘
```

## Part 2: Components

### 1. py-libp2p — Agent-to-Agent Communication

`py-libp2p` provides the peer-to-peer networking layer.

Each agent runs its own libp2p host:

```text
Agent 1 → TCP 9101
Agent 2 → TCP 9102
Agent 3 → TCP 9103
```

The application defines a custom protocol:

```text
/sea-lion-multi-agent/1.0.0
```
Each peer can establish a stream to another peer and exchange JSON messages.

### 2. SEA-LION — Orchestration

SEA-LION is used as the orchestration controller.

The controller receives the current workflow state and asks the SEA-LION model which agent should act next:

```text
agent1
agent2
agent3
done
```

The controller uses workflow state to prevent repeatedly selecting agents whose required stage has already been completed.

### 3. LiteLLM — LLM Interface

LiteLLM provides a common API interface between the application and the LLM backend.

The project uses:

```python
from litellm import acompletion
```

and sends requests using:

```text
ollama/<model-name>
```

The application therefore does not need to implement a separate LLM client for each model provider.

In this project, LiteLLM connects the Python application to Ollama:

```text
Python application
       │
       ▼
    LiteLLM
       │
       ▼
     Ollama
       │
       ▼
     Model
```

The implementation uses LiteLLM for both the SEA-LION orchestration model and the worker-agent model.

### 4. Ollama — Local Model Runtime

Ollama runs the models locally.

The project uses two models:

```text
SEA-LION:
aisingapore/Llama-SEA-LION-v3.5-8B-R:latest

Worker agents:
gemma3:1b
```

These are configured in the application as:

```python
ORCHESTRATOR_MODEL = "aisingapore/Llama-SEA-LION-v3.5-8B-R:latest"
AGENT_MODEL = "gemma3:1b"
```

The Ollama API is accessed through:

```text
http://127.0.0.1:11434
```

### 5. Gemma 3:1B — Worker Agent LLM

`gemma3:1b` is the LLM used by the three worker agents.

Each agent has a different persona:

**Agent 1 — Risk Analysis**

Identifies:

* Risks
* Assumptions
* Weaknesses
* Edge cases
* Vulnerabilities
* Failure modes

**Agent 2 — Implementation**

Converts Agent 1's identified risks into:

* Practical implementation solutions
* Trade-offs
* Engineering approaches

**Agent 3 — Validation**

Reviews the previous contributions and checks:

* Inconsistencies
* Missing requirements
* Unresolved risks
* Incorrect implementation assumptions
* Remaining weaknesses
* Whether the solution satisfies the objective

The personas are explicitly defined in the application.

All three worker agents use the same `gemma3:1b` LLM, but their system prompts give them different responsibilities.

### 6. EtherCalc — Agent Activity Logging

EtherCalc provides a shared spreadsheet where agent activity is recorded.

The application uses:

```text
http://127.0.0.1:8000
```

with the room:

```text
sea-lion-agent-collaboration
```

When an agent produces an operation, the application writes a CSV row containing:

```text
Turn
Agent
Role
Request
Response
```

to the EtherCalc room.

This provides a simple human-readable record of the multi-agent workflow.

---

## Part 3: Prerequisites

Install the following:

* Python 3
* Git
* Ollama
* Docker
* EtherCalc
* An Ollama-compatible machine capable of running the selected models

Clone the repository:

```bash
git clone https://github.com/abdullah-Ikram-0599/Agentic-AI-Application-with-py-libp2p-SeaLion-LiteLLM-EtherCalc-Integration.git

cd Agentic-AI-Application-with-py-libp2p-SeaLion-LiteLLM-EtherCalc-Integration
```

### 1. Install Python Dependencies

Create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install the project dependencies:

```bash
pip install -r requirements.txt
```

---

### 2. Start Ollama

Install Ollama if it is not already installed.

Start the Ollama server:

```bash
ollama serve
```

The application expects Ollama to be available at:

```text
http://127.0.0.1:11434
```

Keep Ollama running while executing the application.

---

### 3. Pull the Models

Pull the SEA-LION orchestration model:

```bash
ollama pull aisingapore/Llama-SEA-LION-v3.5-8B-R:latest
```
Pull Gemma 3:1B:

```bash
ollama pull gemma3:1b
```

Verify that both models are available:

```bash
ollama list
```

---

### 4. Start EtherCalc:

Start EtherCalc using: 

```text
ethercalc
```

The application expects EtherCalc to be available at:

```text
http://127.0.0.1:8000
```

Start an EtherCalc instance on port `8000`.

The application uses the following room:

```text
sea-lion-agent-collaboration
```

The resulting spreadsheet can be accessed at:

```text
http://localhost:8000/sea-lion-agent-collaboration
```

The application automatically appends agent operations to this room.

---

### 5. Run Locally

With Ollama and EtherCalc running, start the application:

```bash
python3 main.py
```

---

### 6. Docker

The project can also be run using the published Docker image.

Pull the image:

```bash
docker pull abdullahikram/sealion-multi-agent-ethercalc-pylibp2p-litellm:latest
```

Run it:

```bash
docker run --rm \
  -p 9101:9101 \
  -p 9102:9102 \
  -p 9103:9103 \
  abdullahikram/sealion-multi-agent-ethercalc-pylibp2p-litellm:latest
```

The three ports correspond to the three libp2p agents:

```text
9101 → Agent 1
9102 → Agent 2
9103 → Agent 3
```
