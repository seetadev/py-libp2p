import argparse
import json
import logging
import time

import multiaddr
import trio

from libp2p import new_host
from libp2p.crypto.rsa import create_new_key_pair
from libp2p.custom_types import TProtocol
from libp2p.peer.peerinfo import info_from_p2p_addr
from libp2p.pubsub.gossipsub import GossipSub
from libp2p.pubsub.pubsub import Pubsub
from libp2p.stream_muxer.mplex.mplex import MPLEX_PROTOCOL_ID, Mplex
from libp2p.tools.anyio_service import background_trio_service
from libp2p.utils.address_validation import find_free_port

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("ai-agent")

TASK_TOPIC = "agent/tasks/v1"
RESPONSE_TOPIC = "agent/responses/v1"
GOSSIPSUB_PROTOCOL_ID = TProtocol("/meshsub/1.0.0")

key_pair = create_new_key_pair()


def process_task(task: str, worker_id: str) -> str:
    task_lower = task.lower()

    if any(w in task_lower for w in ["summarize", "summary", "tldr"]):
        return f"[{worker_id}] Summary complete. Key points extracted and condensed from input."
    elif any(w in task_lower for w in ["translate", "language"]):
        return f"[{worker_id}] Translation done. Source parsed, target schema applied."
    elif any(w in task_lower for w in ["analyse", "analyze", "analysis"]):
        return f"[{worker_id}] Analysis done. Patterns identified. Confidence: 0.91. Anomalies: 0."
    elif any(w in task_lower for w in ["generate", "create", "write"]):
        return f"[{worker_id}] Generation complete. Tokens used: {len(task.split()) * 12}."
    else:
        return f"[{worker_id}] Task processed. Input: {len(task)} chars. Time: {round(len(task) * 0.003, 3)}s."


async def worker_loop(task_sub, pubsub, worker_id, stop_event):
    logger.info(f"Worker [{worker_id}] listening for tasks...")

    while not stop_event.is_set():
        try:
            msg = await task_sub.get()
            payload = json.loads(msg.data.decode("utf-8"))

            task_id = payload.get("task_id", "unknown")
            task_text = payload.get("task", "")

            logger.info(f"Received task [{task_id}]: {task_text}")

            result = await trio.to_thread.run_sync(process_task, task_text, worker_id)

            response = json.dumps({
                "task_id": task_id,
                "worker_id": worker_id,
                "result": result,
                "timestamp": time.time(),
            }).encode("utf-8")

            await pubsub.publish(RESPONSE_TOPIC, response)
            logger.info(f"Response sent for task [{task_id}]")

        except Exception:
            logger.exception("Error in worker loop")
            await trio.sleep(1)


async def dispatcher_response_loop(response_sub, stop_event):
    while not stop_event.is_set():
        try:
            msg = await response_sub.get()
            payload = json.loads(msg.data.decode("utf-8"))

            task_id = payload.get("task_id", "?")
            worker_id = payload.get("worker_id", "?")
            result = payload.get("result", "")

            print(f"\n[Response] task_id={task_id} | worker={worker_id}")
            print(f"  {result}\n")

        except Exception:
            logger.exception("Error in response loop")
            await trio.sleep(1)


async def dispatcher_input_loop(pubsub, stop_event):
    print("\nType a task and press Enter to send to workers.")
    print('Type "quit" to exit.\n')
    counter = 0

    while not stop_event.is_set():
        try:
            text = await trio.to_thread.run_sync(input, "> ")

            if text.strip().lower() == "quit":
                stop_event.set()
                break

            if text.strip():
                counter += 1
                task_id = f"task-{counter}"
                payload = json.dumps({
                    "task_id": task_id,
                    "task": text.strip(),
                }).encode("utf-8")

                await pubsub.publish(TASK_TOPIC, payload)
                logger.info(f"Dispatched [{task_id}]: {text.strip()}")

        except Exception:
            logger.exception("Error in input loop")
            await trio.sleep(1)


async def run(destination, is_worker, port):
    from libp2p.utils.address_validation import (
        get_available_interfaces,
        get_optimal_binding_address,
    )

    if not port:
        port = find_free_port()

    listen_addrs = get_available_interfaces(port)

    host = new_host(
        key_pair=key_pair,
        muxer_opt={MPLEX_PROTOCOL_ID: Mplex},
    )

    gossipsub = GossipSub(
        protocols=[GOSSIPSUB_PROTOCOL_ID],
        degree=3,
        degree_low=2,
        degree_high=4,
        direct_peers=None,
        time_to_live=60,
        gossip_window=2,
        gossip_history=5,
        heartbeat_initial_delay=2.0,
        heartbeat_interval=5,
    )

    pubsub = Pubsub(host, gossipsub)
    stop_event = trio.Event()
    worker_id = host.get_id().to_string()[:8]

    async with host.run(listen_addrs=listen_addrs), trio.open_nursery() as nursery:
        nursery.start_soon(host.get_peerstore().start_cleanup_task, 60)
        logger.info(f"Node started | Peer ID: {host.get_id()}")

        async with background_trio_service(pubsub):
            async with background_trio_service(gossipsub):
                await pubsub.wait_until_ready()

                task_sub = await pubsub.subscribe(TASK_TOPIC)
                response_sub = await pubsub.subscribe(RESPONSE_TOPIC)

                if not destination:
                    optimal = get_optimal_binding_address(port)
                    peer_addr = f"{optimal}/p2p/{host.get_id().to_string()}"

                    logger.info("\nShare this address with worker agents:")
                    logger.info(f"\n  python agent.py -d {peer_addr} --worker\n")
                    logger.info("Waiting for workers...")
                    await trio.sleep(1)

                    nursery.start_soon(dispatcher_response_loop, response_sub, stop_event)
                    nursery.start_soon(dispatcher_input_loop, pubsub, stop_event)

                else:
                    maddr = multiaddr.Multiaddr(destination)
                    info = info_from_p2p_addr(maddr)

                    logger.info(f"Connecting to dispatcher: {info.peer_id}")
                    await host.connect(info)
                    logger.info("Connected. Waiting for mesh to form...")
                    await trio.sleep(2)

                    nursery.start_soon(worker_loop, task_sub, pubsub, worker_id, stop_event)

                await stop_event.wait()

        nursery.cancel_scope.cancel()

    logger.info("Shutdown complete")


def main():
    parser = argparse.ArgumentParser(
        description="AI agent communication demo over py-libp2p GossipSub."
    )
    parser.add_argument("-d", "--destination", type=str, default=None)
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("-p", "--port", type=int, default=None)
    parser.add_argument("-v", "--verbose", action="store_true")

    args = parser.parse_args()

    if args.verbose:
        logger.setLevel(logging.DEBUG)

    role = "Worker" if args.destination else "Dispatcher"
    logger.info(f"Starting | Role: {role}")

    try:
        trio.run(run, args.destination, args.worker, args.port)
    except KeyboardInterrupt:
        logger.info("Terminated by user")


if __name__ == "__main__":
    main()