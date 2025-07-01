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
    """Get active weather alerts for the given US state. Requires a 2-letter US state code.
    Examples: CA (California), TX (Texas), FL (Florida), NY (New York), RI (Rhode Island).
    Use this when users ask about weather alerts, warnings, watches, or emergency weather conditions."""
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

@server.resource("resource://about", name="about", description="Get server information")
def get_about() -> dict:
    """Returns information about the server."""
    return {
        "server_name": "Weather & Animal Resource Server",
        "version": "1.0.0",
        "resources": ["dolphin", "elephant", "lion", "cloudwhale"]
    }

@server.resource("animal://{animal_name}", name="animal-description", description="Get description of an animal")
def get_animal_description(animal_name: str) -> str:
    """Returns the description of a specified animal from a file."""
    import os
    file_path = os.path.join(os.path.dirname(__file__), "resources", f"{animal_name.lower()}.txt")
    try:
        with open(file_path, "r") as f:
            return f.read()
    except FileNotFoundError:
        return f"Description for {animal_name} not found."


@server.prompt()
def weather_briefing(location: str, include_alerts: bool = True) -> str:
    """Generate a comprehensive weather briefing for a specific location.
    
    Args:
        location: The location to get weather for (e.g., "Providence, RI")
        include_alerts: Whether to include weather alerts (default: True)
    """
    prompt = f"""You are a professional meteorologist. Please provide a comprehensive weather briefing for {location}.

Your briefing should include:
1. Current conditions and temperature
2. Detailed forecast for the next 3-7 days
3. Any notable weather patterns or trends
4. Recommendations for outdoor activities
"""
    
    if include_alerts:
        prompt += """5. Any active weather alerts, warnings, or watches
6. Safety recommendations if severe weather is expected
"""
    
    prompt += """
Format your response in a clear, professional manner that would be suitable for a weather briefing.
Use the available weather tools to get accurate, up-to-date information."""
    
    return prompt


@server.prompt()
def animal_profile(animal_name: str, focus: str = "general") -> str:
    """Create a detailed educational profile for an animal.
    
    Args:
        animal_name: Name of the animal (dolphin, elephant, lion, or cloudwhale)
        focus: Focus area - general, habitat, behavior, or conservation
    """
    prompt = f"""You are a wildlife educator. Create a detailed educational profile for {animal_name}.

Please structure your response with the following sections:

1. **Overview**: Brief introduction and key characteristics
2. **Physical Features**: Size, appearance, distinctive traits
3. **Habitat**: Where they live and environmental needs
4. **Behavior**: Social structure, feeding habits, daily activities
5. **Conservation**: Current status and threats
6. **Interesting Facts**: 3-5 fascinating facts most people don't know

"""
    
    if focus == "habitat":
        prompt += "**Special Focus**: Provide extra detail about their habitat requirements and environmental adaptations.\n"
    elif focus == "behavior":
        prompt += "**Special Focus**: Provide extra detail about their social behavior and interactions.\n"
    elif focus == "conservation":
        prompt += "**Special Focus**: Provide extra detail about conservation efforts and threats they face.\n"
    
    prompt += """
Use the available animal resources to get accurate information about this animal.
Format your response in an educational, engaging manner suitable for students."""
    
    return prompt


@server.prompt()
def habitat_weather(animal_name: str, location: str) -> str:
    """Combine animal habitat information with current weather conditions.
    
    Args:
        animal_name: Name of the animal (dolphin, elephant, lion, or cloudwhale)
        location: Geographic location to check weather for
    """
    prompt = f"""You are a wildlife and weather expert. Analyze how current weather conditions in {location} relate to {animal_name} habitat and behavior.

Please provide:

1. **Animal Habitat Requirements**: What climate and weather conditions does {animal_name} prefer?
2. **Current Weather Analysis**: What are the current weather conditions in {location}?
3. **Habitat Suitability**: How suitable are current conditions for {animal_name}?
4. **Behavioral Impact**: How might current weather affect {animal_name} behavior?
5. **Seasonal Considerations**: How do weather patterns affect {animal_name} throughout the year?

Use both weather tools and animal resources to provide a comprehensive analysis.
This is perfect for educational content about wildlife and environmental science."""
    
    return prompt


@server.prompt()
def travel_wildlife_briefing(destination: str, season: str = "current") -> str:
    """Create a travel briefing combining weather and wildlife information.
    
    Args:
        destination: Travel destination
        season: Season to focus on (current, spring, summer, fall, winter)
    """
    prompt = f"""You are a travel and wildlife expert. Create a comprehensive briefing for someone planning to visit {destination}.

Your briefing should cover:

1. **Weather Conditions**: Current or seasonal weather for {destination}
2. **Wildlife Viewing**: What animals might be spotted in this region
3. **Best Viewing Times**: When and where to see wildlife based on weather
4. **Safety Considerations**: Weather and wildlife safety tips
5. **Activity Recommendations**: Outdoor activities suitable for the conditions
6. **Packing Suggestions**: What to bring based on weather and wildlife encounters

"""
    
    if season != "current":
        prompt += f"**Seasonal Focus**: Provide information specifically for {season} conditions.\n"
    
    prompt += """
Use weather tools to get current conditions and any available animal resources.
Format as a practical travel guide that's both informative and engaging."""
    
    return prompt


@app.websocket("/")

async def websocket_endpoint(websocket: WebSocket):
    async with websocket_server(websocket.scope, websocket.receive, websocket.send) as (reader, writer):
        await server._mcp_server.run(reader, writer, server._mcp_server.create_initialization_options())

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8765)
