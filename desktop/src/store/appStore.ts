import { create } from 'zustand';

export type AgentStatus = 'disconnected' | 'connecting' | 'connected' | 'processing';

export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  isProcessing?: boolean;
}

interface AppState {
  // Initialization
  isInitialized: boolean;
  setInitialized: (value: boolean) => void;

  // Agent connection
  agentStatus: AgentStatus;
  setAgentStatus: (status: AgentStatus) => void;

  // Voice state
  isListening: boolean;
  setListening: (value: boolean) => void;
  isSpeaking: boolean;
  setSpeaking: (value: boolean) => void;

  // Conversation
  messages: Message[];
  addMessage: (message: Omit<Message, 'id' | 'timestamp'>) => void;
  updateMessage: (id: string, updates: Partial<Message>) => void;
  clearMessages: () => void;

  // UI state
  isWindowVisible: boolean;
  setWindowVisible: (value: boolean) => void;
}

export const useAppStore = create<AppState>((set) => ({
  // Initialization
  isInitialized: false,
  setInitialized: (value) => set({ isInitialized: value }),

  // Agent connection
  agentStatus: 'disconnected',
  setAgentStatus: (status) => set({ agentStatus: status }),

  // Voice state
  isListening: false,
  setListening: (value) => set({ isListening: value }),
  isSpeaking: false,
  setSpeaking: (value) => set({ isSpeaking: value }),

  // Conversation
  messages: [],
  addMessage: (message) =>
    set((state) => ({
      messages: [
        ...state.messages,
        {
          ...message,
          id: crypto.randomUUID(),
          timestamp: new Date(),
        },
      ],
    })),
  updateMessage: (id, updates) =>
    set((state) => ({
      messages: state.messages.map((msg) =>
        msg.id === id ? { ...msg, ...updates } : msg
      ),
    })),
  clearMessages: () => set({ messages: [] }),

  // UI state
  isWindowVisible: true,
  setWindowVisible: (value) => set({ isWindowVisible: value }),
}));
