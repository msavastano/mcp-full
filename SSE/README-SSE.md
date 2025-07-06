# MCP SSE Demo

This is a Server-Sent Events (SSE) implementation of the Model Context Protocol (MCP) demo. It provides the same functionality as the WebSocket version but uses HTTP + SSE for communication.

## Architecture Comparison

### WebSocket Version (Original)
- **Ports**: MCP Server: 8765, PWA Client: 5173
- **Communication**: Bidirectional WebSocket with JSON-RPC 2.0
- **Real-time**: Full duplex communication

### SSE Version (This Project)
- **Ports**: MCP Server: 8766, PWA Client: 5174
- **Communication**: HTTP POST requests + Server-Sent Events
- **Real-time**: HTTP requests for client→server, SSE for server→client

## Project Structure

```
mcp-full/
├── mcp-server-sse/          # SSE-based MCP server (port 8766)
│   ├── mcp_server_sse.py    # FastAPI server with SSE endpoints  
│   ├── requirements.txt     # Python dependencies
│   ├── setup.sh            # Setup script
│   ├── start.sh            # Start server script
│   ├── venv-new/           # Python virtual environment
│   └── resources/          # Animal data files
└── pwa-mcp-sse/            # SSE-based PWA client (port 5174)
    ├── src/
    │   ├── services/
    │   │   ├── sse.ts      # SSE service (replaces websocket.ts)
    │   │   └── gemini.ts   # Gemini API integration
    │   └── App.tsx         # Main React component
    ├── package.json        # Node.js dependencies
    ├── .gitignore          # Git ignore file
    └── node_modules/       # NPM dependencies
```

## Quick Start

### 1. Setup MCP SSE Server

```bash
cd mcp-server-sse
./setup.sh
./start.sh
```

Server will start on http://localhost:8766

### 2. Setup PWA SSE Client

```bash
cd pwa-mcp-sse
npm install

# Create .env file with your Gemini API key
echo "VITE_GEMINI_API_KEY=your_api_key_here" > .env

npm run dev
```

Client will start on http://localhost:5174

## Features

### Tools Available
- **get_weather_alerts**: Get weather alerts for US states
- **get_coordinates**: Convert locations to coordinates using OpenStreetMap
- **get_weather_forecast**: Get real-time weather forecasts from National Weather Service

### Resources Available
- **Static Resources**: Animal information (dolphin, elephant, lion, cloudwhale)
- **Dynamic Resources**: 
  - Weather reports with customizable days
  - Animal facts by category
  - Historical climate data

### Prompts Available
- **animal_profile**: Create educational animal profiles
- **habitat_weather**: Combine animal habitat with weather conditions
- **travel_wildlife_briefing**: Travel briefings with weather and wildlife info

## API Endpoints (SSE Server)

### HTTP Endpoints
- `POST /mcp/initialize` - Initialize MCP session
- `POST /mcp/tools` - Tool operations (list, call)
- `POST /mcp/resources` - Resource operations (list, read)
- `POST /mcp/prompts` - Prompt operations (list, get)
- `GET /mcp/sse` - Server-Sent Events stream
- `GET /health` - Health check

### SSE Events
- `connected` - Client connected with ID
- `serverInfo` - Server capabilities and info
- `heartbeat` - Keep-alive messages (every 30 seconds)
- `notification` - Server notifications

## Technical Differences from WebSocket Version

### Communication Pattern
```
WebSocket Version:
Client ←──WebSocket──→ Server

SSE Version:
Client ──HTTP POST──→ Server
Client ←──SSE Stream─── Server
```

### Request Handling
- **WebSocket**: Single persistent connection for all communication
- **SSE**: HTTP POST for requests + SSE stream for real-time updates

### Error Handling
- **WebSocket**: Connection-level error handling
- **SSE**: HTTP status codes + SSE connection management

### Reconnection
- **WebSocket**: WebSocket reconnection logic
- **SSE**: EventSource auto-reconnection + HTTP retry logic

## Running Both Versions Side-by-Side

You can run both versions simultaneously for comparison:

```bash
# Terminal 1: WebSocket MCP Server
cd mcp-server
source venv/bin/activate
python mcp_server.py  # Runs on port 8765

# Terminal 2: SSE MCP Server  
cd mcp-server-sse
./start.sh  # Runs on port 8766

# Terminal 3: WebSocket PWA Client
cd pwa-mcp
npm run dev  # Runs on port 5173

# Terminal 4: SSE PWA Client
cd pwa-mcp-sse  
npm run dev  # Runs on port 5174
```

## Example Usage

1. **Weather Forecast**: "Get weather forecast for Providence RI"
2. **Weather Report**: "Give me a 5-day weather report for Boston"
3. **Animal Information**: Click on animal prompts or ask "Tell me about dolphins"
4. **Weather Alerts**: "Are there any weather alerts for Rhode Island?"

## Benefits of SSE vs WebSocket

### SSE Advantages
- **Simpler Protocol**: Standard HTTP + EventSource API
- **Better Caching**: HTTP requests can be cached
- **Firewall Friendly**: Works through most firewalls
- **Auto-Reconnection**: Built-in EventSource reconnection
- **Simpler Debugging**: Standard HTTP requests in dev tools

### WebSocket Advantages
- **Full Duplex**: True bidirectional communication
- **Lower Latency**: No HTTP overhead per message
- **Better for Real-time**: Ideal for continuous data streams
- **Protocol Flexibility**: Can use custom protocols

## Troubleshooting

### Common Issues

1. **CORS Errors**: Make sure both servers are running and CORS is configured correctly
2. **API Key Issues**: Ensure VITE_GEMINI_API_KEY is set in the .env file
3. **Port Conflicts**: Check that ports 8766 and 5174 are not in use
4. **SSE Connection Issues**: Check browser network tab for EventSource connection

### Debug Mode
The PWA client includes a debug panel that shows:
- Raw SSE events
- HTTP request/response data
- MCP protocol messages
- Gemini API interactions

## Development

### Adding New Tools
1. Add tool definition to `TOOLS` array in `mcp_server_sse.py`
2. Implement tool function
3. Add HTTP handler in `handle_tool_request()`

### Adding New Resources
1. Add resource definition to `RESOURCES` array
2. Implement resource reader in `read_resource()`
3. Handle URI patterns in the reader

### Adding New Prompts
1. Add prompt definition to `PROMPTS` array
2. Implement prompt generator in `get_prompt()`

## License

This project is for educational purposes demonstrating MCP with Server-Sent Events.