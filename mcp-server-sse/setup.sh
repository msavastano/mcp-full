#!/bin/bash

echo "🚀 Setting up MCP SSE Server..."

# Create virtual environment if it doesn't exist
if [ ! -d "venv-new" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv-new
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv-new/bin/activate

# Upgrade pip
echo "⬆️  Upgrading pip..."
pip install --upgrade pip

# Install dependencies
echo "📚 Installing dependencies..."
pip install -r requirements.txt

echo ""
echo "✅ MCP SSE Server setup complete!"
echo ""
echo "To run the server:"
echo "  cd $(pwd)"
echo "  source venv-new/bin/activate"
echo "  python mcp_server_sse.py"
echo ""
echo "Server will run on: http://localhost:8766"