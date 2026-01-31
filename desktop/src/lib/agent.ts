import { invoke } from '@tauri-apps/api/core';

const AGENT_BASE_URL = 'http://127.0.0.1:8741';

export interface AgentHealthResponse {
  status: 'healthy' | 'degraded' | 'unhealthy';
  version: string;
  uptime: number;
}

export interface ChatRequest {
  message: string;
  conversation_id?: string;
}

export interface ChatResponse {
  id: string;
  response: string;
  conversation_id: string;
  reasoning?: string;
}

/**
 * Check if the agent runtime is healthy
 */
export async function checkAgentHealth(): Promise<AgentHealthResponse> {
  const response = await fetch(`${AGENT_BASE_URL}/health`);
  if (!response.ok) {
    throw new Error(`Agent health check failed: ${response.status}`);
  }
  return response.json();
}

/**
 * Send a chat message to the agent
 */
export async function sendChatMessage(request: ChatRequest): Promise<ChatResponse> {
  const response = await fetch(`${AGENT_BASE_URL}/api/v1/chat`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    throw new Error(`Chat request failed: ${response.status}`);
  }

  return response.json();
}

/**
 * Stream a chat response from the agent
 */
export async function* streamChatMessage(
  request: ChatRequest
): AsyncGenerator<string, void, unknown> {
  const response = await fetch(`${AGENT_BASE_URL}/api/v1/chat/stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    throw new Error(`Chat stream request failed: ${response.status}`);
  }

  const reader = response.body?.getReader();
  if (!reader) {
    throw new Error('No response body');
  }

  const decoder = new TextDecoder();
  
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    
    const chunk = decoder.decode(value, { stream: true });
    yield chunk;
  }
}

/**
 * Request the agent to process voice input through Tauri
 */
export async function processVoiceInput(audioData: ArrayBuffer): Promise<string> {
  return invoke<string>('process_voice_input', { audioData: Array.from(new Uint8Array(audioData)) });
}
