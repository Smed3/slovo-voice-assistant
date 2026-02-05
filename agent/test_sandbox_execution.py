"""
Test tool execution configuration in sandbox.

This test verifies that:
1. Sandbox uses actual tool command from manifest when available
2. Falls back to placeholder when execution config is missing
3. Docker container is configured correctly with manifest settings
"""

import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from slovo_agent.models import (
    ExecutionStatus,
    PermissionType,
    ToolManifestDB,
    ToolPermissionDB,
    ToolSourceType,
    ToolStatus,
)
from slovo_agent.tools.sandbox import DockerSandboxManager


@pytest.fixture
def mock_tool_repository():
    """Mock tool repository."""
    repo = MagicMock()
    repo.create_tool_execution = AsyncMock()
    repo.update_tool_execution = AsyncMock()
    repo.list_tool_volumes = AsyncMock(return_value=[])
    repo.create_tool_volume = AsyncMock()
    return repo


@pytest.fixture
def tool_manifest_with_execution():
    """Tool manifest with execution configuration."""
    return ToolManifestDB(
        id=uuid.uuid4(),
        name="test-tool",
        version="1.0.0",
        description="Test tool with execution config",
        source_type=ToolSourceType.LOCAL,
        source_location="/test/manifest.json",
        status=ToolStatus.APPROVED,
        openapi_spec=None,
        capabilities=[],
        parameters_schema={},
        execution_type="docker",
        docker_image="slovo/test-tool:latest",
        docker_entrypoint="python /app/main.py",
        execution_timeout=30,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        approved_at=datetime.utcnow(),
        revoked_at=None,
    )


@pytest.fixture
def tool_manifest_without_execution():
    """Tool manifest without execution configuration."""
    return ToolManifestDB(
        id=uuid.uuid4(),
        name="test-tool-no-exec",
        version="1.0.0",
        description="Test tool without execution config",
        source_type=ToolSourceType.LOCAL,
        source_location="/test/manifest.json",
        status=ToolStatus.APPROVED,
        openapi_spec=None,
        capabilities=[],
        parameters_schema={},
        execution_type=None,
        docker_image=None,
        docker_entrypoint=None,
        execution_timeout=30,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        approved_at=datetime.utcnow(),
        revoked_at=None,
    )


@pytest.fixture
def permissions():
    """Tool permissions."""
    tool_id = uuid.uuid4()
    return [
        ToolPermissionDB(
            id=uuid.uuid4(),
            tool_id=tool_id,
            permission_type=PermissionType.INTERNET_ACCESS,
            permission_value="false",
            granted_by="user",
            created_at=datetime.utcnow(),
        ),
        ToolPermissionDB(
            id=uuid.uuid4(),
            tool_id=tool_id,
            permission_type=PermissionType.CPU_LIMIT,
            permission_value="50",
            granted_by="user",
            created_at=datetime.utcnow(),
        ),
        ToolPermissionDB(
            id=uuid.uuid4(),
            tool_id=tool_id,
            permission_type=PermissionType.MEMORY_LIMIT,
            permission_value="512",
            granted_by="user",
            created_at=datetime.utcnow(),
        ),
    ]


@pytest.mark.asyncio
async def test_uses_manifest_execution_config(
    mock_tool_repository, tool_manifest_with_execution, permissions
):
    """Test that sandbox uses execution config from manifest."""
    # Skip Docker connection for this test
    with patch("slovo_agent.tools.sandbox.docker.from_env") as mock_docker:
        mock_client = MagicMock()
        mock_docker.return_value = mock_client
        
        sandbox = DockerSandboxManager(mock_tool_repository)
        
        # Build container config
        config = await sandbox._build_container_config(
            tool_manifest_with_execution,
            permissions,
            {"test_param": "test_value"},
        )
        
        # Verify it uses the manifest's docker image
        assert config["image"] == "slovo/test-tool:latest"
        
        # Verify it uses the manifest's entrypoint
        assert config["command"] == ["python", "/app/main.py"]
        
        # Verify environment variable is set
        assert "TOOL_PARAMS" in config["environment"]


@pytest.mark.asyncio
async def test_falls_back_to_placeholder(
    mock_tool_repository, tool_manifest_without_execution, permissions
):
    """Test that sandbox falls back to placeholder when execution config is missing."""
    # Skip Docker connection for this test
    with patch("slovo_agent.tools.sandbox.docker.from_env") as mock_docker:
        mock_client = MagicMock()
        mock_docker.return_value = mock_client
        
        sandbox = DockerSandboxManager(mock_tool_repository)
        
        # Build container config
        config = await sandbox._build_container_config(
            tool_manifest_without_execution,
            permissions,
            {"test_param": "test_value"},
        )
        
        # Verify it falls back to placeholder image
        assert config["image"] == "python:3.11-slim"
        
        # Verify it uses placeholder command
        assert "python" in config["command"]
        assert "-c" in config["command"]
        
        # Verify environment variable is set
        assert "TOOL_PARAMS" in config["environment"]


@pytest.mark.asyncio
async def test_container_config_enforces_permissions(
    mock_tool_repository, tool_manifest_with_execution, permissions
):
    """Test that container config correctly enforces permissions."""
    # Skip Docker connection for this test
    with patch("slovo_agent.tools.sandbox.docker.from_env") as mock_docker:
        mock_client = MagicMock()
        mock_docker.return_value = mock_client
        
        sandbox = DockerSandboxManager(mock_tool_repository)
        
        # Build container config
        config = await sandbox._build_container_config(
            tool_manifest_with_execution,
            permissions,
            {"test_param": "test_value"},
        )
        
        # Verify network is disabled (no internet access)
        assert config["network_mode"] == "none"
        
        # Verify CPU limit (50% = 50000 quota)
        assert config["cpu_quota"] == 50000
        assert config["cpu_period"] == 100000
        
        # Verify memory limit
        assert config["mem_limit"] == "512m"
        
        # Verify security settings
        assert config["read_only"] is True
        assert "no-new-privileges:true" in config["security_opt"]
        assert "ALL" in config["cap_drop"]


@pytest.mark.asyncio
async def test_entrypoint_can_be_list(
    mock_tool_repository, permissions
):
    """Test that entrypoint can be provided as a list."""
    # Create manifest with list entrypoint
    manifest = ToolManifestDB(
        id=uuid.uuid4(),
        name="test-tool",
        version="1.0.0",
        description="Test tool",
        source_type=ToolSourceType.LOCAL,
        source_location="/test/manifest.json",
        status=ToolStatus.APPROVED,
        openapi_spec=None,
        capabilities=[],
        parameters_schema={},
        execution_type="docker",
        docker_image="slovo/test-tool:latest",
        docker_entrypoint=["node", "/app/index.js", "--verbose"],
        execution_timeout=30,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        approved_at=datetime.utcnow(),
        revoked_at=None,
    )
    
    # Skip Docker connection for this test
    with patch("slovo_agent.tools.sandbox.docker.from_env") as mock_docker:
        mock_client = MagicMock()
        mock_docker.return_value = mock_client
        
        sandbox = DockerSandboxManager(mock_tool_repository)
        
        # Build container config
        config = await sandbox._build_container_config(
            manifest,
            permissions,
            {"test_param": "test_value"},
        )
        
        # Verify it uses the list entrypoint
        assert config["command"] == ["node", "/app/index.js", "--verbose"]
