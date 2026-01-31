import { useEffect } from 'react';
import { useAppStore } from './store/appStore';
import { initializeTray } from './lib/tray';
import { initializeAutostart } from './lib/autostart';
import { AgentStatus } from './components/AgentStatus';
import { VoiceInput } from './components/VoiceInput';
import { ConversationView } from './components/ConversationView';
import './styles/App.css';

function App() {
  const { isInitialized, setInitialized, agentStatus } = useAppStore();

  useEffect(() => {
    const initialize = async () => {
      try {
        // Initialize system tray
        await initializeTray();
        
        // Initialize autostart
        await initializeAutostart();
        
        setInitialized(true);
        console.log('Slovo Voice Assistant initialized');
      } catch (error) {
        console.error('Failed to initialize:', error);
      }
    };

    initialize();
  }, [setInitialized]);

  if (!isInitialized) {
    return (
      <div className="app loading">
        <div className="loading-spinner" />
        <p>Initializing Slovo...</p>
      </div>
    );
  }

  return (
    <div className="app">
      <header className="app-header">
        <h1>Slovo</h1>
        <AgentStatus status={agentStatus} />
      </header>
      
      <main className="app-main">
        <ConversationView />
      </main>
      
      <footer className="app-footer">
        <VoiceInput />
      </footer>
    </div>
  );
}

export default App;
