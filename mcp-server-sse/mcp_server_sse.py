#!/usr/bin/env python3
"""
SSE-based MCP Server
Port: 8766 (different from WebSocket version on 8765)
"""

import asyncio
import json
import time
from typing import Dict, Any, List, Optional
from urllib.request import urlopen
from urllib.error import HTTPError, URLError
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

# Request/Response Models
class MCPRequest(BaseModel):
    jsonrpc: str = "2.0"
    id: Optional[int] = None
    method: str
    params: Optional[Dict[str, Any]] = None

class MCPResponse(BaseModel):
    jsonrpc: str = "2.0"
    id: Optional[int] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, Any]] = None

# Initialize FastAPI app
app = FastAPI(title="MCP SSE Server", version="1.0.0")

# CORS middleware - allow the SSE PWA client
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5174", "http://127.0.0.1:5174"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global state for SSE connections
sse_connections: Dict[str, asyncio.Queue] = {}

# MCP Server Info
SERVER_INFO = {
    "name": "mcp-sse-server",
    "version": "1.0.0",
    "capabilities": {
        "tools": {},
        "resources": {},
        "prompts": {}
    }
}

# Available tools
TOOLS = [
    {
        "name": "get_weather_alerts",
        "description": "Get active weather alerts for the given US state. Requires a 2-letter US state code.\nExamples: CA (California), TX (Texas), FL (Florida), NY (New York), RI (Rhode Island).\nUse this when users ask about weather alerts, warnings, watches, or emergency weather conditions.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "state": {
                    "type": "string",
                    "description": "2-letter US state code (e.g., CA, TX, FL, NY, RI)"
                }
            },
            "required": ["state"]
        }
    },
    {
        "name": "get_coordinates",
        "description": "Get latitude and longitude coordinates for any city or location worldwide using OpenStreetMap.\n\nThis tool can find coordinates for cities, addresses, landmarks, and locations globally.\nUse this when you need coordinates for the weather forecast tool.\n\nExamples: 'Boston MA', 'Paris France', 'Tokyo', '1600 Pennsylvania Avenue', 'Eiffel Tower'\n\nReturns latitude and longitude that can be used with get_weather_forecast.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": "Location name to get coordinates for"
                }
            },
            "required": ["location"]
        }
    },
    {
        "name": "get_weather_forecast",
        "description": "Get REAL-TIME weather forecast from National Weather Service for the given coordinates.\n\nUse this tool when users ask for \"forecast\", \"weather forecast\", or current/upcoming weather conditions.\nThis provides live weather data from the National Weather Service API.\n\nIf you need to convert a city name to coordinates, use the get_coordinates tool first.\nYou can also use your geographic knowledge for well-known cities if preferred.\n\nThis tool requires exact latitude and longitude values and works for US locations only.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "latitude": {
                    "type": "number",
                    "description": "Latitude coordinate (-90 to 90)"
                },
                "longitude": {
                    "type": "number",
                    "description": "Longitude coordinate (-180 to 180)"
                }
            },
            "required": ["latitude", "longitude"]
        }
    }
]

# Available resources
RESOURCES = [
    {
        "uri": "animal://dolphin",
        "name": "Dolphin Information",
        "description": "Information about dolphins"
    },
    {
        "uri": "animal://elephant",
        "name": "Elephant Information", 
        "description": "Information about elephants"
    },
    {
        "uri": "animal://lion",
        "name": "Lion Information",
        "description": "Information about lions"
    },
    {
        "uri": "animal://cloudwhale",
        "name": "Cloudwhale Information",
        "description": "Information about cloudwhales"
    },
    {
        "uri": "weather://report/{location}/{days}",
        "name": "Weather Report",
        "description": "Dynamic weather report template"
    },
    {
        "uri": "animal://facts/{species}/{category}",
        "name": "Animal Facts",
        "description": "Dynamic animal facts template"
    },
    {
        "uri": "climate://{location}/{year}/{month}",
        "name": "Climate Data",
        "description": "Historical climate data template"
    }
]

# Available prompts
PROMPTS = [
    {
        "name": "animal_profile",
        "description": "Create educational animal profile",
        "arguments": [
            {
                "name": "animal",
                "description": "Animal species to profile",
                "required": True
            },
            {
                "name": "detail_level",
                "description": "Level of detail (basic, detailed, expert)",
                "required": False
            }
        ]
    },
    {
        "name": "habitat_weather",
        "description": "Combine animal habitat information with current weather conditions",
        "arguments": [
            {
                "name": "animal",
                "description": "Animal species",
                "required": True
            },
            {
                "name": "location",
                "description": "Geographic location",
                "required": True
            }
        ]
    },
    {
        "name": "travel_wildlife_briefing",
        "description": "Create travel briefing with weather and wildlife information",
        "arguments": [
            {
                "name": "destination",
                "description": "Travel destination",
                "required": True
            },
            {
                "name": "travel_dates",
                "description": "Travel dates",
                "required": False
            }
        ]
    }
]

# Tool implementations
def get_weather_alerts(state: str) -> List[Dict[str, Any]]:
    """Get active weather alerts for the given US state."""
    if not state or len(state) != 2:
        raise ValueError("State must be a 2-letter US state code")
    
    state = state.upper()
    
    try:
        # NWS API for weather alerts
        url = f"https://api.weather.gov/alerts/active?area={state}"
        
        with urlopen(url) as response:
            data = json.loads(response.read().decode())
        
        alerts = []
        for feature in data.get('features', []):
            properties = feature.get('properties', {})
            alerts.append({
                'event': properties.get('event', 'Unknown'),
                'headline': properties.get('headline', ''),
                'description': properties.get('description', ''),
                'severity': properties.get('severity', 'Unknown'),
                'certainty': properties.get('certainty', 'Unknown'),
                'urgency': properties.get('urgency', 'Unknown'),
                'areas': properties.get('areaDesc', ''),
                'effective': properties.get('effective', ''),
                'expires': properties.get('expires', '')
            })
        
        return alerts
    except Exception as e:
        raise RuntimeError(f"Failed to fetch weather alerts: {str(e)}")

def get_coordinates(location: str) -> Dict[str, Any]:
    """Get latitude and longitude coordinates for any city or location worldwide using OpenStreetMap."""
    import urllib.parse
    import time
    
    try:
        # URL encode the location query
        encoded_location = urllib.parse.quote(location)
        
        # Try multiple search strategies
        search_urls = []
        
        # First try: original query
        search_urls.append(f"https://nominatim.openstreetmap.org/search?q={encoded_location}&format=json&limit=5&addressdetails=1")
        
        # Second try: add "United States" if it looks like a US location
        if any(state in location.upper() for state in ['RI', 'MA', 'NY', 'CA', 'TX', 'FL', 'IL', 'PA', 'OH', 'MI', 'GA', 'NC', 'NJ', 'VA', 'WA', 'AZ', 'TN', 'IN', 'MO', 'MD', 'WI', 'CO', 'MN', 'SC', 'AL', 'LA', 'KY', 'OR', 'OK', 'CT', 'IA', 'MS', 'AR', 'KS', 'UT', 'NV', 'NM', 'WV', 'NE', 'ID', 'HI', 'NH', 'ME', 'MT', 'DE', 'SD', 'ND', 'AK', 'VT', 'WY']):
            us_query = urllib.parse.quote(f"{location} United States")
            search_urls.append(f"https://nominatim.openstreetmap.org/search?q={us_query}&format=json&limit=5&addressdetails=1")
        
        data = []
        for url in search_urls:
            # Add delay to respect rate limiting (1 request per second)
            time.sleep(1)
            
            # Make the request with proper headers
            from urllib.request import Request
            headers = {
                'User-Agent': 'MCP-SSE-Demo/1.0 (Educational Demo)'
            }
            
            request = Request(url, headers=headers)
            
            with urlopen(request) as response:
                batch_data = json.loads(response.read().decode())
                data.extend(batch_data)
                
                # If we found US results, break early
                if any('United States' in r.get('display_name', '') for r in batch_data):
                    break
        
        if data and len(data) > 0:
            # Priority selection: prefer US locations for common US city names
            result = data[0]  # default to first result
            
            # Check if we have multiple results and prioritize US locations
            if len(data) > 1:
                # Look for US locations first
                us_results = [r for r in data if 'United States' in r.get('display_name', '')]
                if us_results:
                    result = us_results[0]
                else:
                    # If no US results, look for results with state abbreviations
                    state_results = [r for r in data if any(f' {state} ' in r.get('display_name', '') or r.get('display_name', '').endswith(f' {state}') 
                                                          for state in ['RI', 'MA', 'NY', 'CA', 'TX', 'FL', 'IL', 'PA', 'OH', 'MI', 'GA', 'NC', 'NJ', 'VA', 'WA', 'AZ', 'TN', 'IN', 'MO', 'MD', 'WI', 'CO', 'MN', 'SC', 'AL', 'LA', 'KY', 'OR', 'OK', 'CT', 'IA', 'MS', 'AR', 'KS', 'UT', 'NV', 'NM', 'WV', 'NE', 'ID', 'HI', 'NH', 'ME', 'MT', 'DE', 'SD', 'ND', 'AK', 'VT', 'WY'])]
                    if state_results:
                        result = state_results[0]
            
            lat = float(result['lat'])
            lon = float(result['lon'])
            
            # Extract display name for confirmation
            display_name = result.get('display_name', location)
            
            return {
                "location": location,
                "display_name": display_name,
                "latitude": lat,
                "longitude": lon,
                "found": True,
                "source": "OpenStreetMap Nominatim"
            }
        else:
            return {
                "location": location,
                "error": f"No coordinates found for '{location}'. Try being more specific (e.g., add state/country).",
                "found": False,
                "suggestion": "Try adding more details like state, country, or specific address"
            }
    
    except Exception as e:
        return {
            "location": location,
            "error": f"Failed to get coordinates: {str(e)}",
            "found": False,
            "fallback": "You may need to provide approximate coordinates manually"
        }

def get_weather_forecast(latitude: float, longitude: float) -> Dict[str, Any]:
    """Get weather forecast for the given coordinates."""
    if not (-90 <= latitude <= 90) or not (-180 <= longitude <= 180):
        raise ValueError("Invalid coordinates")
    
    try:
        # First, get the grid point
        grid_url = f"https://api.weather.gov/points/{latitude},{longitude}"
        
        with urlopen(grid_url) as response:
            grid_data = json.loads(response.read().decode())
        
        # Get the forecast URL
        forecast_url = grid_data.get('properties', {}).get('forecast')
        if not forecast_url:
            raise RuntimeError("No forecast URL found in grid point response")
        
        # Get the forecast
        with urlopen(forecast_url) as response:
            forecast_data = json.loads(response.read().decode())
        
        # Extract relevant forecast information
        properties = forecast_data.get('properties', {})
        periods = properties.get('periods', [])
        
        # Format the forecast
        forecast = {
            'location': f"{latitude}, {longitude}",
            'updated': properties.get('updated', 'Unknown'),
            'periods': []
        }
        
        for period in periods:
            forecast['periods'].append({
                'name': period.get('name', 'Unknown'),
                'temperature': period.get('temperature', 'N/A'),
                'temperatureUnit': period.get('temperatureUnit', 'F'),
                'windSpeed': period.get('windSpeed', 'N/A'),
                'windDirection': period.get('windDirection', 'N/A'),
                'shortForecast': period.get('shortForecast', 'No forecast available'),
                'detailedForecast': period.get('detailedForecast', 'No detailed forecast available')
            })
        
        return forecast
    
    except HTTPError as e:
        if e.code == 404:
            return {
                'error': 'Location not found or outside US National Weather Service coverage area',
                'latitude': latitude,
                'longitude': longitude,
                'suggestion': 'Try a location within the United States'
            }
        else:
            raise RuntimeError(f"HTTP error {e.code}: {e.reason}")
    except URLError as e:
        raise RuntimeError(f"Network error: {e.reason}")
    except Exception as e:
        raise RuntimeError(f"Failed to get weather forecast: {str(e)}")

# Resource readers
def read_resource(uri: str) -> Dict[str, Any]:
    """Read a resource by URI."""
    try:
        if uri.startswith("animal://"):
            # Handle animal resources
            if uri.count("/") == 1:
                # Static animal resource: animal://dolphin
                animal = uri.split("://")[1]
                return read_animal_resource(animal)
            else:
                # Dynamic animal facts: animal://facts/dolphin/habitat
                parts = uri.split("/")
                if len(parts) >= 4 and parts[2] == "facts":
                    species = parts[3]
                    category = parts[4] if len(parts) > 4 else "general"
                    return generate_animal_facts(species, category)
        
        elif uri.startswith("weather://report/"):
            # Dynamic weather report: weather://report/providence-ri/7
            parts = uri.split("/")
            if len(parts) >= 4:
                location = parts[3]
                days = parts[4] if len(parts) > 4 else "7"
                return generate_weather_report(location, days)
        
        elif uri.startswith("climate://"):
            # Climate data: climate://boston/2024/01
            parts = uri.split("/")
            if len(parts) >= 4:
                location = parts[2]
                year = parts[3]
                month = parts[4] if len(parts) > 4 else "01"
                return generate_climate_data(location, year, month)
        
        return {"error": f"Unknown resource URI: {uri}"}
    
    except Exception as e:
        return {"error": f"Failed to read resource {uri}: {str(e)}"}

def read_animal_resource(animal: str) -> Dict[str, Any]:
    """Read animal information from file."""
    try:
        file_path = f"resources/{animal}.txt"
        with open(file_path, 'r') as f:
            content = f.read()
        
        return {
            "contents": [
                {
                    "type": "text",
                    "text": content
                }
            ]
        }
    except FileNotFoundError:
        return {"error": f"Animal resource not found: {animal}"}
    except Exception as e:
        return {"error": f"Failed to read animal resource: {str(e)}"}

def generate_animal_facts(species: str, category: str) -> Dict[str, Any]:
    """Generate dynamic animal facts."""
    facts_db = {
        "dolphin": {
            "habitat": "Dolphins live in oceans and seas around the world, preferring warm, tropical waters.",
            "diet": "Dolphins are carnivores, feeding primarily on fish, squid, and crustaceans.",
            "behavior": "Dolphins are highly social animals, living in groups called pods.",
            "conservation": "Many dolphin species are threatened by pollution, fishing nets, and habitat loss.",
            "physical": "Dolphins have streamlined bodies, a distinctive beak, and a dorsal fin.",
            "reproduction": "Dolphins typically give birth to a single calf after a gestation period of 12 months."
        },
        "elephant": {
            "habitat": "Elephants live in savannas, grasslands, and forests across Africa and Asia.",
            "diet": "Elephants are herbivores, consuming up to 300 pounds of vegetation daily.",
            "behavior": "Elephants live in matriarchal herds led by the oldest female.",
            "conservation": "Elephants face threats from poaching for ivory and habitat destruction.",
            "physical": "Elephants are the largest land mammals, with distinctive trunks and tusks.",
            "reproduction": "Elephants have a gestation period of 22 months, the longest of any mammal."
        },
        "lion": {
            "habitat": "Lions primarily inhabit grasslands, savannas, and open woodlands in Africa.",
            "diet": "Lions are apex predators, hunting large ungulates like zebras and wildebeest.",
            "behavior": "Lions are the only social cats, living in groups called prides.",
            "conservation": "Lion populations have declined significantly due to habitat loss and human conflict.",
            "physical": "Male lions are distinguished by their manes, which darken with age.",
            "reproduction": "Lions typically give birth to 2-4 cubs after a gestation period of 4 months."
        },
        "cloudwhale": {
            "habitat": "Cloudwhales migrate through the atmospheric layers, preferring cumulus formations.",
            "diet": "Cloudwhales feed on atmospheric plankton and condensed water vapor.",
            "behavior": "Cloudwhales are solitary creatures, communicating through low-frequency sky songs.",
            "conservation": "Cloudwhales are endangered due to air pollution and climate change.",
            "physical": "Cloudwhales have translucent bodies and can reach lengths of up to 200 feet.",
            "reproduction": "Cloudwhales reproduce during storm seasons, with calves born in thunderclouds."
        }
    }
    
    fact = facts_db.get(species, {}).get(category, f"No {category} information available for {species}.")
    
    return {
        "contents": [
            {
                "type": "text",
                "text": f"{species.title()} - {category.title()}: {fact}"
            }
        ]
    }

def generate_weather_report(location: str, days: str) -> Dict[str, Any]:
    """Generate a formatted weather report."""
    try:
        days_int = int(days)
        if days_int < 1 or days_int > 14:
            return {"error": "Days must be between 1 and 14"}
        
        # Parse location to get coordinates (simplified for demo)
        location_coords = {
            "providence-ri": (41.8240, -71.4128),
            "boston-ma": (42.3601, -71.0589),
            "new-york-ny": (40.7128, -74.0060),
            "los-angeles-ca": (34.0522, -118.2437),
            "chicago-il": (41.8781, -87.6298)
        }
        
        if location not in location_coords:
            available = ", ".join(location_coords.keys())
            return {"error": f"Location '{location}' not supported. Available: {available}"}
        
        lat, lon = location_coords[location]
        
        # Generate sample report
        report = f"""
WEATHER REPORT for {location.upper().replace('-', ', ')}
Generated: {time.strftime('%Y-%m-%d %H:%M:%S UTC')}
Coordinates: {lat}, {lon}
Forecast Period: {days} days

{'='*50}
"""
        
        # Add sample forecast days
        for i in range(days_int):
            day_name = ["Today", "Tomorrow", "Day 3", "Day 4", "Day 5", "Day 6", "Day 7", 
                       "Day 8", "Day 9", "Day 10", "Day 11", "Day 12", "Day 13", "Day 14"][i]
            temp_high = 70 + (i * 2) % 20
            temp_low = temp_high - 15
            
            report += f"""
{day_name}:
  High: {temp_high}°F
  Low: {temp_low}°F
  Conditions: Partly cloudy
  Wind: 5-10 mph SW
  Humidity: 65%
"""
        
        return {
            "contents": [
                {
                    "type": "text",
                    "text": report
                }
            ]
        }
    
    except ValueError:
        return {"error": "Invalid number of days"}
    except Exception as e:
        return {"error": f"Failed to generate weather report: {str(e)}"}

def generate_climate_data(location: str, year: str, month: str) -> Dict[str, Any]:
    """Generate historical climate data."""
    try:
        year_int = int(year)
        month_int = int(month)
        
        if year_int < 1900 or year_int > 2024:
            return {"error": "Year must be between 1900 and 2024"}
        
        if month_int < 1 or month_int > 12:
            return {"error": "Month must be between 1 and 12"}
        
        month_names = ["", "January", "February", "March", "April", "May", "June",
                      "July", "August", "September", "October", "November", "December"]
        
        # Generate sample climate data
        avg_temp = 60 + (month_int - 6) * 5  # Simulate seasonal variation
        precipitation = 3.5 + (month_int % 4) * 0.5  # Simulate seasonal precipitation
        
        climate_data = f"""
CLIMATE DATA for {location.upper()}
Period: {month_names[month_int]} {year}

Average Temperature: {avg_temp}°F
Total Precipitation: {precipitation:.1f} inches
Average Humidity: 68%
Prevailing Wind: SW at 8 mph
Sunny Days: {20 + (month_int % 3) * 3}
Cloudy Days: {8 - (month_int % 3) * 2}

Historical Context:
- This data represents typical conditions for the region
- Temperature variations of ±5°F are common
- Precipitation patterns may vary significantly year to year
"""
        
        return {
            "contents": [
                {
                    "type": "text",
                    "text": climate_data
                }
            ]
        }
    
    except ValueError:
        return {"error": "Invalid year or month"}
    except Exception as e:
        return {"error": f"Failed to generate climate data: {str(e)}"}

# Prompt handlers
def get_prompt(name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Get a prompt template with filled arguments."""
    if name == "animal_profile":
        animal = arguments.get("animal", "unknown")
        detail_level = arguments.get("detail_level", "basic")
        
        prompt = f"""Create a {detail_level} educational profile for {animal}. 
Include information about habitat, diet, behavior, and conservation status.
Format the response in a clear, engaging way suitable for educational purposes."""
        
        return {
            "description": f"Educational profile for {animal}",
            "messages": [
                {
                    "role": "user",
                    "content": {
                        "type": "text",
                        "text": prompt
                    }
                }
            ]
        }
    
    elif name == "habitat_weather":
        animal = arguments.get("animal", "unknown")
        location = arguments.get("location", "unknown")
        
        prompt = f"""Provide information about {animal} habitat characteristics and how they relate to the current weather conditions in {location}.
Include how weather affects the animal's behavior, feeding patterns, and survival strategies."""
        
        return {
            "description": f"Habitat and weather analysis for {animal} in {location}",
            "messages": [
                {
                    "role": "user",
                    "content": {
                        "type": "text",
                        "text": prompt
                    }
                }
            ]
        }
    
    elif name == "travel_wildlife_briefing":
        destination = arguments.get("destination", "unknown")
        travel_dates = arguments.get("travel_dates", "unspecified")
        
        prompt = f"""Create a travel briefing for {destination} including:
1. Current weather conditions and forecast
2. Local wildlife that might be encountered
3. Best practices for wildlife viewing
4. Safety considerations
5. What to pack based on weather conditions

Travel dates: {travel_dates}"""
        
        return {
            "description": f"Travel briefing for {destination}",
            "messages": [
                {
                    "role": "user",
                    "content": {
                        "type": "text",
                        "text": prompt
                    }
                }
            ]
        }
    
    else:
        return {"error": f"Unknown prompt: {name}"}

# API Endpoints

@app.get("/")
async def root():
    """Root endpoint with server information."""
    return {
        "name": "MCP SSE Server",
        "version": "1.0.0",
        "description": "Model Context Protocol server using Server-Sent Events",
        "port": 8766,
        "endpoints": {
            "initialize": "POST /mcp/initialize",
            "tools": "POST /mcp/tools",
            "resources": "POST /mcp/resources",
            "prompts": "POST /mcp/prompts",
            "sse": "GET /mcp/sse"
        }
    }

@app.post("/mcp/initialize")
async def initialize(request: MCPRequest):
    """Initialize MCP session."""
    return MCPResponse(
        id=request.id,
        result={
            "capabilities": SERVER_INFO["capabilities"],
            "serverInfo": SERVER_INFO
        }
    )

@app.post("/mcp/tools")
async def handle_tool_request(request: MCPRequest):
    """Handle tool-related requests."""
    method = request.method
    params = request.params or {}
    
    if method == "tools/list":
        return MCPResponse(
            id=request.id,
            result={"tools": TOOLS}
        )
    
    elif method == "tools/call":
        tool_name = params.get("name")
        arguments = params.get("arguments", {})
        
        try:
            if tool_name == "get_weather_alerts":
                result = get_weather_alerts(arguments.get("state"))
            elif tool_name == "get_coordinates":
                result = get_coordinates(arguments.get("location"))
            elif tool_name == "get_weather_forecast":
                result = get_weather_forecast(arguments.get("latitude"), arguments.get("longitude"))
            else:
                return MCPResponse(
                    id=request.id,
                    error={"code": -32601, "message": f"Unknown tool: {tool_name}"}
                )
            
            return MCPResponse(
                id=request.id,
                result={
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(result, indent=2)
                        }
                    ]
                }
            )
        
        except Exception as e:
            return MCPResponse(
                id=request.id,
                error={"code": -32603, "message": f"Tool execution failed: {str(e)}"}
            )
    
    else:
        return MCPResponse(
            id=request.id,
            error={"code": -32601, "message": f"Unknown method: {method}"}
        )

@app.post("/mcp/resources")
async def handle_resource_request(request: MCPRequest):
    """Handle resource-related requests."""
    method = request.method
    params = request.params or {}
    
    if method == "resources/list":
        return MCPResponse(
            id=request.id,
            result={"resources": RESOURCES}
        )
    
    elif method == "resources/read":
        uri = params.get("uri")
        if not uri:
            return MCPResponse(
                id=request.id,
                error={"code": -32602, "message": "Missing required parameter: uri"}
            )
        
        try:
            result = read_resource(uri)
            return MCPResponse(
                id=request.id,
                result=result
            )
        
        except Exception as e:
            return MCPResponse(
                id=request.id,
                error={"code": -32603, "message": f"Resource read failed: {str(e)}"}
            )
    
    else:
        return MCPResponse(
            id=request.id,
            error={"code": -32601, "message": f"Unknown method: {method}"}
        )

@app.post("/mcp/prompts")
async def handle_prompt_request(request: MCPRequest):
    """Handle prompt-related requests."""
    method = request.method
    params = request.params or {}
    
    if method == "prompts/list":
        return MCPResponse(
            id=request.id,
            result={"prompts": PROMPTS}
        )
    
    elif method == "prompts/get":
        name = params.get("name")
        arguments = params.get("arguments", {})
        
        if not name:
            return MCPResponse(
                id=request.id,
                error={"code": -32602, "message": "Missing required parameter: name"}
            )
        
        try:
            result = get_prompt(name, arguments)
            return MCPResponse(
                id=request.id,
                result=result
            )
        
        except Exception as e:
            return MCPResponse(
                id=request.id,
                error={"code": -32603, "message": f"Prompt generation failed: {str(e)}"}
            )
    
    else:
        return MCPResponse(
            id=request.id,
            error={"code": -32601, "message": f"Unknown method: {method}"}
        )

@app.get("/mcp/sse")
async def sse_endpoint(request: Request):
    """Server-Sent Events endpoint for real-time updates."""
    
    async def event_generator():
        client_id = f"client_{int(time.time())}"
        queue = asyncio.Queue()
        sse_connections[client_id] = queue
        
        try:
            # Send initial connection event
            yield f"data: {json.dumps({'type': 'connected', 'clientId': client_id})}\n\n"
            
            # Send server info
            yield f"data: {json.dumps({'type': 'serverInfo', 'data': SERVER_INFO})}\n\n"
            
            # Keep connection alive and send any queued events
            while True:
                try:
                    # Wait for events with timeout
                    event = await asyncio.wait_for(queue.get(), timeout=30)
                    yield f"data: {json.dumps(event)}\n\n"
                except asyncio.TimeoutError:
                    # Send heartbeat
                    yield f"data: {json.dumps({'type': 'heartbeat', 'timestamp': time.time()})}\n\n"
                
        except asyncio.CancelledError:
            pass
        finally:
            # Clean up connection
            if client_id in sse_connections:
                del sse_connections[client_id]
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Cache-Control"
        }
    )

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "connections": len(sse_connections)
    }

if __name__ == "__main__":
    print("🚀 Starting MCP SSE Server on port 8766...")
    print("📡 WebSocket version runs on port 8765")
    print("🔄 SSE version runs on port 8766")
    print("🌐 SSE endpoints:")
    print("   - Initialize: POST http://localhost:8766/mcp/initialize")
    print("   - Tools: POST http://localhost:8766/mcp/tools")
    print("   - Resources: POST http://localhost:8766/mcp/resources")
    print("   - Prompts: POST http://localhost:8766/mcp/prompts")
    print("   - SSE Stream: GET http://localhost:8766/mcp/sse")
    print("   - Health: GET http://localhost:8766/health")
    
    uvicorn.run(app, host="127.0.0.1", port=8766)