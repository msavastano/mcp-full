#!/usr/bin/env python3

import asyncio
import datetime
import json
import sys
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode
from urllib.request import urlopen

from mcp.server.fastmcp import FastMCP
from mcp.server.websocket import websocket_server
import httpx
import uvicorn
from fastapi import FastAPI, WebSocket
import mcp.types as types

server = FastMCP("mcp-server")



app = FastAPI()


@server.tool()
def get_weather_alerts(state: str) -> List[Dict[str, Any]]:
    """Get weather alerts for the given US state."""
    if not state or len(state) != 2:
        raise ValueError("State must be a valid 2-letter US state code")
    
    state = state.upper()
    url = f"https://api.weather.gov/alerts/active?area={state}"
    
    try:
        with urlopen(url) as response:
            data = json.loads(response.read().decode())
        
        alerts = []
        for feature in data.get("features", []):
            properties = feature.get("properties", {})
            alert = {
                "headline": properties.get("headline", ""),
                "severity": properties.get("severity", ""),
                "urgency": properties.get("urgency", ""),
                "areas": properties.get("areaDesc", ""),
                "description": properties.get("description", "")
            }
            alerts.append(alert)
        
        return alerts
    except Exception as e:
        raise RuntimeError(f"Failed to fetch weather alerts: {str(e)}")


@server.tool()
def get_weather_forecast(latitude: float, longitude: float) -> Dict[str, Any]:
    """Get weather forecast for the given coordinates. Requires exact latitude and longitude values. 
    If you only have a location name like 'Providence RI', you'll need to look up the coordinates first:
    Providence, RI is approximately 41.8240, -71.4128
    Boston, MA is approximately 42.3601, -71.0589
    New York, NY is approximately 40.7128, -74.0060
    For other locations, use your knowledge of geography to provide approximate coordinates."""
    if not (-90 <= latitude <= 90) or not (-180 <= longitude <= 180):
        raise ValueError("Invalid coordinates")
    
    # First, get the grid point
    url = f"https://api.weather.gov/points/{latitude},{longitude}"
    
    try:
        with urlopen(url) as response:
            data = json.loads(response.read().decode())
        
        forecast_url = data["properties"]["forecast"]
        
        # Get the forecast
        with urlopen(forecast_url) as response:
            forecast_data = json.loads(response.read().decode())
        
        periods = []
        for period in forecast_data["properties"]["periods"][:7]:  # Next 7 periods
            periods.append({
                "name": period["name"],
                "temperature": period["temperature"],
                "temperatureUnit": period["temperatureUnit"],
                "windSpeed": period["windSpeed"],
                "windDirection": period["windDirection"],
                "shortForecast": period["shortForecast"],
                "detailedForecast": period["detailedForecast"]
            })
        
        return {
            "location": f"{latitude}, {longitude}",
            "periods": periods
        }
    except Exception as e:
        raise RuntimeError(f"Failed to fetch weather forecast: {str(e)}")

# @server.resource("resource://about", name="about", description="Get server information")
# def get_about() -> dict:
#     """Returns information about the server."""
#     return {
#         "server_name": "Weather & Joke Server",
#         "version": "1.0.0",
#         "contact": "user@example.com"
#     }

# @server.resource("animal://{animal_name}", name="animal-description", description="Get description of an animal")
# def get_animal_description(animal_name: str) -> str:
#     """Returns the description of a specified animal from a file."""
#     file_path = f"/Users/user/Documents/dev/mcp-server/resources/{animal_name.lower()}.txt"
#     try:
#         with open(file_path, "r") as f:
#             return f.read()
#     except FileNotFoundError:
#         return f"Description for {animal_name} not found."




@app.websocket("/")

async def websocket_endpoint(websocket: WebSocket):
    async with websocket_server(websocket.scope, websocket.receive, websocket.send) as (reader, writer):
        await server._mcp_server.run(reader, writer, server._mcp_server.create_initialization_options())

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8765)
