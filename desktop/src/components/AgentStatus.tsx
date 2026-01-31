import type { AgentStatus } from '../store/appStore';
import './AgentStatus.css';

interface AgentStatusProps {
  status: AgentStatus;
}

const STATUS_CONFIG: Record<AgentStatus, { label: string; className: string }> = {
  disconnected: { label: 'Disconnected', className: 'status-disconnected' },
  connecting: { label: 'Connecting...', className: 'status-connecting' },
  connected: { label: 'Connected', className: 'status-connected' },
  processing: { label: 'Processing...', className: 'status-processing' },
};

export function AgentStatus({ status }: AgentStatusProps) {
  const config = STATUS_CONFIG[status];

  return (
    <div className={`agent-status ${config.className}`}>
      <span className="status-indicator" />
      <span className="status-label">{config.label}</span>
    </div>
  );
}
