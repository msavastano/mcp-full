import { useState, useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import { sseService } from './services/sse';
import { callGemini } from './services/gemini';
import './App.css';

interface Tool {
  name: string;
  description: string;
  inputSchema: any;
}

interface Resource {
  uri: string;
  name: string;
  description: string;
}

interface Prompt {
  name: string;
  description: string;
  arguments: any[];
}

interface Message {
  type: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: Date;
}

function App() {
  const [connectionStatus, setConnectionStatus] = useState<'disconnected' | 'connecting' | 'connected'>('disconnected');
  const [tools, setTools] = useState<Tool[]>([]);
  const [resources, setResources] = useState<Resource[]>([]);
  const [prompts, setPrompts] = useState<Prompt[]>([]);
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [showDebug, setShowDebug] = useState(false);
  const [debugMessages, setDebugMessages] = useState<any[]>([]);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    // Set up SSE service event listeners
    const handleConnecting = () => {
      setConnectionStatus('connecting');
      addSystemMessage('Connecting to SSE MCP server...');
    };

    const handleConnected = () => {
      setConnectionStatus('connected');
      addSystemMessage('✅ Connected to SSE MCP server on port 8766');
      loadMCPData();
    };

    const handleDisconnected = () => {
      setConnectionStatus('disconnected');
      addSystemMessage('❌ Disconnected from SSE MCP server');
    };

    const handleServerInfo = (serverInfo: any) => {
      addDebugMessage('Server Info', serverInfo);
    };

    const handleNotification = (notification: any) => {
      addDebugMessage('Notification', notification);
    };

    sseService.on('connecting', handleConnecting);
    sseService.on('connected', handleConnected);
    sseService.on('disconnected', handleDisconnected);
    sseService.on('serverInfo', handleServerInfo);
    sseService.on('notification', handleNotification);

    // Auto-connect on mount
    sseService.connect();

    return () => {
      sseService.off('connecting', handleConnecting);
      sseService.off('connected', handleConnected);
      sseService.off('disconnected', handleDisconnected);
      sseService.off('serverInfo', handleServerInfo);
      sseService.off('notification', handleNotification);
    };
  }, []);

  const addSystemMessage = (content: string) => {
    setMessages(prev => [...prev, {
      type: 'system',
      content,
      timestamp: new Date()
    }]);
  };

  const addDebugMessage = (type: string, data: any) => {
    setDebugMessages(prev => [...prev, {
      type,
      data,
      timestamp: new Date()
    }]);
  };

  const loadMCPData = async () => {
    try {
      // Load tools, resources, and prompts
      const [toolsData, resourcesData, promptsData] = await Promise.all([
        sseService.listTools(),
        sseService.listResources(),
        sseService.listPrompts()
      ]);

      setTools(toolsData);
      setResources(resourcesData);
      setPrompts(promptsData);

      addSystemMessage(`📋 Loaded ${toolsData.length} tools, ${resourcesData.length} resources, ${promptsData.length} prompts`);
      
      addDebugMessage('Tools loaded', toolsData);
      addDebugMessage('Resources loaded', resourcesData);
      addDebugMessage('Prompts loaded', promptsData);

    } catch (error) {
      console.error('Failed to load MCP data:', error);
      addSystemMessage(`❌ Failed to load MCP data: ${error}`);
    }
  };

  const handleConnect = () => {
    sseService.connect();
  };

  const handleDisconnect = () => {
    sseService.disconnect();
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputValue.trim() || isLoading || connectionStatus !== 'connected') return;

    const userMessage = inputValue.trim();
    setInputValue('');
    setIsLoading(true);

    // Add user message to chat
    setMessages(prev => [...prev, {
      type: 'user',
      content: userMessage,
      timestamp: new Date()
    }]);

    try {
      // Convert tools to Gemini format
      const geminiTools = tools.map(tool => ({
        name: tool.name,
        description: tool.description,
        parameters: tool.inputSchema
      }));

      // Call Gemini with MCP tools
      const response = await callGemini(userMessage, geminiTools, resources);
      addDebugMessage('Gemini Response', response);

      // Extract response text
      const candidate = response.candidates?.[0];
      const responseText = candidate?.content?.parts?.[0]?.text || 'No response generated.';

      // Add assistant response to chat
      setMessages(prev => [...prev, {
        type: 'assistant',
        content: responseText,
        timestamp: new Date()
      }]);

    } catch (error) {
      console.error('Error processing message:', error);
      setMessages(prev => [...prev, {
        type: 'system',
        content: `❌ Error: ${error}`,
        timestamp: new Date()
      }]);
    } finally {
      setIsLoading(false);
    }
  };

  const handlePromptClick = async (prompt: Prompt) => {
    if (connectionStatus !== 'connected') return;

    try {
      // Get the prompt template
      const promptData = await sseService.getPrompt(prompt.name, {});
      addDebugMessage('Prompt Data', promptData);

      // Extract the prompt text
      const promptText = promptData.messages?.[0]?.content?.text || prompt.description;

      // Fill the input field with the prompt text so user can edit it
      setInputValue(promptText);
      
      // Focus the input field so user can immediately start editing
      setTimeout(() => {
        inputRef.current?.focus();
        inputRef.current?.setSelectionRange(promptText.length, promptText.length);
      }, 100);

    } catch (error) {
      console.error('Error loading prompt:', error);
      // Fallback to just the prompt description
      setInputValue(prompt.description);
      
      // Focus the input field
      setTimeout(() => {
        inputRef.current?.focus();
        inputRef.current?.setSelectionRange(prompt.description.length, prompt.description.length);
      }, 100);
    }
  };

  const getConnectionStatusClass = () => {
    switch (connectionStatus) {
      case 'connected': return 'status-connected';
      case 'connecting': return 'status-connecting';
      case 'disconnected': return 'status-disconnected';
      default: return 'status-disconnected';
    }
  };

  const getConnectionStatusText = () => {
    switch (connectionStatus) {
      case 'connected': return '🟢 Connected (SSE)';
      case 'connecting': return '🟡 Connecting...';
      case 'disconnected': return '🔴 Disconnected';
      default: return '🔴 Disconnected';
    }
  };

  return (
    <div className="App">
      <header className="App-header">
        <h1>🌐 MCP SSE Demo</h1>
        <div className={`connection-status ${getConnectionStatusClass()}`}>
          {getConnectionStatusText()}
          <div className="connection-actions">
            {connectionStatus === 'disconnected' && (
              <button onClick={handleConnect} className="connect-btn">
                Connect
              </button>
            )}
            {connectionStatus === 'connected' && (
              <button onClick={handleDisconnect} className="disconnect-btn">
                Disconnect
              </button>
            )}
          </div>
        </div>
        <div className="server-info">
          <span>🔌 SSE Server: localhost:8766</span>
          <span>📊 Tools: {tools.length}</span>
          <span>📁 Resources: {resources.length}</span>
          <span>💬 Prompts: {prompts.length}</span>
        </div>
      </header>

      <main className="App-main">
        {prompts.length > 0 && (
          <div className="prompts-section">
            <h3>📝 Available Prompts</h3>
            <div className="prompts-grid">
              {prompts.map(prompt => (
                <button
                  key={prompt.name}
                  onClick={() => handlePromptClick(prompt)}
                  className="prompt-button"
                  disabled={connectionStatus !== 'connected' || isLoading}
                  title={prompt.description}
                >
                  {prompt.name}
                </button>
              ))}
            </div>
          </div>
        )}

        <div className="chat-container">
          <div className="messages">
            {messages.map((message, index) => (
              <div key={index} className={`message message-${message.type}`}>
                <div className="message-content">
                  <div className="message-text">
                    {message.type === 'assistant' ? (
                      <ReactMarkdown>{message.content}</ReactMarkdown>
                    ) : (
                      message.content
                    )}
                  </div>
                  <div className="message-time">
                    {message.timestamp.toLocaleTimeString()}
                  </div>
                </div>
              </div>
            ))}
            {isLoading && (
              <div className="message message-assistant">
                <div className="message-content">
                  <div className="message-text">🤖 Thinking...</div>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          <form onSubmit={handleSubmit} className="input-form">
            <textarea
              ref={inputRef}
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              placeholder="Ask about weather, animals, or anything else..."
              disabled={connectionStatus !== 'connected' || isLoading}
              className="message-input"
              rows={4}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  handleSubmit(e);
                }
              }}
            />
            <button 
              type="submit" 
              disabled={connectionStatus !== 'connected' || isLoading || !inputValue.trim()}
              className="send-button"
            >
              Send
            </button>
          </form>
        </div>

        <div className="debug-section">
          <button 
            onClick={() => setShowDebug(!showDebug)}
            className="debug-toggle"
          >
            {showDebug ? '🔼' : '🔽'} Debug Info
          </button>
          
          {showDebug && (
            <div className="debug-content">
              <h4>🐛 Debug Messages</h4>
              <div className="debug-messages">
                {debugMessages.map((msg, index) => (
                  <div key={index} className="debug-message">
                    <div className="debug-header">
                      <span className="debug-type">{msg.type}</span>
                      <span className="debug-time">
                        {msg.timestamp.toLocaleTimeString()}
                      </span>
                    </div>
                    <pre className="debug-data">
                      {JSON.stringify(msg.data, null, 2)}
                    </pre>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}

export default App;