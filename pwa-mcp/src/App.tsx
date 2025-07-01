import { useState, useEffect, useRef } from 'react';
import { webSocketService } from './services/websocket';
import { callGemini } from './services/gemini';
import './App.css';

function App() {
  const [messages, setMessages] = useState<any[]>([]);
  const [input, setInput] = useState('');
  const [tools, setTools] = useState<any[]>([]);
  const [geminiResponses, setGeminiResponses] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState<'connecting' | 'connected' | 'disconnected'>('connecting');
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const connectWithRetry = () => {
      try {
        webSocketService.connect('ws://localhost:8765', 
          () => setConnectionStatus('connected'),
          () => setConnectionStatus('disconnected')
        );
      } catch (error) {
        console.error('Failed to connect to MCP server:', error);
        setConnectionStatus('disconnected');
        // Retry connection after 3 seconds
        setTimeout(connectWithRetry, 3000);
      }
    };

    connectWithRetry();

    const messageListener = (data: any) => {
      console.log('App.tsx: Message received by listener:', data);
      setMessages(prevMessages => [...prevMessages, data]);
      if (data.result && data.result.tools && data.result.tools.function_declarations) {
        const cleanedTools = data.result.tools.function_declarations.map((tool: any) => ({
          name: tool.name,
          description: tool.description,
          parameters: tool.parameters,
        }));
        setTools(cleanedTools);
        setConnectionStatus('connected');
      } else if (data.result && data.result.tools) {
        // Fallback for cases where tools might be directly an array of function declarations
        const cleanedTools = data.result.tools.map((tool: any) => ({
          name: tool.name,
          description: tool.description,
          parameters: tool.parameters,
        }));
        setTools(cleanedTools);
        setConnectionStatus('connected');
      }
    };

    webSocketService.addListener(messageListener);

    return () => {
      webSocketService.removeListener(messageListener);
    };
  }, []);

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [geminiResponses]);

  const formatWeatherResponse = (text: string): string => {
    // Simple formatting to make weather data more readable
    return text
      .replace(/Temperature: (\d+)°([CF])/g, '🌡️ **$1°$2**')
      .replace(/Wind Speed: ([^,\n]+)/g, '💨 **$1**')
      .replace(/Short Forecast: ([^,\n]+)/g, '☁️ **$1**')
      .replace(/(\d{1,2}:\d{2}\s*(AM|PM))/g, '🕐 **$1**')
      .replace(/Today|Tonight|Tomorrow/g, '📅 **$&**')
      // Weather alerts formatting
      .replace(/Severity: (\w+)/g, '⚠️ **Severity: $1**')
      .replace(/Urgency: (\w+)/g, '🚨 **Urgency: $1**')
      .replace(/(Weather Alert|Warning|Watch|Advisory)/gi, '🌪️ **$1**')
      .replace(/Headline: ([^\n]+)/g, '📢 **$1**');
  };

  const handleSendMessage = async () => {
    if (!input.trim()) {
      alert('Please enter a prompt.');
      return;
    }
    
    if (connectionStatus === 'disconnected') {
      alert('MCP server is disconnected. Please check that the server is running on localhost:8765.');
      return;
    }
    
    if (isLoading) {
      return; // Prevent multiple simultaneous requests
    }
    
    const userMessage = input.trim();
    setInput('');
    setIsLoading(true);
    
    // Add user message immediately
    setGeminiResponses(prev => [...prev, {
      prompt: userMessage,
      response: 'Thinking...',
      timestamp: new Date().toLocaleTimeString(),
      isLoading: true
    }]);
    
    try {
      const response = await callGemini(userMessage, tools);
      const responseText = response.candidates?.[0]?.content?.parts?.[0]?.text || 'No response received from Gemini';
      
      // Format weather data nicely if it contains weather information
      const formattedResponse = formatWeatherResponse(responseText);
      
      // Update the last message with the actual response
      setGeminiResponses(prev => {
        const updated = [...prev];
        updated[updated.length - 1] = {
          prompt: userMessage,
          response: formattedResponse,
          timestamp: new Date().toLocaleTimeString(),
          isLoading: false
        };
        return updated;
      });
    } catch (error) {
      console.error('Error:', error);
      let errorMessage = 'An error occurred';
      
      if (error instanceof Error) {
        if (error.message.includes('Failed to fetch')) {
          errorMessage = 'Network error: Could not reach Gemini API. Check your internet connection.';
        } else if (error.message.includes('WebSocket')) {
          errorMessage = 'MCP server connection error. Please check that the server is running.';
        } else {
          errorMessage = `Error: ${error.message}`;
        }
      }
      
      // Update the last message with error
      setGeminiResponses(prev => {
        const updated = [...prev];
        updated[updated.length - 1] = {
          prompt: userMessage,
          response: errorMessage,
          timestamp: new Date().toLocaleTimeString(),
          isLoading: false,
          isError: true
        };
        return updated;
      });
    } finally {
      setIsLoading(false);
    }
  };

  


  return (
    <div className="App">
      <div className="header">
        <h1>MCP WebSocket Client</h1>
        <div className={`connection-status ${connectionStatus}`}>
          <span className="status-indicator"></span>
          {connectionStatus === 'connecting' && 'Connecting to MCP server...'}
          {connectionStatus === 'connected' && `Connected (${tools.length} tools available)`}
          {connectionStatus === 'disconnected' && 'Disconnected - Check MCP server'}
        </div>
      </div>
      
      <div className="gemini-conversation">
        <h2>Conversation with Gemini</h2>
        <div className="conversation-messages">
          {geminiResponses.map((item, index) => (
            <div key={index} className="conversation-item">
              <div className="user-message">
                <strong>You ({item.timestamp}):</strong> {item.prompt}
              </div>
              <div className={`gemini-response ${item.isError ? 'error' : ''}`}>
                <strong>Gemini:</strong> 
                {item.isLoading ? (
                  <span className="loading">
                    <span className="loading-dots">Thinking</span>
                    <span className="dots">...</span>
                  </span>
                ) : (
                  <div dangerouslySetInnerHTML={{
                    __html: item.response
                      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
                      .replace(/\n/g, '<br/>')
                  }} />
                )}
              </div>
            </div>
          ))}
          {geminiResponses.length === 0 && (
            <div className="empty-state">
              Ask me about the weather! Try:<br/>
              • "Get weather forecast for Providence RI"<br/>
              • "Are there any weather alerts in California?"<br/>
              • "Show me weather warnings for Texas"
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>
      </div>

      <div className="message-input">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask about weather (e.g., 'Get weather forecast for Providence RI' or 'Are there any weather alerts in California?')"
          onKeyPress={(e) => e.key === 'Enter' && !isLoading && handleSendMessage()}
          disabled={isLoading || connectionStatus === 'disconnected'}
        />
        <button 
          onClick={handleSendMessage}
          disabled={isLoading || connectionStatus === 'disconnected' || !input.trim()}
          className={isLoading ? 'loading' : ''}
        >
          {isLoading ? 'Sending...' : 'Send to Gemini'}
        </button>
      </div>

      <details className="debug-area">
        <summary>Debug: MCP Messages ({messages.length})</summary>
        <div className="messages">
          {messages.map((msg, index) => (
            <div key={index} className="message">
              {JSON.stringify(msg, null, 2)}
            </div>
          ))}
        </div>
      </details>
    </div>
  );
}

export default App;
