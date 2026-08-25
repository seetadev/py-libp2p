import logging
from dataclasses import dataclass

from protocol import receive_frame, send_frame
from state import SharedState

logger = logging.getLogger(__name__)


@dataclass
class AgentPersona:
    agent_id: str
    name: str
    system_prompt: str


async def generate_worker_response(
    persona,
    llm,
    state: SharedState,
    instruction,
):
    history = await state.recent(12)

    messages = [
        {
            "role": "system",
            "content": persona.system_prompt,
        }
    ]

    messages += [
        {
            "role": "user",
            "content": (
                f"{item['agent_name']} [{item['role']}]:\n"
                f"{item['content']}"
            ),
        }
        for item in history
    ]

    messages.append(
        {
            "role": "user",
            "content": instruction,
        }
    )

    response = await llm.complete(
        messages,
        temperature=0.3,
    )

    return await state.add(
        agent_id=persona.agent_id,
        agent_name=persona.name,
        role="agent",
        content=response,
    )


async def handle_incoming_request(
    stream,
    local_agent,
    state,
    llm,
    ethercalc,
    personas,
):
    try:
        message = await receive_frame(stream)

        if message.get("type") == "state_sync":
            operation = message.get("operation")

            if not isinstance(operation, dict):
                raise ValueError("Missing operation.")

            await state.merge(operation)

            await send_frame(
                stream,
                {
                    "type": "sync_ack",
                    "agent": local_agent.agent_id,
                },
            )
            return

        if message.get("type") != "agent_request":
            raise ValueError("Expected agent_request.")

        source_agent = message.get("source_agent")
        target_agent = message.get("target_agent")
        operation = message.get("operation")

        if source_agent not in personas:
            raise ValueError(f"Unknown source agent: {source_agent}")

        if target_agent != local_agent.agent_id:
            raise ValueError("Request sent to wrong agent.")

        if not isinstance(operation, dict):
            raise ValueError("Missing operation.")

        await state.merge(operation)

        response = await generate_worker_response(
            persona=local_agent,
            llm=llm,
            state=state,
            instruction=(
                f"You received a request from "
                f"{operation['agent_name']}.\n\n"
                f"REQUEST:\n{operation['content']}\n\n"
                "Analyze the request, then provide a concise "
                "summary of your result suitable for sending "
                "back to the requesting agent."
            ),
        )      

        await ethercalc.append(
            response,
            request=operation["content"],
        )

        await send_frame(
            stream,
            {
                "type": "agent_response",
                "request_id": message.get("request_id"),
                "source_agent": local_agent.agent_id,
                "target_agent": source_agent,
                "operation": response,
            },
        )

    except Exception as exc:
        logger.exception("Incoming P2P request failed.")

        try:
            await send_frame(
                stream,
                {
                    "type": "error",
                    "agent": local_agent.agent_id,
                    "content": f"{type(exc).__name__}: {exc}",
                },
            )
          
        except Exception:
            pass

    finally:
        await stream.close()
  
