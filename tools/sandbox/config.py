"""
Sandbox configuration for tool execution.

This module defines the security policies and resource limits
for running tools in isolated environments.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class SandboxType(str, Enum):
    """Types of sandbox environments."""
    DOCKER = "docker"
    WASM = "wasm"


@dataclass
class NetworkPolicy:
    """Network access policy for sandboxed tools."""
    
    outbound_allowed: bool = False
    allowed_hosts: list[str] = field(default_factory=list)
    allowed_ports: list[int] = field(default_factory=lambda: [80, 443])
    

@dataclass
class StoragePolicy:
    """Storage policy for sandboxed tools."""
    
    persistent: bool = False
    max_size_mb: int = 100
    read_only_root: bool = True


@dataclass
class ResourceLimits:
    """Resource limits for sandboxed tools."""
    
    max_memory_mb: int = 256
    max_cpu_percent: int = 50
    max_execution_time_seconds: int = 30
    max_processes: int = 10


@dataclass
class SandboxConfig:
    """Complete sandbox configuration for a tool."""
    
    sandbox_type: SandboxType
    network: NetworkPolicy = field(default_factory=NetworkPolicy)
    storage: StoragePolicy = field(default_factory=StoragePolicy)
    resources: ResourceLimits = field(default_factory=ResourceLimits)
    environment: dict[str, str] = field(default_factory=dict)
    
    # Docker-specific
    docker_image: Optional[str] = None
    docker_user: str = "slovo"
    
    # WASM-specific
    wasm_module: Optional[str] = None


# Default configurations for different trust levels
SANDBOX_PRESETS = {
    "minimal": SandboxConfig(
        sandbox_type=SandboxType.DOCKER,
        network=NetworkPolicy(outbound_allowed=False),
        storage=StoragePolicy(persistent=False, max_size_mb=50),
        resources=ResourceLimits(max_memory_mb=128, max_cpu_percent=25),
    ),
    "standard": SandboxConfig(
        sandbox_type=SandboxType.DOCKER,
        network=NetworkPolicy(outbound_allowed=False),
        storage=StoragePolicy(persistent=True, max_size_mb=100),
        resources=ResourceLimits(max_memory_mb=256, max_cpu_percent=50),
    ),
    "network": SandboxConfig(
        sandbox_type=SandboxType.DOCKER,
        network=NetworkPolicy(outbound_allowed=True, allowed_ports=[80, 443]),
        storage=StoragePolicy(persistent=True, max_size_mb=200),
        resources=ResourceLimits(max_memory_mb=512, max_cpu_percent=75),
    ),
}


def create_sandbox_config_from_manifest(manifest: dict) -> SandboxConfig:
    """
    Create a sandbox configuration from a tool manifest.
    
    Args:
        manifest: Tool manifest dictionary
        
    Returns:
        SandboxConfig instance
    """
    execution = manifest.get("execution", {})
    permissions = manifest.get("permissions", {})
    
    # Determine sandbox type
    sandbox_type = SandboxType(execution.get("type", "docker"))
    
    # Parse network policy
    network_config = permissions.get("network", {})
    network = NetworkPolicy(
        outbound_allowed=network_config.get("outbound", False),
        allowed_hosts=network_config.get("allowedHosts", []),
    )
    
    # Parse storage policy
    storage_config = permissions.get("storage", {})
    storage = StoragePolicy(
        persistent=storage_config.get("persistent", False),
        max_size_mb=storage_config.get("maxSizeMB", 100),
    )
    
    # Parse resource limits
    resource_config = permissions.get("resources", {})
    resources = ResourceLimits(
        max_memory_mb=resource_config.get("maxMemoryMB", 256),
        max_cpu_percent=resource_config.get("maxCpuPercent", 50),
        max_execution_time_seconds=execution.get("timeout", 30),
    )
    
    return SandboxConfig(
        sandbox_type=sandbox_type,
        network=network,
        storage=storage,
        resources=resources,
        docker_image=execution.get("image"),
        wasm_module=execution.get("module"),
    )
