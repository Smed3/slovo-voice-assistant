/**
 * Memory Inspector Component for Slovo Voice Assistant
 *
 * Phase 3: Memory Inspector UI (Required)
 *
 * User must be able to:
 * - Browse memory entries (by type)
 * - View content + metadata
 * - Edit entries
 * - Delete individual entries
 * - Full reset (with confirmation)
 */

import { useCallback, useEffect, useState } from 'react';
import {
  checkMemoryHealth,
  deleteMemory,
  getMemory,
  getUserProfile,
  listMemories,
  resetMemory,
  updateMemory,
  updateUserProfile,
  type MemoryDetailResponse,
  type MemoryHealthResponse,
  type MemoryListItem,
  type MemoryType,
  type UserProfile,
} from '../lib/memory';
import './MemoryInspector.css';

// =============================================================================
// Types
// =============================================================================

type ViewMode = 'list' | 'detail' | 'edit' | 'profile' | 'reset';

interface MemoryInspectorProps {
  onClose?: () => void;
}

// =============================================================================
// Component
// =============================================================================

export function MemoryInspector({ onClose }: MemoryInspectorProps) {
  // State
  const [viewMode, setViewMode] = useState<ViewMode>('list');
  const [typeFilter, setTypeFilter] = useState<MemoryType | 'all'>('all');
  const [memories, setMemories] = useState<MemoryListItem[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [currentPage, setCurrentPage] = useState(0);
  const [selectedMemory, setSelectedMemory] = useState<MemoryDetailResponse | null>(null);
  const [editContent, setEditContent] = useState('');
  const [editConfidence, setEditConfidence] = useState(0);
  const [userProfile, setUserProfile] = useState<UserProfile | null>(null);
  const [health, setHealth] = useState<MemoryHealthResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [confirmReset, setConfirmReset] = useState(false);
  const [preserveProfile, setPreserveProfile] = useState(true);

  const PAGE_SIZE = 20;

  // Load memories
  const loadMemories = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const response = await listMemories({
        type: typeFilter === 'all' ? undefined : typeFilter,
        limit: PAGE_SIZE,
        offset: currentPage * PAGE_SIZE,
      });
      setMemories(response.items);
      setTotalCount(response.total_count);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load memories');
    } finally {
      setLoading(false);
    }
  }, [typeFilter, currentPage]);

  // Load memory detail
  const loadMemoryDetail = useCallback(async (id: string) => {
    setLoading(true);
    setError(null);

    try {
      const detail = await getMemory(id);
      setSelectedMemory(detail);
      setEditContent(detail.content);
      setEditConfidence(detail.confidence);
      setViewMode('detail');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load memory');
    } finally {
      setLoading(false);
    }
  }, []);

  // Load user profile
  const loadUserProfile = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const profile = await getUserProfile();
      setUserProfile(profile);
      setViewMode('profile');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load profile');
    } finally {
      setLoading(false);
    }
  }, []);

  // Load health status
  const loadHealth = useCallback(async () => {
    try {
      const healthStatus = await checkMemoryHealth();
      setHealth(healthStatus);
    } catch (err) {
      console.error('Failed to check health:', err);
    }
  }, []);

  // Initial load
  useEffect(() => {
    loadMemories();
    loadHealth();
  }, [loadMemories, loadHealth]);

  // Handle save edit
  const handleSaveEdit = async () => {
    if (!selectedMemory) return;

    setLoading(true);
    setError(null);

    try {
      await updateMemory(selectedMemory.id, {
        content: editContent !== selectedMemory.content ? editContent : undefined,
        confidence: editConfidence !== selectedMemory.confidence ? editConfidence : undefined,
      });
      await loadMemoryDetail(selectedMemory.id);
      setViewMode('detail');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update memory');
    } finally {
      setLoading(false);
    }
  };

  // Handle delete
  const handleDelete = async () => {
    if (!selectedMemory) return;

    if (!confirm(`Are you sure you want to delete this memory entry?\n\n"${selectedMemory.summary}"`)) {
      return;
    }

    setLoading(true);
    setError(null);

    try {
      await deleteMemory(selectedMemory.id);
      setSelectedMemory(null);
      setViewMode('list');
      loadMemories();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete memory');
    } finally {
      setLoading(false);
    }
  };

  // Handle full reset
  const handleFullReset = async () => {
    if (!confirmReset) {
      setError('Please confirm full reset by checking the confirmation box');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const result = await resetMemory(preserveProfile);

      if (result.success) {
        setConfirmReset(false);
        setViewMode('list');
        loadMemories();
        loadHealth();
        alert('Memory reset completed successfully');
      } else {
        setError(result.error || 'Reset failed');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to reset memory');
    } finally {
      setLoading(false);
    }
  };

  // Handle profile update
  const handleProfileUpdate = async (updates: Partial<UserProfile>) => {
    setLoading(true);
    setError(null);

    try {
      const updated = await updateUserProfile({
        preferred_languages: updates.preferred_languages,
        communication_style: updates.communication_style ?? undefined,
        privacy_level: updates.privacy_level,
        memory_capture_enabled: updates.memory_capture_enabled,
      });
      setUserProfile(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update profile');
    } finally {
      setLoading(false);
    }
  };

  // Format date
  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleString();
  };

  // Get type badge color
  const getTypeBadgeClass = (type: MemoryType) => {
    switch (type) {
      case 'semantic':
        return 'badge-semantic';
      case 'episodic':
        return 'badge-episodic';
      case 'preference':
        return 'badge-preference';
      default:
        return '';
    }
  };

  // =============================================================================
  // Render Functions
  // =============================================================================

  const renderHeader = () => (
    <div className="memory-inspector-header">
      <h2>Memory Inspector</h2>
      <div className="header-actions">
        {health && (
          <div className="health-indicators">
            <span className={`health-dot ${health.redis ? 'healthy' : 'unhealthy'}`} title="Redis" />
            <span className={`health-dot ${health.qdrant ? 'healthy' : 'unhealthy'}`} title="Qdrant" />
            <span className={`health-dot ${health.postgres ? 'healthy' : 'unhealthy'}`} title="PostgreSQL" />
          </div>
        )}
        <button className="btn-icon" onClick={loadUserProfile} title="User Profile">
          👤
        </button>
        <button className="btn-icon danger" onClick={() => setViewMode('reset')} title="Reset Memory">
          ⚠️
        </button>
        {onClose && (
          <button className="btn-icon" onClick={onClose} title="Close">
            ✕
          </button>
        )}
      </div>
    </div>
  );

  const renderListView = () => (
    <div className="memory-list-view">
      <div className="filter-bar">
        <select value={typeFilter} onChange={(e) => { setTypeFilter(e.target.value as MemoryType | 'all'); setCurrentPage(0); }}>
          <option value="all">All Types</option>
          <option value="semantic">Semantic</option>
          <option value="episodic">Episodic</option>
          <option value="preference">Preference</option>
        </select>
        <span className="result-count">{totalCount} entries</span>
      </div>

      {loading && <div className="loading">Loading...</div>}
      {error && <div className="error">{error}</div>}

      <div className="memory-list">
        {memories.map((memory) => (
          <div
            key={memory.id}
            className={`memory-item ${memory.is_deleted ? 'deleted' : ''}`}
            onClick={() => loadMemoryDetail(memory.id)}
          >
            <div className="memory-item-header">
              <span className={`badge ${getTypeBadgeClass(memory.memory_type)}`}>
                {memory.memory_type}
              </span>
              <span className="confidence">{(memory.confidence * 100).toFixed(0)}%</span>
            </div>
            <div className="memory-item-summary">{memory.summary}</div>
            <div className="memory-item-meta">
              <span className="source">{memory.source}</span>
              <span className="date">{formatDate(memory.created_at)}</span>
            </div>
          </div>
        ))}
      </div>

      {totalCount > PAGE_SIZE && (
        <div className="pagination">
          <button
            disabled={currentPage === 0}
            onClick={() => setCurrentPage((p) => p - 1)}
          >
            Previous
          </button>
          <span>
            Page {currentPage + 1} of {Math.ceil(totalCount / PAGE_SIZE)}
          </span>
          <button
            disabled={(currentPage + 1) * PAGE_SIZE >= totalCount}
            onClick={() => setCurrentPage((p) => p + 1)}
          >
            Next
          </button>
        </div>
      )}
    </div>
  );

  const renderDetailView = () => {
    if (!selectedMemory) return null;

    return (
      <div className="memory-detail-view">
        <div className="detail-header">
          <button className="btn-back" onClick={() => { setViewMode('list'); setSelectedMemory(null); }}>
            ← Back
          </button>
          <div className="detail-actions">
            <button className="btn-edit" onClick={() => setViewMode('edit')}>
              Edit
            </button>
            <button className="btn-delete" onClick={handleDelete}>
              Delete
            </button>
          </div>
        </div>

        <div className="detail-content">
          <div className="detail-row">
            <label>Type:</label>
            <span className={`badge ${getTypeBadgeClass(selectedMemory.memory_type)}`}>
              {selectedMemory.memory_type}
            </span>
          </div>

          <div className="detail-row">
            <label>Source:</label>
            <span>{selectedMemory.source}</span>
          </div>

          <div className="detail-row">
            <label>Confidence:</label>
            <span>{(selectedMemory.confidence * 100).toFixed(1)}%</span>
          </div>

          <div className="detail-row">
            <label>Store:</label>
            <span>{selectedMemory.store_location}</span>
          </div>

          <div className="detail-row">
            <label>Created:</label>
            <span>{formatDate(selectedMemory.created_at)}</span>
          </div>

          <div className="detail-row">
            <label>Updated:</label>
            <span>{formatDate(selectedMemory.updated_at)}</span>
          </div>

          <div className="detail-row full-width">
            <label>Content:</label>
            <div className="content-box">{selectedMemory.content}</div>
          </div>

          {Object.keys(selectedMemory.metadata).length > 0 && (
            <div className="detail-row full-width">
              <label>Metadata:</label>
              <div className="metadata-box">
                {Object.entries(selectedMemory.metadata).map(([key, value]) => (
                  <div key={key} className="metadata-item">
                    <span className="metadata-key">{key}:</span>
                    <span className="metadata-value">{value}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    );
  };

  const renderEditView = () => {
    if (!selectedMemory) return null;

    return (
      <div className="memory-edit-view">
        <div className="edit-header">
          <button className="btn-back" onClick={() => setViewMode('detail')}>
            ← Cancel
          </button>
          <h3>Edit Memory</h3>
        </div>

        {error && <div className="error">{error}</div>}

        <div className="edit-form">
          <div className="form-group">
            <label>Content:</label>
            <textarea
              value={editContent}
              onChange={(e) => setEditContent(e.target.value)}
              rows={6}
            />
          </div>

          <div className="form-group">
            <label>Confidence ({(editConfidence * 100).toFixed(0)}%):</label>
            <input
              type="range"
              min="0"
              max="1"
              step="0.05"
              value={editConfidence}
              onChange={(e) => setEditConfidence(parseFloat(e.target.value))}
            />
          </div>

          <div className="form-actions">
            <button className="btn-secondary" onClick={() => setViewMode('detail')}>
              Cancel
            </button>
            <button className="btn-primary" onClick={handleSaveEdit} disabled={loading}>
              {loading ? 'Saving...' : 'Save Changes'}
            </button>
          </div>
        </div>
      </div>
    );
  };

  const renderProfileView = () => {
    if (!userProfile) return null;

    return (
      <div className="profile-view">
        <div className="profile-header">
          <button className="btn-back" onClick={() => setViewMode('list')}>
            ← Back
          </button>
          <h3>User Profile</h3>
        </div>

        {error && <div className="error">{error}</div>}

        <div className="profile-form">
          <div className="form-group">
            <label>Preferred Languages:</label>
            <input
              type="text"
              value={userProfile.preferred_languages.join(', ')}
              onChange={(e) => {
                const langs = e.target.value.split(',').map((l) => l.trim()).filter(Boolean);
                setUserProfile({ ...userProfile, preferred_languages: langs });
              }}
              placeholder="en, es, fr"
            />
          </div>

          <div className="form-group">
            <label>Communication Style:</label>
            <select
              value={userProfile.communication_style || 'friendly'}
              onChange={(e) => setUserProfile({ ...userProfile, communication_style: e.target.value })}
            >
              <option value="friendly">Friendly</option>
              <option value="professional">Professional</option>
              <option value="concise">Concise</option>
              <option value="detailed">Detailed</option>
            </select>
          </div>

          <div className="form-group">
            <label>Privacy Level:</label>
            <select
              value={userProfile.privacy_level}
              onChange={(e) => setUserProfile({ ...userProfile, privacy_level: e.target.value })}
            >
              <option value="minimal">Minimal</option>
              <option value="standard">Standard</option>
              <option value="maximum">Maximum</option>
            </select>
          </div>

          <div className="form-group checkbox">
            <label>
              <input
                type="checkbox"
                checked={userProfile.memory_capture_enabled}
                onChange={(e) => setUserProfile({ ...userProfile, memory_capture_enabled: e.target.checked })}
              />
              Enable Memory Capture
            </label>
            <p className="help-text">
              When disabled, the assistant will not save new memories from conversations.
            </p>
          </div>

          <div className="form-actions">
            <button className="btn-secondary" onClick={() => setViewMode('list')}>
              Cancel
            </button>
            <button
              className="btn-primary"
              onClick={() => handleProfileUpdate(userProfile)}
              disabled={loading}
            >
              {loading ? 'Saving...' : 'Save Profile'}
            </button>
          </div>
        </div>
      </div>
    );
  };

  const renderResetView = () => (
    <div className="reset-view">
      <div className="reset-header">
        <button className="btn-back" onClick={() => { setViewMode('list'); setConfirmReset(false); }}>
          ← Cancel
        </button>
        <h3>⚠️ Full Memory Reset</h3>
      </div>

      <div className="reset-warning">
        <p>
          <strong>WARNING:</strong> This will permanently delete ALL memory data:
        </p>
        <ul>
          <li>All semantic memories (learned context)</li>
          <li>All episodic logs (action history)</li>
          <li>All preferences (except user profile if preserved)</li>
          <li>All session data</li>
        </ul>
        <p>This action cannot be undone!</p>
      </div>

      {error && <div className="error">{error}</div>}

      <div className="reset-form">
        <div className="form-group checkbox">
          <label>
            <input
              type="checkbox"
              checked={preserveProfile}
              onChange={(e) => setPreserveProfile(e.target.checked)}
            />
            Preserve basic user profile settings
          </label>
        </div>

        <div className="form-group checkbox">
          <label>
            <input
              type="checkbox"
              checked={confirmReset}
              onChange={(e) => setConfirmReset(e.target.checked)}
            />
            I understand this will delete all my memory data
          </label>
        </div>

        <div className="form-actions">
          <button className="btn-secondary" onClick={() => { setViewMode('list'); setConfirmReset(false); }}>
            Cancel
          </button>
          <button
            className="btn-danger"
            onClick={handleFullReset}
            disabled={loading || !confirmReset}
          >
            {loading ? 'Resetting...' : 'Reset All Memory'}
          </button>
        </div>
      </div>
    </div>
  );

  // =============================================================================
  // Main Render
  // =============================================================================

  return (
    <div className="memory-inspector">
      {renderHeader()}

      <div className="memory-inspector-content">
        {viewMode === 'list' && renderListView()}
        {viewMode === 'detail' && renderDetailView()}
        {viewMode === 'edit' && renderEditView()}
        {viewMode === 'profile' && renderProfileView()}
        {viewMode === 'reset' && renderResetView()}
      </div>
    </div>
  );
}

export default MemoryInspector;
