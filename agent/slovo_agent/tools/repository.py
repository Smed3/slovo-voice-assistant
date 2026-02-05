"""
PostgreSQL Repository for Tool Management.

Phase 4: Autonomous tool lifecycle management
- Tool manifests and metadata
- Permission management
- Execution logging
- State persistence
"""

from datetime import datetime
from uuid import UUID, uuid4

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from slovo_agent.models import (
    DiscoveryStatus,
    ExecutionStatus,
    PermissionType,
    ToolDiscoveryQueueDB,
    ToolDiscoveryRequest,
    ToolDiscoveryUpdate,
    ToolExecutionCreate,
    ToolExecutionLogDB,
    ToolExecutionUpdate,
    ToolManifestCreate,
    ToolManifestDB,
    ToolManifestUpdate,
    ToolPermissionCreate,
    ToolPermissionDB,
    ToolSourceType,
    ToolStateCreate,
    ToolStateDB,
    ToolStateUpdate,
    ToolStatus,
    ToolVolumeCreate,
    ToolVolumeDB,
)

logger = structlog.get_logger(__name__)


class ToolRepository:
    """
    Repository for tool management in PostgreSQL.

    Used for:
    - Tool manifest storage and versioning
    - Permission tracking
    - Execution logging
    - State persistence
    - Discovery queue management
    """

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        """
        Initialize tool repository.

        Args:
            session_factory: SQLAlchemy async session factory
        """
        self._session_factory = session_factory
        logger.info("Tool repository initialized")

    # =========================================================================
    # Tool Manifest Management
    # =========================================================================

    async def create_tool_manifest(self, manifest: ToolManifestCreate) -> ToolManifestDB:
        """
        Create a new tool manifest.

        Args:
            manifest: Tool manifest to create

        Returns:
            Created tool manifest with ID
        """
        tool_id = uuid4()
        now = datetime.utcnow()

        async with self._session_factory() as session:
            await session.execute(
                text("""
                    INSERT INTO tool_manifest (
                        id, name, version, description, source_type, source_location,
                        status, openapi_spec, capabilities, parameters_schema,
                        created_at, updated_at
                    ) VALUES (
                        :id, :name, :version, :description, :source_type, :source_location,
                        :status, :openapi_spec, :capabilities, :parameters_schema,
                        :created_at, :updated_at
                    )
                """),
                {
                    "id": tool_id,
                    "name": manifest.name,
                    "version": manifest.version,
                    "description": manifest.description,
                    "source_type": manifest.source_type.value,
                    "source_location": manifest.source_location,
                    "status": ToolStatus.PENDING_APPROVAL.value,
                    "openapi_spec": manifest.openapi_spec,
                    "capabilities": manifest.capabilities,
                    "parameters_schema": manifest.parameters_schema,
                    "created_at": now,
                    "updated_at": now,
                },
            )
            await session.commit()

        logger.info("Tool manifest created", tool_id=str(tool_id), name=manifest.name)

        return await self.get_tool_manifest(tool_id)

    async def get_tool_manifest(self, tool_id: UUID) -> ToolManifestDB:
        """
        Get a tool manifest by ID.

        Args:
            tool_id: Tool UUID

        Returns:
            Tool manifest

        Raises:
            ValueError: If tool not found
        """
        async with self._session_factory() as session:
            result = await session.execute(
                text("""
                    SELECT id, name, version, description, source_type, source_location,
                           status, openapi_spec, capabilities, parameters_schema,
                           created_at, updated_at, approved_at, revoked_at
                    FROM tool_manifest
                    WHERE id = :id
                """),
                {"id": tool_id},
            )
            row = result.fetchone()

            if row is None:
                raise ValueError(f"Tool not found: {tool_id}")

            return ToolManifestDB(
                id=row[0],
                name=row[1],
                version=row[2],
                description=row[3],
                source_type=ToolSourceType(row[4]),
                source_location=row[5],
                status=ToolStatus(row[6]),
                openapi_spec=row[7],
                capabilities=row[8] or [],
                parameters_schema=row[9] or {},
                created_at=row[10],
                updated_at=row[11],
                approved_at=row[12],
                revoked_at=row[13],
            )

    async def get_tool_manifest_by_name(self, name: str) -> ToolManifestDB | None:
        """
        Get a tool manifest by name.

        Args:
            name: Tool name

        Returns:
            Tool manifest or None if not found
        """
        async with self._session_factory() as session:
            result = await session.execute(
                text("""
                    SELECT id, name, version, description, source_type, source_location,
                           status, openapi_spec, capabilities, parameters_schema,
                           created_at, updated_at, approved_at, revoked_at
                    FROM tool_manifest
                    WHERE name = :name
                    ORDER BY created_at DESC
                    LIMIT 1
                """),
                {"name": name},
            )
            row = result.fetchone()

            if row is None:
                return None

            return ToolManifestDB(
                id=row[0],
                name=row[1],
                version=row[2],
                description=row[3],
                source_type=ToolSourceType(row[4]),
                source_location=row[5],
                status=ToolStatus(row[6]),
                openapi_spec=row[7],
                capabilities=row[8] or [],
                parameters_schema=row[9] or {},
                created_at=row[10],
                updated_at=row[11],
                approved_at=row[12],
                revoked_at=row[13],
            )

    async def list_tool_manifests(
        self, status: ToolStatus | None = None, limit: int = 100, offset: int = 0
    ) -> list[ToolManifestDB]:
        """
        List tool manifests with optional filtering.

        Args:
            status: Optional status filter
            limit: Maximum number of results
            offset: Offset for pagination

        Returns:
            List of tool manifests
        """
        async with self._session_factory() as session:
            if status:
                result = await session.execute(
                    text("""
                        SELECT id, name, version, description, source_type, source_location,
                               status, openapi_spec, capabilities, parameters_schema,
                               created_at, updated_at, approved_at, revoked_at
                        FROM tool_manifest
                        WHERE status = :status
                        ORDER BY created_at DESC
                        LIMIT :limit OFFSET :offset
                    """),
                    {"status": status.value, "limit": limit, "offset": offset},
                )
            else:
                result = await session.execute(
                    text("""
                        SELECT id, name, version, description, source_type, source_location,
                               status, openapi_spec, capabilities, parameters_schema,
                               created_at, updated_at, approved_at, revoked_at
                        FROM tool_manifest
                        ORDER BY created_at DESC
                        LIMIT :limit OFFSET :offset
                    """),
                    {"limit": limit, "offset": offset},
                )

            manifests = []
            for row in result:
                manifests.append(
                    ToolManifestDB(
                        id=row[0],
                        name=row[1],
                        version=row[2],
                        description=row[3],
                        source_type=ToolSourceType(row[4]),
                        source_location=row[5],
                        status=ToolStatus(row[6]),
                        openapi_spec=row[7],
                        capabilities=row[8] or [],
                        parameters_schema=row[9] or {},
                        created_at=row[10],
                        updated_at=row[11],
                        approved_at=row[12],
                        revoked_at=row[13],
                    )
                )

            return manifests

    async def update_tool_manifest(
        self, tool_id: UUID, update: ToolManifestUpdate
    ) -> ToolManifestDB:
        """
        Update a tool manifest.

        Args:
            tool_id: Tool UUID
            update: Fields to update

        Returns:
            Updated tool manifest
        """
        updates = {}
        if update.version is not None:
            updates["version"] = update.version
        if update.description is not None:
            updates["description"] = update.description
        if update.status is not None:
            updates["status"] = update.status.value
            if update.status == ToolStatus.APPROVED:
                updates["approved_at"] = datetime.utcnow()
            elif update.status == ToolStatus.REVOKED:
                updates["revoked_at"] = datetime.utcnow()
        if update.openapi_spec is not None:
            updates["openapi_spec"] = update.openapi_spec
        if update.capabilities is not None:
            updates["capabilities"] = update.capabilities
        if update.parameters_schema is not None:
            updates["parameters_schema"] = update.parameters_schema

        if not updates:
            return await self.get_tool_manifest(tool_id)

        updates["updated_at"] = datetime.utcnow()

        # Build UPDATE query dynamically
        set_clause = ", ".join([f"{k} = :{k}" for k in updates.keys()])
        updates["id"] = tool_id

        async with self._session_factory() as session:
            await session.execute(
                text(f"UPDATE tool_manifest SET {set_clause} WHERE id = :id"),
                updates,
            )
            await session.commit()

        logger.info("Tool manifest updated", tool_id=str(tool_id))

        return await self.get_tool_manifest(tool_id)

    async def delete_tool_manifest(self, tool_id: UUID) -> None:
        """
        Delete a tool manifest and all related data.

        Args:
            tool_id: Tool UUID
        """
        async with self._session_factory() as session:
            await session.execute(
                text("DELETE FROM tool_manifest WHERE id = :id"),
                {"id": tool_id},
            )
            await session.commit()

        logger.info("Tool manifest deleted", tool_id=str(tool_id))

    # =========================================================================
    # Tool Permission Management
    # =========================================================================

    async def create_tool_permission(
        self, permission: ToolPermissionCreate
    ) -> ToolPermissionDB:
        """
        Create a tool permission.

        Args:
            permission: Permission to create

        Returns:
            Created permission
        """
        permission_id = uuid4()
        now = datetime.utcnow()

        async with self._session_factory() as session:
            await session.execute(
                text("""
                    INSERT INTO tool_permission (
                        id, tool_id, permission_type, permission_value, granted_by, created_at
                    ) VALUES (
                        :id, :tool_id, :permission_type, :permission_value, :granted_by, :created_at
                    )
                    ON CONFLICT (tool_id, permission_type)
                    DO UPDATE SET
                        permission_value = EXCLUDED.permission_value,
                        granted_by = EXCLUDED.granted_by
                    RETURNING id
                """),
                {
                    "id": permission_id,
                    "tool_id": permission.tool_id,
                    "permission_type": permission.permission_type.value,
                    "permission_value": permission.permission_value,
                    "granted_by": permission.granted_by,
                    "created_at": now,
                },
            )
            result = await session.execute(
                text("SELECT id FROM tool_permission WHERE tool_id = :tool_id AND permission_type = :permission_type"),
                {"tool_id": permission.tool_id, "permission_type": permission.permission_type.value}
            )
            row = result.fetchone()
            if row:
                permission_id = row[0]
            await session.commit()

        logger.info(
            "Tool permission created",
            tool_id=str(permission.tool_id),
            permission_type=permission.permission_type.value,
        )

        return await self.get_tool_permission(permission_id)

    async def get_tool_permission(self, permission_id: UUID) -> ToolPermissionDB:
        """
        Get a tool permission by ID.

        Args:
            permission_id: Permission UUID

        Returns:
            Tool permission

        Raises:
            ValueError: If permission not found
        """
        async with self._session_factory() as session:
            result = await session.execute(
                text("""
                    SELECT id, tool_id, permission_type, permission_value, granted_by, created_at
                    FROM tool_permission
                    WHERE id = :id
                """),
                {"id": permission_id},
            )
            row = result.fetchone()

            if row is None:
                raise ValueError(f"Permission not found: {permission_id}")

            return ToolPermissionDB(
                id=row[0],
                tool_id=row[1],
                permission_type=PermissionType(row[2]),
                permission_value=row[3],
                granted_by=row[4],
                created_at=row[5],
            )

    async def list_tool_permissions(self, tool_id: UUID) -> list[ToolPermissionDB]:
        """
        List all permissions for a tool.

        Args:
            tool_id: Tool UUID

        Returns:
            List of permissions
        """
        async with self._session_factory() as session:
            result = await session.execute(
                text("""
                    SELECT id, tool_id, permission_type, permission_value, granted_by, created_at
                    FROM tool_permission
                    WHERE tool_id = :tool_id
                    ORDER BY created_at DESC
                """),
                {"tool_id": tool_id},
            )

            permissions = []
            for row in result:
                permissions.append(
                    ToolPermissionDB(
                        id=row[0],
                        tool_id=row[1],
                        permission_type=PermissionType(row[2]),
                        permission_value=row[3],
                        granted_by=row[4],
                        created_at=row[5],
                    )
                )

            return permissions

    # =========================================================================
    # Tool Execution Logging
    # =========================================================================

    async def create_tool_execution(
        self, execution: ToolExecutionCreate
    ) -> ToolExecutionLogDB:
        """
        Create a tool execution log entry.

        Args:
            execution: Execution to log

        Returns:
            Created execution log
        """
        execution_id = uuid4()
        now = datetime.utcnow()

        async with self._session_factory() as session:
            await session.execute(
                text("""
                    INSERT INTO tool_execution_log (
                        id, tool_id, conversation_id, turn_id, input_params,
                        started_at, status, created_at
                    ) VALUES (
                        :id, :tool_id, :conversation_id, :turn_id, :input_params,
                        :started_at, :status, :created_at
                    )
                """),
                {
                    "id": execution_id,
                    "tool_id": execution.tool_id,
                    "conversation_id": execution.conversation_id,
                    "turn_id": execution.turn_id,
                    "input_params": execution.input_params,
                    "started_at": now,
                    "status": ExecutionStatus.RUNNING.value,
                    "created_at": now,
                },
            )
            await session.commit()

        logger.info("Tool execution logged", execution_id=str(execution_id))

        return await self.get_tool_execution(execution_id)

    async def get_tool_execution(self, execution_id: UUID) -> ToolExecutionLogDB:
        """
        Get a tool execution log by ID.

        Args:
            execution_id: Execution UUID

        Returns:
            Tool execution log

        Raises:
            ValueError: If execution not found
        """
        async with self._session_factory() as session:
            result = await session.execute(
                text("""
                    SELECT id, tool_id, conversation_id, turn_id, input_params,
                           started_at, completed_at, duration_ms, status, output,
                           error_message, exit_code, cpu_usage_ms, memory_peak_mb,
                           container_id, created_at
                    FROM tool_execution_log
                    WHERE id = :id
                """),
                {"id": execution_id},
            )
            row = result.fetchone()

            if row is None:
                raise ValueError(f"Execution not found: {execution_id}")

            return ToolExecutionLogDB(
                id=row[0],
                tool_id=row[1],
                conversation_id=row[2],
                turn_id=row[3],
                input_params=row[4] or {},
                started_at=row[5],
                completed_at=row[6],
                duration_ms=row[7],
                status=ExecutionStatus(row[8]),
                output=row[9],
                error_message=row[10],
                exit_code=row[11],
                cpu_usage_ms=row[12],
                memory_peak_mb=row[13],
                container_id=row[14],
                created_at=row[15],
            )

    async def update_tool_execution(
        self, execution_id: UUID, update: ToolExecutionUpdate
    ) -> ToolExecutionLogDB:
        """
        Update a tool execution log.

        Args:
            execution_id: Execution UUID
            update: Fields to update

        Returns:
            Updated execution log
        """
        updates = {}
        if update.completed_at is not None:
            updates["completed_at"] = update.completed_at
        if update.duration_ms is not None:
            updates["duration_ms"] = update.duration_ms
        if update.status is not None:
            updates["status"] = update.status.value
        if update.output is not None:
            updates["output"] = update.output
        if update.error_message is not None:
            updates["error_message"] = update.error_message
        if update.exit_code is not None:
            updates["exit_code"] = update.exit_code
        if update.cpu_usage_ms is not None:
            updates["cpu_usage_ms"] = update.cpu_usage_ms
        if update.memory_peak_mb is not None:
            updates["memory_peak_mb"] = update.memory_peak_mb
        if update.container_id is not None:
            updates["container_id"] = update.container_id

        if not updates:
            return await self.get_tool_execution(execution_id)

        # Build UPDATE query dynamically
        set_clause = ", ".join([f"{k} = :{k}" for k in updates.keys()])
        updates["id"] = execution_id

        async with self._session_factory() as session:
            await session.execute(
                text(f"UPDATE tool_execution_log SET {set_clause} WHERE id = :id"),
                updates,
            )
            await session.commit()

        return await self.get_tool_execution(execution_id)

    async def list_tool_executions(
        self, tool_id: UUID | None = None, status: ExecutionStatus | None = None, limit: int = 100
    ) -> list[ToolExecutionLogDB]:
        """
        List tool execution logs with optional filtering.

        Args:
            tool_id: Optional tool UUID filter
            status: Optional status filter
            limit: Maximum number of results

        Returns:
            List of execution logs
        """
        conditions = []
        params: dict[str, Any] = {"limit": limit}

        if tool_id:
            conditions.append("tool_id = :tool_id")
            params["tool_id"] = tool_id

        if status:
            conditions.append("status = :status")
            params["status"] = status.value

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        async with self._session_factory() as session:
            result = await session.execute(
                text(f"""
                    SELECT id, tool_id, conversation_id, turn_id, input_params,
                           started_at, completed_at, duration_ms, status, output,
                           error_message, exit_code, cpu_usage_ms, memory_peak_mb,
                           container_id, created_at
                    FROM tool_execution_log
                    WHERE {where_clause}
                    ORDER BY started_at DESC
                    LIMIT :limit
                """),
                params,
            )

            executions = []
            for row in result:
                executions.append(
                    ToolExecutionLogDB(
                        id=row[0],
                        tool_id=row[1],
                        conversation_id=row[2],
                        turn_id=row[3],
                        input_params=row[4] or {},
                        started_at=row[5],
                        completed_at=row[6],
                        duration_ms=row[7],
                        status=ExecutionStatus(row[8]),
                        output=row[9],
                        error_message=row[10],
                        exit_code=row[11],
                        cpu_usage_ms=row[12],
                        memory_peak_mb=row[13],
                        container_id=row[14],
                        created_at=row[15],
                    )
                )

            return executions

    # =========================================================================
    # Tool State Management
    # =========================================================================

    async def create_or_update_tool_state(
        self, tool_id: UUID, state_key: str, state_value: dict, size_bytes: int
    ) -> ToolStateDB:
        """
        Create or update tool state.

        Args:
            tool_id: Tool UUID
            state_key: State key
            state_value: State value
            size_bytes: Size in bytes

        Returns:
            Created or updated tool state
        """
        state_id = uuid4()
        now = datetime.utcnow()

        async with self._session_factory() as session:
            await session.execute(
                text("""
                    INSERT INTO tool_state (
                        id, tool_id, state_key, state_value, size_bytes, created_at, updated_at
                    ) VALUES (
                        :id, :tool_id, :state_key, :state_value, :size_bytes, :created_at, :updated_at
                    )
                    ON CONFLICT (tool_id, state_key)
                    DO UPDATE SET
                        state_value = EXCLUDED.state_value,
                        size_bytes = EXCLUDED.size_bytes,
                        updated_at = EXCLUDED.updated_at
                    RETURNING id
                """),
                {
                    "id": state_id,
                    "tool_id": tool_id,
                    "state_key": state_key,
                    "state_value": state_value,
                    "size_bytes": size_bytes,
                    "created_at": now,
                    "updated_at": now,
                },
            )
            result = await session.execute(
                text("SELECT id FROM tool_state WHERE tool_id = :tool_id AND state_key = :state_key"),
                {"tool_id": tool_id, "state_key": state_key}
            )
            row = result.fetchone()
            if row:
                state_id = row[0]
            await session.commit()

        return await self.get_tool_state(state_id)

    async def get_tool_state(self, state_id: UUID) -> ToolStateDB:
        """
        Get tool state by ID.

        Args:
            state_id: State UUID

        Returns:
            Tool state

        Raises:
            ValueError: If state not found
        """
        async with self._session_factory() as session:
            result = await session.execute(
                text("""
                    SELECT id, tool_id, state_key, state_value, size_bytes, updated_at, created_at
                    FROM tool_state
                    WHERE id = :id
                """),
                {"id": state_id},
            )
            row = result.fetchone()

            if row is None:
                raise ValueError(f"State not found: {state_id}")

            return ToolStateDB(
                id=row[0],
                tool_id=row[1],
                state_key=row[2],
                state_value=row[3] or {},
                size_bytes=row[4],
                updated_at=row[5],
                created_at=row[6],
            )

    async def get_tool_state_by_key(
        self, tool_id: UUID, state_key: str
    ) -> ToolStateDB | None:
        """
        Get tool state by tool ID and key.

        Args:
            tool_id: Tool UUID
            state_key: State key

        Returns:
            Tool state or None if not found
        """
        async with self._session_factory() as session:
            result = await session.execute(
                text("""
                    SELECT id, tool_id, state_key, state_value, size_bytes, updated_at, created_at
                    FROM tool_state
                    WHERE tool_id = :tool_id AND state_key = :state_key
                """),
                {"tool_id": tool_id, "state_key": state_key},
            )
            row = result.fetchone()

            if row is None:
                return None

            return ToolStateDB(
                id=row[0],
                tool_id=row[1],
                state_key=row[2],
                state_value=row[3] or {},
                size_bytes=row[4],
                updated_at=row[5],
                created_at=row[6],
            )

    # =========================================================================
    # Tool Volume Management
    # =========================================================================

    async def create_tool_volume(self, volume: ToolVolumeCreate) -> ToolVolumeDB:
        """
        Create a tool volume record.

        Args:
            volume: Volume to create

        Returns:
            Created volume
        """
        volume_id = uuid4()
        now = datetime.utcnow()

        async with self._session_factory() as session:
            await session.execute(
                text("""
                    INSERT INTO tool_volume (
                        id, tool_id, volume_name, mount_path, quota_mb, created_at
                    ) VALUES (
                        :id, :tool_id, :volume_name, :mount_path, :quota_mb, :created_at
                    )
                """),
                {
                    "id": volume_id,
                    "tool_id": volume.tool_id,
                    "volume_name": volume.volume_name,
                    "mount_path": volume.mount_path,
                    "quota_mb": volume.quota_mb,
                    "created_at": now,
                },
            )
            await session.commit()

        logger.info("Tool volume created", volume_id=str(volume_id))

        return await self.get_tool_volume(volume_id)

    async def get_tool_volume(self, volume_id: UUID) -> ToolVolumeDB:
        """
        Get a tool volume by ID.

        Args:
            volume_id: Volume UUID

        Returns:
            Tool volume

        Raises:
            ValueError: If volume not found
        """
        async with self._session_factory() as session:
            result = await session.execute(
                text("""
                    SELECT id, tool_id, volume_name, mount_path, size_mb, quota_mb, created_at
                    FROM tool_volume
                    WHERE id = :id
                """),
                {"id": volume_id},
            )
            row = result.fetchone()

            if row is None:
                raise ValueError(f"Volume not found: {volume_id}")

            return ToolVolumeDB(
                id=row[0],
                tool_id=row[1],
                volume_name=row[2],
                mount_path=row[3],
                size_mb=row[4],
                quota_mb=row[5],
                created_at=row[6],
            )

    async def list_tool_volumes(self, tool_id: UUID) -> list[ToolVolumeDB]:
        """
        List all volumes for a tool.

        Args:
            tool_id: Tool UUID

        Returns:
            List of volumes
        """
        async with self._session_factory() as session:
            result = await session.execute(
                text("""
                    SELECT id, tool_id, volume_name, mount_path, size_mb, quota_mb, created_at
                    FROM tool_volume
                    WHERE tool_id = :tool_id
                    ORDER BY created_at DESC
                """),
                {"tool_id": tool_id},
            )

            volumes = []
            for row in result:
                volumes.append(
                    ToolVolumeDB(
                        id=row[0],
                        tool_id=row[1],
                        volume_name=row[2],
                        mount_path=row[3],
                        size_mb=row[4],
                        quota_mb=row[5],
                        created_at=row[6],
                    )
                )

            return volumes

    # =========================================================================
    # Tool Discovery Queue
    # =========================================================================

    async def create_discovery_request(
        self, request: ToolDiscoveryRequest
    ) -> ToolDiscoveryQueueDB:
        """
        Create a tool discovery request.

        Args:
            request: Discovery request

        Returns:
            Created discovery request
        """
        request_id = uuid4()
        now = datetime.utcnow()

        async with self._session_factory() as session:
            await session.execute(
                text("""
                    INSERT INTO tool_discovery_queue (
                        id, capability_description, requested_by, search_query,
                        status, created_at, updated_at
                    ) VALUES (
                        :id, :capability_description, :requested_by, :search_query,
                        :status, :created_at, :updated_at
                    )
                """),
                {
                    "id": request_id,
                    "capability_description": request.capability_description,
                    "requested_by": request.requested_by,
                    "search_query": request.search_query,
                    "status": DiscoveryStatus.PENDING.value,
                    "created_at": now,
                    "updated_at": now,
                },
            )
            await session.commit()

        logger.info("Discovery request created", request_id=str(request_id))

        return await self.get_discovery_request(request_id)

    async def get_discovery_request(self, request_id: UUID) -> ToolDiscoveryQueueDB:
        """
        Get a discovery request by ID.

        Args:
            request_id: Request UUID

        Returns:
            Discovery request

        Raises:
            ValueError: If request not found
        """
        async with self._session_factory() as session:
            result = await session.execute(
                text("""
                    SELECT id, capability_description, requested_by, search_query, status,
                           discovered_apis, selected_api, tool_manifest_id, error_message,
                           created_at, updated_at, completed_at
                    FROM tool_discovery_queue
                    WHERE id = :id
                """),
                {"id": request_id},
            )
            row = result.fetchone()

            if row is None:
                raise ValueError(f"Discovery request not found: {request_id}")

            return ToolDiscoveryQueueDB(
                id=row[0],
                capability_description=row[1],
                requested_by=row[2],
                search_query=row[3],
                status=DiscoveryStatus(row[4]),
                discovered_apis=row[5],
                selected_api=row[6],
                tool_manifest_id=row[7],
                error_message=row[8],
                created_at=row[9],
                updated_at=row[10],
                completed_at=row[11],
            )

    async def update_discovery_request(
        self, request_id: UUID, update: ToolDiscoveryUpdate
    ) -> ToolDiscoveryQueueDB:
        """
        Update a discovery request.

        Args:
            request_id: Request UUID
            update: Fields to update

        Returns:
            Updated discovery request
        """
        updates = {"updated_at": datetime.utcnow()}

        if update.status is not None:
            updates["status"] = update.status.value
        if update.discovered_apis is not None:
            updates["discovered_apis"] = update.discovered_apis
        if update.selected_api is not None:
            updates["selected_api"] = update.selected_api
        if update.tool_manifest_id is not None:
            updates["tool_manifest_id"] = update.tool_manifest_id
        if update.error_message is not None:
            updates["error_message"] = update.error_message
        if update.completed_at is not None:
            updates["completed_at"] = update.completed_at

        # Build UPDATE query dynamically
        set_clause = ", ".join([f"{k} = :{k}" for k in updates.keys()])
        updates["id"] = request_id

        async with self._session_factory() as session:
            await session.execute(
                text(f"UPDATE tool_discovery_queue SET {set_clause} WHERE id = :id"),
                updates,
            )
            await session.commit()

        return await self.get_discovery_request(request_id)

    async def list_discovery_requests(
        self, status: DiscoveryStatus | None = None, limit: int = 100
    ) -> list[ToolDiscoveryQueueDB]:
        """
        List discovery requests with optional filtering.

        Args:
            status: Optional status filter
            limit: Maximum number of results

        Returns:
            List of discovery requests
        """
        async with self._session_factory() as session:
            if status:
                result = await session.execute(
                    text("""
                        SELECT id, capability_description, requested_by, search_query, status,
                               discovered_apis, selected_api, tool_manifest_id, error_message,
                               created_at, updated_at, completed_at
                        FROM tool_discovery_queue
                        WHERE status = :status
                        ORDER BY created_at DESC
                        LIMIT :limit
                    """),
                    {"status": status.value, "limit": limit},
                )
            else:
                result = await session.execute(
                    text("""
                        SELECT id, capability_description, requested_by, search_query, status,
                               discovered_apis, selected_api, tool_manifest_id, error_message,
                               created_at, updated_at, completed_at
                        FROM tool_discovery_queue
                        ORDER BY created_at DESC
                        LIMIT :limit
                    """),
                    {"limit": limit},
                )

            requests = []
            for row in result:
                requests.append(
                    ToolDiscoveryQueueDB(
                        id=row[0],
                        capability_description=row[1],
                        requested_by=row[2],
                        search_query=row[3],
                        status=DiscoveryStatus(row[4]),
                        discovered_apis=row[5],
                        selected_api=row[6],
                        tool_manifest_id=row[7],
                        error_message=row[8],
                        created_at=row[9],
                        updated_at=row[10],
                        completed_at=row[11],
                    )
                )

            return requests
