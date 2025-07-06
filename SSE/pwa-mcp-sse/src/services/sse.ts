/**
 * SSE-based MCP Client Service
 * Replaces WebSocket with Server-Sent Events + HTTP POST requests
 */

export interface MCPRequest {
  jsonrpc: string;
  id?: number;
  method: string;
  params?: any;
}

export interface MCPResponse {
  jsonrpc: string;
  id?: number;
  result?: any;
  error?: any;
}

export interface SSEEvent {
  type: string;
  data?: any;
  clientId?: string;
  timestamp?: number;
}

class SSEService {
  private baseUrl: string;
  private eventSource: EventSource | null = null;
  private connected = false;
  private connecting = false;
  private messageIdCounter = 0;
  private listeners: Map<string, Function[]> = new Map();
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 10;
  private reconnectDelay = 3000;

  constructor(baseUrl = 'http://localhost:8766') {
    this.baseUrl = baseUrl;
  }

  /**
   * Connect to SSE endpoint and initialize MCP session
   */
  async connect(): Promise<void> {
    if (this.connected || this.connecting) {
      console.log('Already connected or connecting');
      return;
    }

    this.connecting = true;
    this.emit('connecting');

    try {
      // Test server availability first
      const healthResponse = await fetch(`${this.baseUrl}/health`);
      if (!healthResponse.ok) {
        throw new Error(`Server health check failed: ${healthResponse.status}`);
      }

      // Initialize MCP session
      const initResponse = await this.sendHttpRequest('initialize', {
        protocolVersion: '2024-11-05',
        capabilities: {
          roots: {
            listChanged: true
          },
          sampling: {}
        },
        clientInfo: {
          name: 'pwa-mcp-sse',
          version: '1.0.0'
        }
      });

      if (initResponse.error) {
        throw new Error(`MCP initialization failed: ${initResponse.error.message}`);
      }

      // Start SSE connection
      await this.startSSEConnection();

      this.connected = true;
      this.connecting = false;
      this.reconnectAttempts = 0;
      this.emit('connected');

      console.log('✅ SSE MCP connection established');

    } catch (error) {
      console.error('❌ SSE connection failed:', error);
      this.connecting = false;
      this.connected = false;
      this.emit('disconnected');
      
      // Attempt reconnection
      if (this.reconnectAttempts < this.maxReconnectAttempts) {
        this.reconnectAttempts++;
        console.log(`🔄 Reconnecting attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts}...`);
        setTimeout(() => this.connect(), this.reconnectDelay);
      } else {
        console.error('❌ Max reconnection attempts reached');
      }
    }
  }

  /**
   * Start Server-Sent Events connection
   */
  private async startSSEConnection(): Promise<void> {
    return new Promise((resolve, reject) => {
      this.eventSource = new EventSource(`${this.baseUrl}/mcp/sse`);

      this.eventSource.onopen = () => {
        console.log('📡 SSE connection opened');
        resolve();
      };

      this.eventSource.onmessage = (event) => {
        try {
          const data: SSEEvent = JSON.parse(event.data);
          this.handleSSEEvent(data);
        } catch (error) {
          console.error('Failed to parse SSE event:', error, event.data);
        }
      };

      this.eventSource.onerror = (error) => {
        console.error('SSE connection error:', error);
        if (this.eventSource?.readyState === EventSource.CLOSED) {
          this.connected = false;
          this.emit('disconnected');
          // Attempt reconnection
          setTimeout(() => this.connect(), this.reconnectDelay);
        }
      };

      // Timeout for initial connection
      setTimeout(() => {
        if (!this.connected) {
          reject(new Error('SSE connection timeout'));
        }
      }, 10000);
    });
  }

  /**
   * Handle Server-Sent Events
   */
  private handleSSEEvent(event: SSEEvent): void {
    console.log('📨 SSE Event:', event);

    switch (event.type) {
      case 'connected':
        console.log('✅ SSE client connected:', event.clientId);
        break;
      
      case 'serverInfo':
        console.log('📋 Server info:', event.data);
        this.emit('serverInfo', event.data);
        break;
      
      case 'heartbeat':
        console.log('💓 Heartbeat:', new Date(event.timestamp! * 1000).toLocaleTimeString());
        break;
      
      case 'notification':
        this.emit('notification', event.data);
        break;
      
      default:
        console.log('❓ Unknown SSE event type:', event.type);
    }
  }

  /**
   * Send HTTP request to MCP server
   */
  private async sendHttpRequest(method: string, params?: any): Promise<MCPResponse> {
    const request: MCPRequest = {
      jsonrpc: '2.0',
      id: ++this.messageIdCounter,
      method,
      params
    };

    let endpoint = '/mcp/tools'; // default

    // Route to appropriate endpoint based on method
    if (method.startsWith('resources/')) {
      endpoint = '/mcp/resources';
    } else if (method.startsWith('prompts/')) {
      endpoint = '/mcp/prompts';
    } else if (method === 'initialize') {
      endpoint = '/mcp/initialize';
    }

    try {
      const response = await fetch(`${this.baseUrl}${endpoint}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(request)
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const result: MCPResponse = await response.json();
      return result;

    } catch (error) {
      console.error('HTTP request failed:', error);
      throw error;
    }
  }

  /**
   * Send MCP request (wrapper around sendHttpRequest)
   */
  async sendRequest(request: MCPRequest): Promise<MCPResponse> {
    if (!this.connected) {
      throw new Error('Not connected to MCP server');
    }

    const response = await this.sendHttpRequest(request.method, request.params);
    return response;
  }

  /**
   * List available tools
   */
  async listTools(): Promise<any[]> {
    const response = await this.sendHttpRequest('tools/list');
    return response.result?.tools || [];
  }

  /**
   * Call a tool
   */
  async callTool(name: string, args: any): Promise<any> {
    const response = await this.sendHttpRequest('tools/call', {
      name,
      arguments: args
    });
    
    if (response.error) {
      throw new Error(`Tool call failed: ${response.error.message}`);
    }
    
    return response.result;
  }

  /**
   * List available resources
   */
  async listResources(): Promise<any[]> {
    const response = await this.sendHttpRequest('resources/list');
    return response.result?.resources || [];
  }

  /**
   * Read a resource
   */
  async readResource(uri: string): Promise<any> {
    const response = await this.sendHttpRequest('resources/read', { uri });
    
    if (response.error) {
      throw new Error(`Resource read failed: ${response.error.message}`);
    }
    
    return response.result;
  }

  /**
   * List available prompts
   */
  async listPrompts(): Promise<any[]> {
    const response = await this.sendHttpRequest('prompts/list');
    return response.result?.prompts || [];
  }

  /**
   * Get a prompt
   */
  async getPrompt(name: string, args: any = {}): Promise<any> {
    const response = await this.sendHttpRequest('prompts/get', {
      name,
      arguments: args
    });
    
    if (response.error) {
      throw new Error(`Prompt get failed: ${response.error.message}`);
    }
    
    return response.result;
  }

  /**
   * Disconnect from server
   */
  disconnect(): void {
    if (this.eventSource) {
      this.eventSource.close();
      this.eventSource = null;
    }
    this.connected = false;
    this.connecting = false;
    this.emit('disconnected');
    console.log('🔌 SSE connection closed');
  }

  /**
   * Get connection status
   */
  isConnected(): boolean {
    return this.connected;
  }

  /**
   * Get connecting status
   */
  isConnecting(): boolean {
    return this.connecting;
  }

  /**
   * Add event listener
   */
  on(event: string, listener: Function): void {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, []);
    }
    this.listeners.get(event)!.push(listener);
  }

  /**
   * Remove event listener
   */
  off(event: string, listener: Function): void {
    const eventListeners = this.listeners.get(event);
    if (eventListeners) {
      const index = eventListeners.indexOf(listener);
      if (index > -1) {
        eventListeners.splice(index, 1);
      }
    }
  }

  /**
   * Emit event to listeners
   */
  private emit(event: string, data?: any): void {
    const eventListeners = this.listeners.get(event);
    if (eventListeners) {
      eventListeners.forEach(listener => {
        try {
          listener(data);
        } catch (error) {
          console.error('Event listener error:', error);
        }
      });
    }
  }
}

// Export singleton instance
export const sseService = new SSEService();