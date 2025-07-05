#!/usr/bin/env python3
"""
Start the MCP SSE server with proper error handling
"""

import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from mcp_server_simple import HTTPServer, MCPSSEHandler
    print("🚀 Starting MCP SSE Server on port 8766...")
    
    server = HTTPServer(('127.0.0.1', 8766), MCPSSEHandler)
    print("✅ Server started successfully!")
    print("🌐 Access at: http://localhost:8766")
    print("🔄 Press Ctrl+C to stop")
    
    server.serve_forever()
    
except KeyboardInterrupt:
    print("\n🛑 Server stopped by user")
except Exception as e:
    print(f"❌ Server failed to start: {e}")
    import traceback
    traceback.print_exc()