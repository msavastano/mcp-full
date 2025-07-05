#!/usr/bin/env python3
"""
Quick test script to verify SSE server works without full dependencies
"""

import json
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import threading

class SSEHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed_path = urlparse(self.path)
        
        if parsed_path.path == '/health':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            
            response = {
                "status": "healthy",
                "message": "SSE test server is running",
                "timestamp": time.time()
            }
            self.wfile.write(json.dumps(response).encode())
            
        elif parsed_path.path == '/sse':
            self.send_response(200)
            self.send_header('Content-Type', 'text/event-stream')
            self.send_header('Cache-Control', 'no-cache')
            self.send_header('Connection', 'keep-alive')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            
            # Send initial connection event
            event_data = {
                "type": "connected",
                "message": "SSE connection established",
                "timestamp": time.time()
            }
            self.wfile.write(f"data: {json.dumps(event_data)}\n\n".encode())
            self.wfile.flush()
            
            # Send periodic heartbeats
            for i in range(5):
                time.sleep(2)
                heartbeat = {
                    "type": "heartbeat",
                    "count": i + 1,
                    "timestamp": time.time()
                }
                self.wfile.write(f"data: {json.dumps(heartbeat)}\n\n".encode())
                self.wfile.flush()
        else:
            self.send_response(404)
            self.end_headers()
    
    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        
        try:
            request_data = json.loads(post_data.decode())
            response = {
                "message": "POST request received",
                "received_data": request_data,
                "timestamp": time.time()
            }
            self.wfile.write(json.dumps(response).encode())
        except:
            self.wfile.write(b'{"error": "Invalid JSON"}')

if __name__ == '__main__':
    server = HTTPServer(('localhost', 8766), SSEHandler)
    print("🚀 SSE Test Server starting on http://localhost:8766")
    print("📡 Test endpoints:")
    print("   - GET /health - Health check")
    print("   - GET /sse - Server-Sent Events stream")
    print("   - POST /* - Test POST requests")
    print("🔄 Press Ctrl+C to stop")
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n🛑 Server stopped")
        server.shutdown()