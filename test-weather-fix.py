#!/usr/bin/env python3
"""
Test script to verify weather forecast fix
"""

import json
import urllib.request

# Test the SSE server weather forecast endpoint
def test_weather_forecast():
    print("🧪 Testing weather forecast fix...")
    
    # Prepare request payload
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "get_weather_forecast",
            "arguments": {
                "latitude": 41.8239891,
                "longitude": -71.4128343
            }
        }
    }
    
    try:
        # Send request to SSE server
        req = urllib.request.Request(
            'http://localhost:8766/mcp/tools',
            data=json.dumps(payload).encode(),
            headers={'Content-Type': 'application/json'}
        )
        
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode())
        
        if 'error' in result:
            print(f"❌ Error: {result['error']}")
            return False
        else:
            print("✅ Weather forecast working!")
            print(f"📊 Response preview: {str(result)[:200]}...")
            return True
            
    except Exception as e:
        print(f"❌ Request failed: {e}")
        return False

if __name__ == "__main__":
    success = test_weather_forecast()
    if success:
        print("\n🎉 Fix successful! Weather forecast should now work in the UI.")
    else:
        print("\n💥 Fix failed. Check server logs for details.")