#!/bin/bash

echo "🚀 Starting MCP SSE Server..."
echo ""

# Check if virtual environment exists
if [ ! -d "venv-new" ]; then
    echo "❌ Virtual environment not found!"
    echo "Please run './setup.sh' first to set up the server."
    exit 1
fi

# Activate virtual environment
source venv-new/bin/activate

echo "📡 Starting server on http://localhost:8766"
echo "🔄 Press Ctrl+C to stop"
echo ""

# Start the server
python mcp_server_sse.py