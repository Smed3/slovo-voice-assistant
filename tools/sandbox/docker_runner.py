"""
Docker sandbox runner for Slovo tools.

This module provides functionality to run tools in isolated Docker containers
with proper security policies and resource limits.
"""

import asyncio
import json
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from .config import SandboxConfig


@dataclass
class ExecutionResult:
    """Result of tool execution."""
    
    success: bool
    output: Any
    error: Optional[str] = None
    execution_time_ms: int = 0
    resource_usage: Optional[dict] = None


class DockerSandbox:
    """
    Docker-based sandbox for running tools securely.
    """
    
    def __init__(self, config: SandboxConfig) -> None:
        self.config = config
        self._container_id: Optional[str] = None
    
    async def run(
        self,
        input_data: dict[str, Any],
        tool_volume: Optional[Path] = None,
    ) -> ExecutionResult:
        """
        Run a tool in the Docker sandbox.
        
        Args:
            input_data: Input data to pass to the tool
            tool_volume: Path to tool's persistent storage volume
            
        Returns:
            ExecutionResult with output or error
        """
        if not self.config.docker_image:
            return ExecutionResult(
                success=False,
                output=None,
                error="No Docker image specified",
            )
        
        # Build docker run command
        cmd = self._build_docker_command(tool_volume)
        
        try:
            # Create process
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            
            # Send input and wait for completion with timeout
            input_bytes = json.dumps(input_data).encode()
            
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(input=input_bytes),
                    timeout=self.config.resources.max_execution_time_seconds,
                )
            except asyncio.TimeoutError:
                process.kill()
                return ExecutionResult(
                    success=False,
                    output=None,
                    error="Tool execution timed out",
                )
            
            # Parse output
            if process.returncode != 0:
                return ExecutionResult(
                    success=False,
                    output=None,
                    error=stderr.decode() if stderr else "Unknown error",
                )
            
            try:
                output = json.loads(stdout.decode())
            except json.JSONDecodeError:
                output = stdout.decode()
            
            return ExecutionResult(
                success=True,
                output=output,
            )
            
        except Exception as e:
            return ExecutionResult(
                success=False,
                output=None,
                error=str(e),
            )
    
    def _build_docker_command(self, tool_volume: Optional[Path] = None) -> list[str]:
        """Build the docker run command with security options."""
        cmd = ["docker", "run", "--rm", "-i"]
        
        # Resource limits
        cmd.extend([
            f"--memory={self.config.resources.max_memory_mb}m",
            f"--cpus={self.config.resources.max_cpu_percent / 100}",
            f"--pids-limit={self.config.resources.max_processes}",
        ])
        
        # Network policy
        if not self.config.network.outbound_allowed:
            cmd.append("--network=none")
        
        # Security options
        cmd.extend([
            "--security-opt=no-new-privileges",
            "--read-only",
            "--cap-drop=ALL",
        ])
        
        # User
        cmd.extend(["--user", self.config.docker_user])
        
        # Volumes
        if tool_volume and self.config.storage.persistent:
            cmd.extend(["-v", f"{tool_volume}:/data"])
        
        # Temp directory for writes
        cmd.extend(["--tmpfs", "/tmp:rw,noexec,nosuid,size=64m"])
        
        # Environment variables
        for key, value in self.config.environment.items():
            cmd.extend(["-e", f"{key}={value}"])
        
        # Image
        cmd.append(self.config.docker_image)
        
        return cmd


async def run_tool_in_sandbox(
    manifest: dict,
    input_data: dict[str, Any],
    tool_storage_path: Optional[Path] = None,
) -> ExecutionResult:
    """
    Convenience function to run a tool given its manifest.
    
    Args:
        manifest: Tool manifest
        input_data: Input data for the tool
        tool_storage_path: Path to tool's persistent storage
        
    Returns:
        ExecutionResult
    """
    from .config import create_sandbox_config_from_manifest
    
    config = create_sandbox_config_from_manifest(manifest)
    sandbox = DockerSandbox(config)
    
    return await sandbox.run(input_data, tool_storage_path)
