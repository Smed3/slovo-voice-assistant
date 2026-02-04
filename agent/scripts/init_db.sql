-- Slovo Memory System - PostgreSQL Schema
-- Phase 3: Structured Memory for deterministic facts & preferences

-- =============================================================================
-- User Profile Table
-- =============================================================================
-- Purpose: Single user preferences and settings
-- Rules: Exactly one user (CHECK constraint), no auth tables
CREATE TABLE user_profile (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    preferred_languages TEXT[] NOT NULL DEFAULT ARRAY['en'],
    communication_style TEXT,
    privacy_level TEXT DEFAULT 'standard',
    memory_capture_enabled BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Insert default user profile
INSERT INTO user_profile (id, preferred_languages, communication_style, privacy_level, memory_capture_enabled)
VALUES (1, ARRAY['en'], 'friendly', 'standard', true)
ON CONFLICT (id) DO NOTHING;

-- =============================================================================
-- Episodic Log Table
-- =============================================================================
-- Purpose: Agent decisions, tool failures, verifier feedback for explainability
-- Contents: Reasoning logs, not raw memory
CREATE TABLE episodic_log (
    id UUID PRIMARY KEY,
    timestamp TIMESTAMP NOT NULL DEFAULT NOW(),
    agent TEXT NOT NULL,
    action_type TEXT NOT NULL,
    summary TEXT NOT NULL,
    confidence REAL NOT NULL CHECK (confidence >= 0.0 AND confidence <= 1.0),
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Index for efficient time-based queries
CREATE INDEX idx_episodic_log_timestamp ON episodic_log(timestamp DESC);
CREATE INDEX idx_episodic_log_agent ON episodic_log(agent);

-- =============================================================================
-- User Preferences Table
-- =============================================================================
-- Purpose: Structured key-value preferences verified by user or verifier
CREATE TABLE user_preference (
    id UUID PRIMARY KEY,
    key TEXT NOT NULL UNIQUE,
    value TEXT NOT NULL,
    source TEXT NOT NULL CHECK (source IN ('user_edit', 'verifier_approved', 'system_default')),
    confidence REAL NOT NULL CHECK (confidence >= 0.0 AND confidence <= 1.0),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Index for key lookups
CREATE INDEX idx_user_preference_key ON user_preference(key);

-- =============================================================================
-- Memory Metadata Table
-- =============================================================================
-- Purpose: Track all memory entries across stores for Memory Inspector
CREATE TABLE memory_metadata (
    id UUID PRIMARY KEY,
    memory_type TEXT NOT NULL CHECK (memory_type IN ('semantic', 'episodic', 'preference')),
    store_location TEXT NOT NULL CHECK (store_location IN ('qdrant', 'postgres', 'redis')),
    summary TEXT NOT NULL,
    source TEXT NOT NULL CHECK (source IN ('conversation', 'tool', 'user_edit', 'verifier')),
    confidence REAL NOT NULL CHECK (confidence >= 0.0 AND confidence <= 1.0),
    is_deleted BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Indexes for Memory Inspector queries
CREATE INDEX idx_memory_metadata_type ON memory_metadata(memory_type);
CREATE INDEX idx_memory_metadata_source ON memory_metadata(source);
CREATE INDEX idx_memory_metadata_created ON memory_metadata(created_at DESC);
CREATE INDEX idx_memory_metadata_not_deleted ON memory_metadata(is_deleted) WHERE is_deleted = false;

-- =============================================================================
-- Update Timestamp Trigger
-- =============================================================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_user_profile_updated_at
    BEFORE UPDATE ON user_profile
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_user_preference_updated_at
    BEFORE UPDATE ON user_preference
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_memory_metadata_updated_at
    BEFORE UPDATE ON memory_metadata
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
