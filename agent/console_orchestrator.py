"""Simple console app for testing the agent orchestrator."""

from __future__ import annotations

import argparse
import asyncio
import logging
import uuid

import structlog

from slovo_agent.agents.orchestrator import AgentOrchestrator
from slovo_agent.config import settings
from slovo_agent.memory import create_memory_manager


def configure_logging(level: str) -> None:
    """Configure structured logging for console output."""
    logging.basicConfig(level=getattr(logging, level.upper(), logging.INFO))
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


async def _read_input(prompt: str) -> str:
    return await asyncio.to_thread(input, prompt)


def _print_help() -> None:
    print(
        "\nCommands:\n"
        "  /help        Show commands\n"
        "  /exit        Exit\n"
        "  /quit        Exit\n"
        "  /new         New conversation id\n"
        "  /clear       Clear conversation context\n"
        "  /id          Show conversation id\n"
    )


async def run_console(orchestrator: AgentOrchestrator, conversation_id: str) -> None:
    print("\nSlovo Orchestrator Console")
    print("Type your message, or /help for commands.")
    print(f"Conversation ID: {conversation_id}\n")

    while True:
        try:
            text = (await _read_input("you> ")).strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting...")
            return

        if not text:
            continue

        if text.startswith("/"):
            command = text.lower()
            if command in {"/exit", "/quit"}:
                print("Exiting...")
                return
            if command == "/help":
                _print_help()
                continue
            if command == "/new":
                orchestrator.clear_conversation(conversation_id)
                conversation_id = str(uuid.uuid4())
                print(f"New conversation ID: {conversation_id}")
                continue
            if command == "/clear":
                orchestrator.clear_conversation(conversation_id)
                print("Conversation context cleared.")
                continue
            if command == "/id":
                print(f"Conversation ID: {conversation_id}")
                continue

            print("Unknown command. Type /help for commands.")
            continue

        result = await orchestrator.process_message(text, conversation_id)

        print("\nassistant>")
        print(result.response)
        if result.reasoning:
            print(f"\nreasoning: {result.reasoning}")
        print(f"confidence: {result.confidence:.2f}\n")


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Simple console app to test the Slovo orchestrator.",
    )
    parser.add_argument(
        "--conversation-id",
        default=str(uuid.uuid4()),
        help="Conversation id to use (default: random uuid)",
    )
    parser.add_argument(
        "--memory",
        action="store_true",
        help="Enable memory manager (requires Redis/Qdrant/Postgres)",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        help="Logging level (DEBUG, INFO, WARNING, ERROR)",
    )
    args = parser.parse_args()

    configure_logging(args.log_level)

    orchestrator = AgentOrchestrator()

    if args.memory:
        try:
            memory_manager = await create_memory_manager(
                redis_url=settings.redis_url,
                qdrant_url=settings.qdrant_url,
                database_url=settings.database_url,
            )
            orchestrator.set_memory_manager(memory_manager)
        except Exception as exc:
            logger = structlog.get_logger(__name__)
            logger.warning("Memory manager init failed; continuing without memory", error=str(exc))

    await run_console(orchestrator, args.conversation_id)


if __name__ == "__main__":
    asyncio.run(main())
