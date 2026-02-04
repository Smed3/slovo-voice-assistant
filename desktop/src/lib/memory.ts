/**
 * Memory API Client for Slovo Voice Assistant
 *
 * Phase 3: Memory Inspector UI
 * Provides TypeScript interfaces and API functions for memory management.
 */

const AGENT_BASE_URL = 'http://127.0.0.1:8741';

// =============================================================================
// Type Definitions (Strict TypeScript)
// =============================================================================

export type MemoryType = 'semantic' | 'episodic' | 'preference';
export type MemorySource = 'conversation' | 'tool' | 'user_edit' | 'verifier';
export type StoreLocation = 'qdrant' | 'postgres' | 'redis';

export interface MemoryListItem {
  id: string;
  memory_type: MemoryType;
  summary: string;
  source: MemorySource;
  confidence: number;
  created_at: string;
  is_deleted: boolean;
}

export interface MemoryListResponse {
  items: MemoryListItem[];
  total_count: number;
  limit: number;
  offset: number;
}

export interface MemoryDetailResponse {
  id: string;
  memory_type: MemoryType;
  content: string;
  summary: string;
  source: MemorySource;
  confidence: number;
  store_location: StoreLocation;
  created_at: string;
  updated_at: string;
  metadata: Record<string, string>;
}

export interface MemoryUpdateRequest {
  content?: string;
  confidence?: number;
}

export interface MemoryDeleteRequest {
  confirm: boolean;
}

export interface MemoryResetRequest {
  confirm_full_reset: boolean;
  preserve_user_profile: boolean;
}

export interface MemoryResetResponse {
  success: boolean;
  redis_cleared: boolean;
  qdrant_cleared: boolean;
  postgres_cleared: boolean;
  error: string | null;
}

export interface UserProfile {
  id: number;
  preferred_languages: string[];
  communication_style: string | null;
  privacy_level: string;
  memory_capture_enabled: boolean;
  created_at: string;
  updated_at: string;
}

export interface MemoryHealthResponse {
  redis: boolean;
  qdrant: boolean;
  postgres: boolean;
}

export interface MemoryListParams {
  type?: MemoryType;
  source?: MemorySource;
  limit?: number;
  offset?: number;
  include_deleted?: boolean;
}

// =============================================================================
// API Functions
// =============================================================================

/**
 * List memory entries with optional filters
 */
export async function listMemories(params: MemoryListParams = {}): Promise<MemoryListResponse> {
  const searchParams = new URLSearchParams();

  if (params.type) searchParams.set('type', params.type);
  if (params.source) searchParams.set('source', params.source);
  if (params.limit !== undefined) searchParams.set('limit', params.limit.toString());
  if (params.offset !== undefined) searchParams.set('offset', params.offset.toString());
  if (params.include_deleted !== undefined) searchParams.set('include_deleted', params.include_deleted.toString());

  const url = `${AGENT_BASE_URL}/api/v1/memory${searchParams.toString() ? '?' + searchParams.toString() : ''}`;

  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Failed to list memories: ${response.status}`);
  }

  return response.json();
}

/**
 * Get detailed memory entry by ID
 */
export async function getMemory(memoryId: string): Promise<MemoryDetailResponse> {
  const response = await fetch(`${AGENT_BASE_URL}/api/v1/memory/${memoryId}`);

  if (!response.ok) {
    if (response.status === 404) {
      throw new Error(`Memory ${memoryId} not found`);
    }
    throw new Error(`Failed to get memory: ${response.status}`);
  }

  return response.json();
}

/**
 * Update a memory entry
 */
export async function updateMemory(memoryId: string, update: MemoryUpdateRequest): Promise<boolean> {
  const response = await fetch(`${AGENT_BASE_URL}/api/v1/memory/${memoryId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(update),
  });

  if (!response.ok) {
    throw new Error(`Failed to update memory: ${response.status}`);
  }

  const result = await response.json();
  return result.success;
}

/**
 * Delete a memory entry (requires confirmation)
 */
export async function deleteMemory(memoryId: string): Promise<boolean> {
  const request: MemoryDeleteRequest = { confirm: true };

  const response = await fetch(`${AGENT_BASE_URL}/api/v1/memory/${memoryId}`, {
    method: 'DELETE',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    throw new Error(`Failed to delete memory: ${response.status}`);
  }

  const result = await response.json();
  return result.success;
}

/**
 * Perform full memory reset (CAUTION: destructive operation)
 */
export async function resetMemory(preserveUserProfile: boolean = true): Promise<MemoryResetResponse> {
  const request: MemoryResetRequest = {
    confirm_full_reset: true,
    preserve_user_profile: preserveUserProfile,
  };

  const response = await fetch(`${AGENT_BASE_URL}/api/v1/memory/reset`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    throw new Error(`Failed to reset memory: ${response.status}`);
  }

  return response.json();
}

/**
 * Get user profile
 */
export async function getUserProfile(): Promise<UserProfile> {
  const response = await fetch(`${AGENT_BASE_URL}/api/v1/memory/profile`);

  if (!response.ok) {
    throw new Error(`Failed to get user profile: ${response.status}`);
  }

  return response.json();
}

/**
 * Update user profile
 */
export async function updateUserProfile(updates: {
  preferred_languages?: string[];
  communication_style?: string;
  privacy_level?: string;
  memory_capture_enabled?: boolean;
}): Promise<UserProfile> {
  const searchParams = new URLSearchParams();

  if (updates.preferred_languages) {
    updates.preferred_languages.forEach(lang => searchParams.append('preferred_languages', lang));
  }
  if (updates.communication_style) searchParams.set('communication_style', updates.communication_style);
  if (updates.privacy_level) searchParams.set('privacy_level', updates.privacy_level);
  if (updates.memory_capture_enabled !== undefined) {
    searchParams.set('memory_capture_enabled', updates.memory_capture_enabled.toString());
  }

  const response = await fetch(`${AGENT_BASE_URL}/api/v1/memory/profile?${searchParams.toString()}`, {
    method: 'PUT',
  });

  if (!response.ok) {
    throw new Error(`Failed to update user profile: ${response.status}`);
  }

  return response.json();
}

/**
 * Check memory services health
 */
export async function checkMemoryHealth(): Promise<MemoryHealthResponse> {
  const response = await fetch(`${AGENT_BASE_URL}/api/v1/memory/health`);

  if (!response.ok) {
    throw new Error(`Failed to check memory health: ${response.status}`);
  }

  return response.json();
}
