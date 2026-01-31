import { useEffect, useRef } from 'react';
import { useAppStore } from '../store/appStore';
import './ConversationView.css';

export function ConversationView() {
  const { messages } = useAppStore();
  const bottomRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  if (messages.length === 0) {
    return (
      <div className="conversation-empty">
        <div className="empty-icon">
          <svg
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 24 24"
            fill="currentColor"
            width="64"
            height="64"
          >
            <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z" />
          </svg>
        </div>
        <h2>Welcome to Slovo</h2>
        <p>Your agentic voice assistant is ready.</p>
        <p className="hint">Press the microphone button or type to start a conversation.</p>
      </div>
    );
  }

  return (
    <div className="conversation-view">
      {messages.map((message) => (
        <div
          key={message.id}
          className={`message ${message.role === 'user' ? 'message-user' : 'message-assistant'}`}
        >
          <div className="message-content">
            {message.isProcessing ? (
              <div className="typing-indicator">
                <span />
                <span />
                <span />
              </div>
            ) : (
              message.content
            )}
          </div>
          <div className="message-time">
            {message.timestamp.toLocaleTimeString([], { 
              hour: '2-digit', 
              minute: '2-digit' 
            })}
          </div>
        </div>
      ))}
      <div ref={bottomRef} />
    </div>
  );
}
