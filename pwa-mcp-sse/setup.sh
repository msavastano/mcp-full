#!/bin/bash

echo "🚀 Setting up PWA MCP SSE Client..."

# Install dependencies
npm install

echo "✅ PWA MCP SSE Client setup complete!"
echo ""
echo "To run the client:"
echo "  cd $(pwd)"
echo "  npm run dev"
echo ""
echo "Client will run on: http://localhost:5174"
echo ""
echo "⚠️  Make sure to:"
echo "1. Set your VITE_GEMINI_API_KEY in .env file"
echo "2. Start the MCP SSE server first (port 8766)"