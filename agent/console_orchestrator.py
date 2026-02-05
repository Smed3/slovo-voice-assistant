"""Simple console app for testing the agent orchestrator."""

from __future__ import annotations

import argparse
import asyncio
import logging
from pathlib import Path
import uuid

from typing import Any

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
        "\n"
        "Tool commands (requires --tools):\n"
        "  /tools                         List tools\n"
        "  /tools pending                 List pending approvals\n"
        "  /tool import <path>            Import local manifest (.yaml/.json)\n"
        "  /tool openapi <url>            Ingest OpenAPI spec from URL\n"
        "  /tool approve <tool_id>        Approve tool (enables use)\n"
        "  /tool revoke <tool_id>         Revoke tool (disables use)\n"
        "  /tool logs <tool_id> [n]       Show last n execution logs (default: 10)\n"
    )


def _parse_command_args(text: str) -> list[str]:
    return [part for part in text.strip().split() if part]


async def _maybe_init_tools(
    orchestrator: AgentOrchestrator,
    database_url: str,
    enable_tools: bool,
) -> dict[str, Any]:
    """Initialize Phase 4 tool subsystems for the console.

    Returns a dict with optional keys:
      - tool_repo
      - tool_discovery
      - sandbox
      - tool_engine (SQLAlchemy engine)
    """
    if not enable_tools:
        return {}

    # Import lazily so the console still works without Phase 4 deps.
    try:
        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    except Exception as exc:  # pragma: no cover
        logger = structlog.get_logger(__name__)
        logger.warning("SQLAlchemy async not available; tools disabled", error=str(exc))
        return {}

    try:
        from slovo_agent.agents.tool_discovery import ToolDiscoveryAgent
        from slovo_agent.models import PermissionType, ToolManifest, ToolPermissionCreate, ToolStatus, ToolManifestUpdate
        from slovo_agent.tools import DockerSandboxManager, ToolRepository
    except Exception as exc:  # pragma: no cover
        logger = structlog.get_logger(__name__)
        logger.warning("Tool modules not available; tools disabled", error=str(exc))
        return {}

    # Normalize database URL for SQLAlchemy asyncpg
    if database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    tool_engine = create_async_engine(database_url, echo=False)
    session_factory = async_sessionmaker(
        tool_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    tool_repo = ToolRepository(session_factory)

    # Wire tool discovery into executor
    tool_discovery = ToolDiscoveryAgent(tool_repo, orchestrator.llm)
    orchestrator.executor_agent.set_tool_discovery_agent(tool_discovery)

    # Wire docker sandbox into executor (best-effort)
    sandbox = None
    try:
        sandbox = DockerSandboxManager(tool_repo)
        orchestrator.executor_agent.set_sandbox_manager(sandbox)
    except Exception as exc:
        logger = structlog.get_logger(__name__)
        logger.warning("Docker sandbox unavailable; tool execution disabled", error=str(exc))

    # Register approved tools with planner so it can plan tool_execution steps.
    # (Planner uses the lightweight ToolManifest model.)
    try:
        approved_tools = await tool_repo.list_tool_manifests(status=ToolStatus.APPROVED)
        for t in approved_tools:
            # Permissions are stored separately; planner only needs a hint.
            perms = await tool_repo.list_tool_permissions(t.id)
            perm_names = [p.permission_type.value for p in perms]
            orchestrator.planner_agent.register_tool(
                t.name,
                ToolManifest(
                    name=t.name,
                    version=t.version,
                    description=t.description,
                    permissions=perm_names,
                    parameters=t.parameters_schema,
                ),
            )
    except Exception as exc:
        logger = structlog.get_logger(__name__)
        logger.warning("Failed to load/register approved tools", error=str(exc))

    return {
        "tool_repo": tool_repo,
        "tool_discovery": tool_discovery,
        "sandbox": sandbox,
        "tool_engine": tool_engine,
        "PermissionType": PermissionType,
        "ToolPermissionCreate": ToolPermissionCreate,
        "ToolStatus": ToolStatus,
        "ToolManifestUpdate": ToolManifestUpdate,
        "ToolManifest": ToolManifest,
    }


async def _tools_apply_permissions_from_manifest(
    tool_ctx: dict[str, Any],
    tool_id: Any,
    manifest_data: dict[str, Any],
) -> None:
    tool_repo = tool_ctx.get("tool_repo")
    PermissionType = tool_ctx.get("PermissionType")
    ToolPermissionCreate = tool_ctx.get("ToolPermissionCreate")
    if not tool_repo or not PermissionType or not ToolPermissionCreate:
        return

    permissions = manifest_data.get("permissions")
    if not isinstance(permissions, dict):
        return

    mapping: list[tuple[Any, str]] = []
    if "internet_access" in permissions:
        mapping.append((PermissionType.INTERNET_ACCESS, "true" if bool(permissions["internet_access"]) else "false"))
    if "storage_quota_mb" in permissions:
        mapping.append((PermissionType.STORAGE, str(int(permissions["storage_quota_mb"])) ))
    if "cpu_limit_percent" in permissions:
        mapping.append((PermissionType.CPU_LIMIT, str(int(permissions["cpu_limit_percent"])) ))
    if "memory_limit_mb" in permissions:
        mapping.append((PermissionType.MEMORY_LIMIT, str(int(permissions["memory_limit_mb"])) ))

    for permission_type, permission_value in mapping:
        try:
            await tool_repo.create_tool_permission(
                ToolPermissionCreate(
                    tool_id=tool_id,
                    permission_type=permission_type,
                    permission_value=permission_value,
                    granted_by="console",
                )
            )
        except Exception as exc:
            logger = structlog.get_logger(__name__)
            logger.warning(
                "Failed to set tool permission",
                tool_id=str(tool_id),
                permission_type=str(permission_type),
                error=str(exc),
            )


async def run_console(
    orchestrator: AgentOrchestrator,
    conversation_id: str,
    tool_ctx: dict[str, Any] | None = None,
) -> None:
    print("\nSlovo Orchestrator Console")
    print("Type your message, or /help for commands.")
    print(f"Conversation ID: {conversation_id}\n")

    tool_ctx = tool_ctx or {}
    tool_repo = tool_ctx.get("tool_repo")
    tool_discovery = tool_ctx.get("tool_discovery")
    sandbox = tool_ctx.get("sandbox")
    ToolStatus = tool_ctx.get("ToolStatus")
    ToolManifestUpdate = tool_ctx.get("ToolManifestUpdate")
    ToolManifest = tool_ctx.get("ToolManifest")

    while True:
        try:
            text = (await _read_input("you> ")).strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting...")
            return

        if not text:
            continue

        if text.startswith("/"):
            parts = _parse_command_args(text)
            command = parts[0].lower()

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

            # Tool commands
            if command == "/tools":
                if not tool_repo:
                    print("Tools not enabled. Start with --tools.")
                    continue
                only_pending = len(parts) >= 2 and parts[1].lower() == "pending"
                status = ToolStatus.PENDING_APPROVAL if only_pending else None
                try:
                    tools = await tool_repo.list_tool_manifests(status=status)
                except Exception as exc:
                    print(f"Failed to list tools: {exc}")
                    continue

                if not tools:
                    print("No tools found.")
                    continue

                print("\nTools:")
                for t in tools:
                    print(f"- {t.name} ({t.version}) id={t.id} status={t.status.value}")
                    print(f"  {t.description}")
                print("")
                continue

            if command == "/tool":
                if not tool_repo or not tool_discovery:
                    print("Tools not enabled. Start with --tools.")
                    continue

                if len(parts) < 2:
                    print("Usage: /tool <import|openapi|approve|revoke|logs> ...")
                    continue

                sub = parts[1].lower()

                if sub == "import":
                    if len(parts) < 3:
                        print("Usage: /tool import <path>")
                        continue
                    path = Path(" ".join(parts[2:])).expanduser()
                    try:
                        # Import via discovery agent
                        tool_id = await tool_discovery.import_local_manifest(path)

                        # Best-effort: apply permissions section to permission table
                        # (ToolDiscoveryAgent currently stores manifest fields but not permissions.)
                        # Load the manifest file again here so the console can set permissions.
                        import json as _json

                        try:
                            raw = path.read_text(encoding="utf-8")
                            if path.suffix.lower() in {".yaml", ".yml"}:
                                import yaml as _yaml

                                manifest_data = _yaml.safe_load(raw)
                            else:
                                manifest_data = _json.loads(raw)
                            if isinstance(manifest_data, dict):
                                await _tools_apply_permissions_from_manifest(tool_ctx, tool_id, manifest_data)
                        except Exception:
                            # Ignore permission parsing errors; tool is still imported.
                            pass

                        print(f"Imported tool. id={tool_id}")
                    except Exception as exc:
                        print(f"Import failed: {exc}")
                    continue

                if sub == "openapi":
                    if len(parts) < 3:
                        print("Usage: /tool openapi <url>")
                        continue
                    url = parts[2]
                    try:
                        tool_id = await tool_discovery.ingest_openapi_url(url)
                        print(f"Ingested OpenAPI spec. id={tool_id}")
                    except Exception as exc:
                        print(f"OpenAPI ingestion failed: {exc}")
                    continue

                if sub == "approve":
                    if len(parts) < 3:
                        print("Usage: /tool approve <tool_id>")
                        continue
                    if not ToolManifestUpdate or not ToolStatus:
                        print("Tool models not available.")
                        continue
                    tool_id_str = parts[2]
                    try:
                        from uuid import UUID

                        tool_id = UUID(tool_id_str)
                        updated = await tool_repo.update_tool_manifest(
                            tool_id,
                            ToolManifestUpdate(status=ToolStatus.APPROVED),
                        )

                        perms = await tool_repo.list_tool_permissions(updated.id)
                        perm_names = [p.permission_type.value for p in perms]
                        if ToolManifest:
                            orchestrator.planner_agent.register_tool(
                                updated.name,
                                ToolManifest(
                                    name=updated.name,
                                    version=updated.version,
                                    description=updated.description,
                                    permissions=perm_names,
                                    parameters=updated.parameters_schema,
                                ),
                            )
                        print(f"Approved tool: {updated.name} id={updated.id}")
                    except Exception as exc:
                        print(f"Approve failed: {exc}")
                    continue

                if sub == "revoke":
                    if len(parts) < 3:
                        print("Usage: /tool revoke <tool_id>")
                        continue
                    if not ToolManifestUpdate or not ToolStatus:
                        print("Tool models not available.")
                        continue
                    tool_id_str = parts[2]
                    try:
                        from uuid import UUID

                        tool_id = UUID(tool_id_str)
                        updated = await tool_repo.update_tool_manifest(
                            tool_id,
                            ToolManifestUpdate(status=ToolStatus.REVOKED),
                        )
                        orchestrator.planner_agent.unregister_tool(updated.name)

                        # Best-effort: cleanup docker volume
                        if sandbox is not None:
                            try:
                                await sandbox.cleanup_tool_resources(updated.id)
                            except Exception:
                                pass

                        print(f"Revoked tool: {updated.name} id={updated.id}")
                    except Exception as exc:
                        print(f"Revoke failed: {exc}")
                    continue

                if sub == "logs":
                    if len(parts) < 3:
                        print("Usage: /tool logs <tool_id> [n]")
                        continue
                    tool_id_str = parts[2]
                    n = 10
                    if len(parts) >= 4:
                        try:
                            n = max(1, min(100, int(parts[3])))
                        except Exception:
                            n = 10
                    try:
                        from uuid import UUID

                        tool_id = UUID(tool_id_str)
                        logs = await tool_repo.list_tool_executions(tool_id=tool_id, limit=n)
                        if not logs:
                            print("No execution logs.")
                            continue
                        print("")
                        for log in logs:
                            print(
                                f"- {log.started_at.isoformat()} status={log.status.value} id={log.id} duration_ms={log.duration_ms}"
                            )
                            if log.error_message:
                                print(f"  error: {log.error_message}")
                        print("")
                    except Exception as exc:
                        print(f"Failed to fetch logs: {exc}")
                    continue

                print("Unknown /tool subcommand. Type /help for commands.")
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
    parser.add_argument(
        "--tools",
        action="store_true",
        help="Enable Phase 4 tools (requires Postgres; Docker optional but recommended)",
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

    tool_ctx: dict[str, Any] = {}
    if args.tools:
        try:
            tool_ctx = await _maybe_init_tools(
                orchestrator=orchestrator,
                database_url=settings.database_url,
                enable_tools=True,
            )
        except Exception as exc:
            logger = structlog.get_logger(__name__)
            logger.warning("Tool subsystem init failed; continuing without tools", error=str(exc))

    try:
        await run_console(orchestrator, args.conversation_id, tool_ctx=tool_ctx)
    finally:
        # Best-effort cleanup
        tool_discovery = tool_ctx.get("tool_discovery")
        if tool_discovery is not None:
            try:
                await tool_discovery.close()
            except Exception:
                pass

        tool_engine = tool_ctx.get("tool_engine")
        if tool_engine is not None:
            try:
                await tool_engine.dispose()
            except Exception:
                pass


if __name__ == "__main__":
    asyncio.run(main())
