"""
Docker Sandbox Manager

Phase 4: Manages Docker containers for isolated tool execution with
strict permission enforcement and resource limits.
"""

import json
from datetime import datetime
from typing import Any
from uuid import UUID

import docker
import structlog
from docker.errors import DockerException
from docker.models.containers import Container
from docker.types import LogConfig, Mount

from slovo_agent.models import (
    ExecutionStatus,
    PermissionType,
    ToolExecutionCreate,
    ToolExecutionUpdate,
    ToolManifestDB,
    ToolPermissionDB,
)
from slovo_agent.tools.repository import ToolRepository

logger = structlog.get_logger(__name__)


class DockerSandboxManager:
    """
    Manages Docker containers for tool execution.

    Responsibilities:
    - Create isolated containers for each tool execution
    - Enforce permission model (network, storage, CPU, memory)
    - Manage tool-scoped volumes for state persistence
    - Monitor resource usage
    - Handle container lifecycle
    """

    def __init__(self, tool_repository: ToolRepository) -> None:
        """
        Initialize Docker sandbox manager.

        Args:
            tool_repository: Repository for tool and execution data
        """
        self.tool_repo = tool_repository
        try:
            self.docker_client = docker.from_env()
            # Test connection
            self.docker_client.ping()
            logger.info("Docker sandbox manager initialized")
        except DockerException as e:
            logger.error("Failed to connect to Docker", error=str(e))
            raise RuntimeError("Docker daemon not available") from e

    # =========================================================================
    # Container Execution
    # =========================================================================

    async def execute_tool(
        self,
        tool_manifest: ToolManifestDB,
        permissions: list[ToolPermissionDB],
        input_params: dict[str, Any],
        conversation_id: str | None = None,
        turn_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Execute a tool in an isolated Docker container.

        Args:
            tool_manifest: Tool manifest
            permissions: Tool permissions
            input_params: Input parameters for the tool
            conversation_id: Optional conversation ID for tracking
            turn_id: Optional turn ID for tracking

        Returns:
            Execution result with output or error

        Raises:
            RuntimeError: If execution fails
        """
        logger.info(
            "Starting tool execution",
            tool_name=tool_manifest.name,
            tool_id=str(tool_manifest.id),
        )

        # Create execution log entry
        execution_create = ToolExecutionCreate(
            tool_id=tool_manifest.id,
            conversation_id=conversation_id,
            turn_id=turn_id,
            input_params=input_params,
        )
        execution_log = await self.tool_repo.create_tool_execution(execution_create)

        try:
            # Build container configuration
            container_config = await self._build_container_config(
                tool_manifest, permissions, input_params
            )

            # Run container
            start_time = datetime.utcnow()
            container = self._run_container(container_config)

            # Wait for completion
            result = container.wait()
            end_time = datetime.utcnow()
            duration_ms = int((end_time - start_time).total_seconds() * 1000)

            # Get logs
            stdout = container.logs(stdout=True, stderr=False).decode("utf-8")
            stderr = container.logs(stdout=False, stderr=True).decode("utf-8")

            # Get resource stats (if available)
            stats = container.stats(stream=False)
            cpu_usage_ms = self._extract_cpu_usage(stats)
            memory_peak_mb = self._extract_memory_peak(stats)

            # Determine status
            exit_code = result.get("StatusCode", -1)
            if exit_code == 0:
                status = ExecutionStatus.SUCCESS
                output = {"stdout": stdout, "stderr": stderr}
                error_message = None
            else:
                status = ExecutionStatus.FAILURE
                output = {"stdout": stdout, "stderr": stderr}
                error_message = f"Container exited with code {exit_code}"

            # Update execution log
            await self.tool_repo.update_tool_execution(
                execution_log.id,
                ToolExecutionUpdate(
                    completed_at=end_time,
                    duration_ms=duration_ms,
                    status=status,
                    output=output,
                    error_message=error_message,
                    exit_code=exit_code,
                    cpu_usage_ms=cpu_usage_ms,
                    memory_peak_mb=memory_peak_mb,
                    container_id=container.id,
                ),
            )

            # Cleanup container
            container.remove(force=True)

            logger.info(
                "Tool execution completed",
                tool_name=tool_manifest.name,
                execution_id=str(execution_log.id),
                status=status.value,
                duration_ms=duration_ms,
            )

            return {
                "execution_id": str(execution_log.id),
                "status": status.value,
                "output": output,
                "error_message": error_message,
                "duration_ms": duration_ms,
                "exit_code": exit_code,
            }

        except Exception as e:
            logger.error(
                "Tool execution failed",
                tool_name=tool_manifest.name,
                execution_id=str(execution_log.id),
                error=str(e),
            )

            # Update execution log with error
            await self.tool_repo.update_tool_execution(
                execution_log.id,
                ToolExecutionUpdate(
                    completed_at=datetime.utcnow(),
                    status=ExecutionStatus.FAILURE,
                    error_message=str(e),
                ),
            )

            raise RuntimeError(f"Tool execution failed: {str(e)}") from e

    async def _build_container_config(
        self,
        tool_manifest: ToolManifestDB,
        permissions: list[ToolPermissionDB],
        input_params: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Build Docker container configuration based on tool and permissions.

        Args:
            tool_manifest: Tool manifest
            permissions: Tool permissions
            input_params: Input parameters

        Returns:
            Container configuration dict
        """
        # Permission lookups
        permission_map = {p.permission_type: p.permission_value for p in permissions}

        # Network configuration
        network_mode = "none"  # Default: no network
        if permission_map.get(PermissionType.INTERNET_ACCESS) == "true":
            network_mode = "bridge"

        # Resource limits
        cpu_limit = int(permission_map.get(PermissionType.CPU_LIMIT, "50"))
        memory_limit = int(permission_map.get(PermissionType.MEMORY_LIMIT, "512"))

        # Convert CPU percentage to CPU quota/period
        # 100% = 100000 microseconds per 100000 period
        cpu_quota = int((cpu_limit / 100.0) * 100000)
        cpu_period = 100000

        # Memory limit in bytes
        mem_limit = f"{memory_limit}m"

        # Tool volume for state persistence
        volumes = await self._get_or_create_volume(tool_manifest.id)

        # Safely pass input parameters via environment variable
        # This prevents injection attacks via command string manipulation
        params_json = json.dumps(input_params)

        # Build container config
        # Note: Actual image name should come from tool manifest
        # For MVP, we'll use a generic Python base image
        config = {
            "image": "python:3.11-slim",
            "command": ["python", "-c", "import os; import json; params = json.loads(os.environ.get('TOOL_PARAMS', '{}')); print(json.dumps(params))"],
            "environment": {
                "TOOL_PARAMS": params_json,
            },
            "network_mode": network_mode,
            "cpu_quota": cpu_quota,
            "cpu_period": cpu_period,
            "mem_limit": mem_limit,
            "memswap_limit": mem_limit,  # Disable swap
            "mounts": volumes,
            "detach": True,
            "remove": False,  # We'll remove manually after getting logs
            "log_config": LogConfig(type="json-file", config={"max-size": "10m"}),
            "security_opt": ["no-new-privileges:true"],
            "cap_drop": ["ALL"],  # Drop all capabilities
            "read_only": True,  # Read-only root filesystem
        }

        return config

    def _run_container(self, config: dict[str, Any]) -> Container:
        """
        Run a Docker container with the given configuration.

        Args:
            config: Container configuration

        Returns:
            Running container
        """
        try:
            container = self.docker_client.containers.run(**config)
            return container
        except DockerException as e:
            logger.error("Failed to run container", error=str(e))
            raise RuntimeError(f"Container execution failed: {str(e)}") from e

    async def _get_or_create_volume(self, tool_id: UUID) -> list[Mount]:
        """
        Get or create a Docker volume for tool state persistence.

        Args:
            tool_id: Tool UUID

        Returns:
            List of volume mounts
        """
        volume_name = f"slovo-tool-{tool_id}"

        # Check if volume exists in database
        volumes = await self.tool_repo.list_tool_volumes(tool_id)

        if not volumes:
            # Create new volume
            try:
                self.docker_client.volumes.create(name=volume_name)
                logger.info("Docker volume created", volume_name=volume_name)

                # Record in database
                from slovo_agent.models import ToolVolumeCreate

                await self.tool_repo.create_tool_volume(
                    ToolVolumeCreate(
                        tool_id=tool_id,
                        volume_name=volume_name,
                        mount_path="/data",
                        quota_mb=1024,
                    )
                )
            except DockerException as e:
                logger.warning("Failed to create volume", error=str(e))
                return []

        # Return mount configuration
        return [Mount(target="/data", source=volume_name, type="volume")]

    # =========================================================================
    # Resource Monitoring
    # =========================================================================

    def _extract_cpu_usage(self, stats: dict[str, Any]) -> int | None:
        """
        Extract CPU usage in milliseconds from container stats.

        Args:
            stats: Container stats

        Returns:
            CPU usage in milliseconds or None
        """
        try:
            cpu_stats = stats.get("cpu_stats", {})
            cpu_usage = cpu_stats.get("cpu_usage", {})
            total_usage = cpu_usage.get("total_usage", 0)
            # Convert nanoseconds to milliseconds
            return int(total_usage / 1_000_000)
        except Exception:
            return None

    def _extract_memory_peak(self, stats: dict[str, Any]) -> int | None:
        """
        Extract peak memory usage in MB from container stats.

        Args:
            stats: Container stats

        Returns:
            Peak memory in MB or None
        """
        try:
            memory_stats = stats.get("memory_stats", {})
            max_usage = memory_stats.get("max_usage", 0)
            # Convert bytes to MB
            return int(max_usage / (1024 * 1024))
        except Exception:
            return None

    # =========================================================================
    # Cleanup
    # =========================================================================

    async def cleanup_tool_resources(self, tool_id: UUID) -> None:
        """
        Clean up Docker resources for a tool.

        Args:
            tool_id: Tool UUID
        """
        logger.info("Cleaning up tool resources", tool_id=str(tool_id))

        # Get tool volumes
        volumes = await self.tool_repo.list_tool_volumes(tool_id)

        for volume in volumes:
            try:
                docker_volume = self.docker_client.volumes.get(volume.volume_name)
                docker_volume.remove(force=True)
                logger.info("Volume removed", volume_name=volume.volume_name)
            except DockerException as e:
                logger.warning(
                    "Failed to remove volume",
                    volume_name=volume.volume_name,
                    error=str(e),
                )

    def close(self) -> None:
        """Close Docker client connection."""
        self.docker_client.close()
        logger.info("Docker sandbox manager closed")
