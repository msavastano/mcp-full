class WebSocketService {
  private socket: WebSocket | null = null;
  private listeners: Array<(data: any) => void> = [];
  private messageIdCounter = 1;
  private pendingRequests = new Map<number, { resolve: (value: any) => void; reject: (reason?: any) => void }>();
  private isConnected = false;

  connect(url: string, onOpen?: () => void, onClose?: () => void) {
    this.socket = new WebSocket(url, ["mcp"]);
    this.socket.binaryType = 'arraybuffer';

    this.socket.onopen = async () => {
      console.log('WebSocket onopen event fired.');
      console.log('WebSocket connected');
      this.isConnected = true;
      
      // Small delay to ensure connection is fully established
      await new Promise(resolve => setTimeout(resolve, 100));
      
      if (onOpen) {
        onOpen();
      }
      try {
        // Send initialize request
        const initializeResponse = await this.sendRequest({
          "jsonrpc": "2.0",
          "id": this.messageIdCounter++,
          "method": "initialize",
          "params": {
              "protocolVersion": "1.0",
              "capabilities": {},
              "clientInfo": {
                  "name": "My WebSocket Client",
                  "version": "1.0"
              },
              "processId": null,
              "rootUri": null,
              "rootPath": null
          }
        });
        console.log('Initialize response:', initializeResponse);

        // Send initialized notification after receiving initialize response
        this.sendMessage({
          "jsonrpc": "2.0",
          "method": "notifications/initialized",
          "params": {}
        });
        console.log('Initialized notification sent.');

        // Automatically request the list of tools
        const toolList = await this.sendRequest({
            "jsonrpc": "2.0",
            "id": this.messageIdCounter++,
            "method": "tools/list",
            "params": {}
        });
        console.log('Tools list response:', toolList);

        // Automatically request the list of resources
        const resourceList = await this.sendRequest({
            "jsonrpc": "2.0",
            "id": this.messageIdCounter++,
            "method": "resources/list",
            "params": {}
        });
        console.log('Resources list response:', resourceList);

        // Automatically request the list of prompts
        const promptList = await this.sendRequest({
            "jsonrpc": "2.0",
            "id": this.messageIdCounter++,
            "method": "prompts/list",
            "params": {}
        });
        console.log('Prompts list response:', promptList);

      } catch (error) {
        console.error('Initialization failed:', error);
      }
    };

    this.socket.onmessage = (event) => {
      console.log('WebSocketService: Raw message received:', event.data);
      try {
        const data = JSON.parse(event.data as string);

        if (data.id && this.pendingRequests.has(data.id)) {
          // This is a response to a pending request
          const { resolve } = this.pendingRequests.get(data.id)!;
          this.pendingRequests.delete(data.id);
          resolve(data);
        }
        // Pass all messages to listeners, regardless of whether they are responses or notifications
        this.listeners.forEach(listener => listener(data));
      } catch (error) {
        console.error('WebSocketService: Error parsing message:', error, 'Raw data:', event.data);
      }
    };

    this.socket.onclose = () => {
      console.log('WebSocket disconnected');
      this.isConnected = false;
      if (onClose) {
        onClose();
      }
    };

    this.socket.onerror = (error) => {
      console.error('WebSocket error:', error);
    };
  }

  sendRequest(payload: any): Promise<any> {
    return new Promise((resolve, reject) => {
      // Add timeout for requests
      const timeout = setTimeout(() => {
        this.pendingRequests.delete(payload.id);
        reject(new Error('WebSocket request timeout'));
      }, 10000); // 10 second timeout
      
      this.pendingRequests.set(payload.id, { 
        resolve: (value) => {
          clearTimeout(timeout);
          resolve(value);
        }, 
        reject: (reason) => {
          clearTimeout(timeout);
          reject(reason);
        }
      });
      
      if (!this.isConnected || !this.socket || this.socket.readyState !== WebSocket.OPEN) {
        reject(new Error('WebSocket not connected or not ready'));
        return;
      }
      
      this.sendMessage(payload);
    });
  }

  sendMessage(data: any) {
    if (this.socket && this.socket.readyState === WebSocket.OPEN && this.isConnected) {
      this.socket.send(JSON.stringify(data));
    } else {
      console.error('WebSocket is not connected. ReadyState:', this.socket?.readyState, 'IsConnected:', this.isConnected);
    }
  }

  addListener(listener: (data: any) => void) {
    this.listeners.push(listener);
  }

  removeListener(listener: (data: any) => void) {
    this.listeners = this.listeners.filter(l => l !== listener);
  }

  async readResource(uri: string): Promise<any> {
    return this.sendRequest({
      "jsonrpc": "2.0",
      "id": this.messageIdCounter++,
      "method": "resources/read",
      "params": {
        "uri": uri
      }
    });
  }

  async getPrompt(name: string, args?: Record<string, any>): Promise<any> {
    return this.sendRequest({
      "jsonrpc": "2.0",
      "id": this.messageIdCounter++,
      "method": "prompts/get",
      "params": {
        "name": name,
        "arguments": args || {}
      }
    });
  }

  disconnect() {
    if (this.socket) {
      this.socket.close();
    }
  }
}

export const webSocketService = new WebSocketService();

