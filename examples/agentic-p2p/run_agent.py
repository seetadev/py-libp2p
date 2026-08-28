#!/usr/bin/env python
"""CLI entrypoint.

Start a responder ("Agent B", the worker that runs the workflow):

    python run_agent.py --role responder --port 8001

Start a requester ("Agent A") pointed at a running responder:

    python run_agent.py --role requester --port 8000 \\
        --peer /ip4/127.0.0.1/tcp/8001/p2p/12D3KooW... \\
        --task "Analyze this inventory: ..."

Or load the task from a JSON file (see examples/demo_task.json):

    python run_agent.py --role requester --port 8000 --peer <addr> \\
        --task-file examples/demo_task.json
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

import trio

from agentic_p2p.agent import Agent
from agentic_p2p.config import get_settings
from agentic_p2p.messages import ErrorMessage
from agentic_p2p.peer import AgentPeer


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a decentralized agent peer.")
    parser.add_argument("--role", choices=["requester", "responder"], required=True)
    parser.add_argument("--port", type=int, default=0, help="TCP port to listen on")
    parser.add_argument("--peer", help="Multiaddress of the responder (requester only)")
    parser.add_argument("--task", help="Task text to send (requester only)")
    parser.add_argument(
        "--task-file", type=Path, help="JSON file with a {'task': '...'} field (requester only)"
    )
    return parser.parse_args(argv)


def _load_task_text(args: argparse.Namespace) -> str:
    if args.task:
        return args.task
    if args.task_file:
        data = json.loads(args.task_file.read_text(encoding="utf-8"))
        return data["task"]
    print("Reading task from stdin (Ctrl+D to send)...", file=sys.stderr)
    return sys.stdin.read()


async def run_responder(port: int) -> None:
    peer = AgentPeer(port=port)
    agent = Agent(peer)
    async with peer.start(on_stream=agent.on_inbound_stream):
        print(f"Agent B listening at: {peer.listen_addresses()[0]}")
        print(f"Peer ID: {peer.peer_id}")
        print("Waiting for tasks... (Ctrl+C to stop)")
        await trio.sleep_forever()


async def run_requester(port: int, peer_addr: str, task_text: str) -> None:
    if not peer_addr:
        raise SystemExit("--peer is required for --role requester")

    peer = AgentPeer(port=port)
    agent = Agent(peer)
    async with peer.start():
        print(f"Agent A Peer ID: {peer.peer_id}")
        remote_peer_id = await peer.connect_to_peer(peer_addr)
        print(f"Connected to Agent B: {remote_peer_id}")
        print("Sending task...")

        reply = await agent.send_task(remote_peer_id, task_text)

        if isinstance(reply, ErrorMessage):
            print(f"\nTask failed: {reply.error}")
        else:
            print(f"\nTask completed.\n\n{reply.summary}")
            if reply.sheet:
                settings = get_settings()
                print(f"\nSpreadsheet: {reply.sheet}")
                print(f"View it at: {settings.ethercalc_url.rstrip('/')}/{reply.sheet}")


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    logging.basicConfig(
        level=get_settings().log_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    if args.role == "responder":
        trio.run(run_responder, args.port)
    else:
        task_text = _load_task_text(args)
        trio.run(run_requester, args.port, args.peer, task_text)


if __name__ == "__main__":
    main()
