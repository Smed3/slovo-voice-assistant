import { useState, useCallback } from 'react';
import { useAppStore } from '../store/appStore';
import { sendChatMessage } from '../lib/agent';
import './VoiceInput.css';

export function VoiceInput() {
  const { isListening, setListening, addMessage, setAgentStatus } = useAppStore();
  const [inputText, setInputText] = useState('');

  const handleSubmit = useCallback(async (text: string) => {
    if (!text.trim()) return;

    // Add user message
    addMessage({ role: 'user', content: text });
    setInputText('');
    setAgentStatus('processing');

    try {
      // Add placeholder for assistant response
      const responseId = crypto.randomUUID();
      addMessage({ role: 'assistant', content: '', isProcessing: true });

      const response = await sendChatMessage({ message: text });
      
      // Update with actual response (in real implementation, update the placeholder)
      addMessage({ role: 'assistant', content: response.response });
      setAgentStatus('connected');
    } catch (error) {
      console.error('Failed to send message:', error);
      addMessage({ 
        role: 'assistant', 
        content: 'Sorry, I encountered an error. Please make sure the agent is running.' 
      });
      setAgentStatus('disconnected');
    }
  }, [addMessage, setAgentStatus]);

  const toggleListening = useCallback(() => {
    setListening(!isListening);
    // TODO: Implement actual voice recording
    if (!isListening) {
      console.log('Started listening...');
    } else {
      console.log('Stopped listening');
    }
  }, [isListening, setListening]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(inputText);
    }
  };

  return (
    <div className="voice-input">
      <button
        className={`voice-button ${isListening ? 'listening' : ''}`}
        onClick={toggleListening}
        title={isListening ? 'Stop listening' : 'Start listening'}
      >
        <svg
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 24 24"
          fill="currentColor"
          width="24"
          height="24"
        >
          <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3z" />
          <path d="M17 11c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z" />
        </svg>
      </button>

      <input
        type="text"
        className="text-input"
        placeholder="Type a message or press the mic button..."
        value={inputText}
        onChange={(e) => setInputText(e.target.value)}
        onKeyDown={handleKeyDown}
      />

      <button
        className="send-button"
        onClick={() => handleSubmit(inputText)}
        disabled={!inputText.trim()}
        title="Send message"
      >
        <svg
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 24 24"
          fill="currentColor"
          width="20"
          height="20"
        >
          <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z" />
        </svg>
      </button>
    </div>
  );
}
