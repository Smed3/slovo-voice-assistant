-- Slovo Tool System - PostgreSQL Schema
-- Phase 4: Autonomous Tool Management

-- =============================================================================
-- Tool Manifest Table
-- =============================================================================
-- Purpose: Store tool definitions, capabilities, and metadata
CREATE TABLE tool_manifest (
    id UUID PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    version TEXT NOT NULL,
    description TEXT NOT NULL,
    source_type TEXT NOT NULL CHECK (source_type IN ('local', 'openapi_url', 'discovered')),
    source_location TEXT NOT NULL,
    
    -- Tool state
    status TEXT NOT NULL DEFAULT 'pending_approval' CHECK (status IN ('pending_approval', 'approved', 'active', 'disabled', 'revoked')),
    
    -- OpenAPI spec storage (for reference)
    openapi_spec JSONB,
    
    -- Generated metadata
    capabilities JSONB DEFAULT '[]'::jsonb,
    parameters_schema JSONB DEFAULT '{}'::jsonb,
    
    -- Execution configuration
    execution_type TEXT DEFAULT 'docker',
    docker_image TEXT,
    docker_entrypoint TEXT,
    execution_timeout INTEGER DEFAULT 30,
    
    -- Timestamps
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    approved_at TIMESTAMP,
    revoked_at TIMESTAMP
);

CREATE INDEX idx_tool_manifest_name ON tool_manifest(name);
CREATE INDEX idx_tool_manifest_status ON tool_manifest(status);
CREATE INDEX idx_tool_manifest_source_type ON tool_manifest(source_type);

-- =============================================================================
-- Tool Permission Table
-- =============================================================================
-- Purpose: Store explicit permissions granted to each tool
CREATE TABLE tool_permission (
    id UUID PRIMARY KEY,
    tool_id UUID NOT NULL REFERENCES tool_manifest(id) ON DELETE CASCADE,
    permission_type TEXT NOT NULL CHECK (permission_type IN ('internet_access', 'storage', 'cpu_limit', 'memory_limit')),
    permission_value TEXT NOT NULL,
    granted_by TEXT NOT NULL DEFAULT 'user',
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_tool_permission_tool_id ON tool_permission(tool_id);
CREATE INDEX idx_tool_permission_type ON tool_permission(permission_type);

-- Ensure unique permission types per tool
CREATE UNIQUE INDEX idx_tool_permission_unique ON tool_permission(tool_id, permission_type);

-- =============================================================================
-- Tool Execution Log Table
-- =============================================================================
-- Purpose: Track all tool executions for verifier review and debugging
CREATE TABLE tool_execution_log (
    id UUID PRIMARY KEY,
    tool_id UUID NOT NULL REFERENCES tool_manifest(id) ON DELETE CASCADE,
    
    -- Execution context
    conversation_id TEXT,
    turn_id TEXT,
    
    -- Execution details
    input_params JSONB NOT NULL,
    started_at TIMESTAMP NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMP,
    duration_ms INTEGER,
    
    -- Results
    status TEXT NOT NULL CHECK (status IN ('running', 'success', 'failure', 'timeout', 'cancelled')),
    output JSONB,
    error_message TEXT,
    exit_code INTEGER,
    
    -- Resource usage
    cpu_usage_ms INTEGER,
    memory_peak_mb INTEGER,
    
    -- Container info
    container_id TEXT,
    
    -- Metadata
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_tool_execution_log_tool_id ON tool_execution_log(tool_id);
CREATE INDEX idx_tool_execution_log_status ON tool_execution_log(status);
CREATE INDEX idx_tool_execution_log_started_at ON tool_execution_log(started_at DESC);
CREATE INDEX idx_tool_execution_log_conversation_id ON tool_execution_log(conversation_id);

-- =============================================================================
-- Tool State Table
-- =============================================================================
-- Purpose: Store persistent state for stateful tools
-- Each tool gets its own isolated state storage
CREATE TABLE tool_state (
    id UUID PRIMARY KEY,
    tool_id UUID NOT NULL REFERENCES tool_manifest(id) ON DELETE CASCADE,
    state_key TEXT NOT NULL,
    state_value JSONB NOT NULL,
    
    -- State metadata
    size_bytes INTEGER NOT NULL,
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_tool_state_tool_id ON tool_state(tool_id);
CREATE INDEX idx_tool_state_updated_at ON tool_state(updated_at DESC);

-- Ensure unique keys per tool
CREATE UNIQUE INDEX idx_tool_state_unique ON tool_state(tool_id, state_key);

-- =============================================================================
-- Tool Volume Table
-- =============================================================================
-- Purpose: Track Docker volumes for tool persistence
CREATE TABLE tool_volume (
    id UUID PRIMARY KEY,
    tool_id UUID NOT NULL REFERENCES tool_manifest(id) ON DELETE CASCADE,
    volume_name TEXT NOT NULL UNIQUE,
    mount_path TEXT NOT NULL,
    size_mb INTEGER,
    quota_mb INTEGER,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_tool_volume_tool_id ON tool_volume(tool_id);
CREATE INDEX idx_tool_volume_name ON tool_volume(volume_name);

-- =============================================================================
-- Update Timestamp Triggers
-- =============================================================================
CREATE TRIGGER update_tool_manifest_updated_at
    BEFORE UPDATE ON tool_manifest
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_tool_state_updated_at
    BEFORE UPDATE ON tool_state
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- =============================================================================
-- Tool Discovery Queue Table
-- =============================================================================
-- Purpose: Track tool discovery requests from planner
CREATE TABLE tool_discovery_queue (
    id UUID PRIMARY KEY,
    
    -- Discovery request details
    capability_description TEXT NOT NULL,
    requested_by TEXT NOT NULL DEFAULT 'planner',
    search_query TEXT,
    
    -- State
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'searching', 'found', 'failed', 'rejected')),
    
    -- Results
    discovered_apis JSONB,
    selected_api TEXT,
    tool_manifest_id UUID REFERENCES tool_manifest(id) ON DELETE SET NULL,
    
    -- Error tracking
    error_message TEXT,
    
    -- Timestamps
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMP
);

CREATE INDEX idx_tool_discovery_queue_status ON tool_discovery_queue(status);
CREATE INDEX idx_tool_discovery_queue_created_at ON tool_discovery_queue(created_at DESC);

CREATE TRIGGER update_tool_discovery_queue_updated_at
    BEFORE UPDATE ON tool_discovery_queue
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
