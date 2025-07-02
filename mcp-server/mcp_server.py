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
def get_coordinates(location: str) -> Dict[str, Any]:
    """Get latitude and longitude coordinates for any city or location worldwide using OpenStreetMap.
    
    This tool can find coordinates for cities, addresses, landmarks, and locations globally.
    Use this when you need coordinates for the weather forecast tool.
    
    Examples: 'Boston MA', 'Paris France', 'Tokyo', '1600 Pennsylvania Avenue', 'Eiffel Tower'
    
    Returns latitude and longitude that can be used with get_weather_forecast."""
    
    import urllib.parse
    import time
    
    try:
        # URL encode the location query
        encoded_location = urllib.parse.quote(location)
        
        # OpenStreetMap Nominatim API (free, no API key required)
        url = f"https://nominatim.openstreetmap.org/search?q={encoded_location}&format=json&limit=1&addressdetails=1"
        
        # Add delay to respect rate limiting (1 request per second)
        time.sleep(1)
        
        # Make the request with proper headers
        from urllib.request import Request
        headers = {
            'User-Agent': 'MCP-Weather-Demo/1.0 (Educational Demo)'
        }
        
        request = Request(url, headers=headers)
        
        with urlopen(request) as response:
            data = json.loads(response.read().decode())
        
        if data and len(data) > 0:
            result = data[0]
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


@server.tool()
def get_weather_forecast(latitude: float, longitude: float) -> Dict[str, Any]:
    """Get weather forecast for the given coordinates.
    
    If you need to convert a city name to coordinates, use the get_coordinates tool first.
    You can also use your geographic knowledge for well-known cities if preferred.
    
    This tool requires exact latitude and longitude values."""
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


@server.resource("weather://report/{location}/{days}", name="weather-report", description="Generate dynamic weather report for location and days")
def get_weather_report(location: str, days: str) -> str:
    """Generate a formatted weather report for a specific location and number of days."""
    try:
        days_int = int(days)
        if days_int < 1 or days_int > 14:
            return "Error: Days must be between 1 and 14"
        
        # Parse location to get coordinates (simplified for demo)
        location_coords = {
            "providence-ri": (41.8240, -71.4128),
            "boston-ma": (42.3601, -71.0589),
            "new-york-ny": (40.7128, -74.0060),
            "los-angeles-ca": (34.0522, -118.2437),
            "chicago-il": (41.8781, -87.6298)
        }
        
        location_key = location.lower().replace(" ", "-").replace(",", "")
        if location_key not in location_coords:
            return f"Weather Report for {location}\n\nLocation not found in our database. Available locations: Providence-RI, Boston-MA, New-York-NY, Los-Angeles-CA, Chicago-IL"
        
        lat, lon = location_coords[location_key]
        
        # This would normally use the weather API, but for demo we'll generate a sample report
        report = f"""# Weather Report for {location.title()}
        
**Location**: {location.title()} ({lat}, {lon})
**Forecast Period**: {days} days
**Generated**: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Summary
This is a dynamically generated weather report using MCP resource templates. In a real implementation, this would call the weather APIs with the provided coordinates and return a {days}-day forecast.

## Resource Template Demo
- **Template URI**: weather://report/{location}/{days}
- **Resolved URI**: weather://report/{location}/{days}
- **Dynamic Content**: This content is generated on-demand based on the parameters in the URI template.

*Note: This demonstrates MCP resource templates - the ability to create dynamic resources using parameterized URIs.*"""
        
        return report
        
    except ValueError:
        return "Error: Days parameter must be a valid number"
    except Exception as e:
        return f"Error generating weather report: {str(e)}"


@server.resource("animal://facts/{species}/{category}", name="animal-facts", description="Get specific facts about animals by category")
def get_animal_facts(species: str, category: str) -> str:
    """Get specific facts about an animal in a particular category."""
    
    # Available categories
    valid_categories = ["habitat", "diet", "behavior", "conservation", "physical", "reproduction"]
    
    if category.lower() not in valid_categories:
        return f"Invalid category '{category}'. Available categories: {', '.join(valid_categories)}"
    
    # Sample fact database (in real implementation, this might query a database)
    animal_facts = {
        "dolphin": {
            "habitat": "Dolphins live in oceans worldwide, preferring warm, shallow waters near coastlines. They can dive up to 1,000 feet deep.",
            "diet": "Dolphins are carnivores that primarily eat fish, squid, and crustaceans. They use echolocation to hunt in murky waters.",
            "behavior": "Dolphins are highly social animals that live in pods of 2-30 individuals. They communicate through clicks, whistles, and body language.",
            "conservation": "Most dolphin species are stable, but some like the Maui's dolphin are critically endangered with fewer than 50 individuals remaining.",
            "physical": "Dolphins have streamlined bodies, blowholes for breathing, and can reach speeds up to 25 mph. Their brains are highly developed.",
            "reproduction": "Dolphins have a gestation period of 12 months and typically give birth to a single calf every 2-3 years."
        },
        "elephant": {
            "habitat": "Elephants live in savannas, forests, and grasslands across Africa and Asia. They require large territories and access to water sources.",
            "diet": "Elephants are herbivores that consume up to 300 pounds of vegetation daily, including grasses, fruits, bark, and roots.",
            "behavior": "Elephants live in matriarchal herds led by the oldest female. They show remarkable intelligence, empathy, and memory.",
            "conservation": "African elephants are endangered due to poaching and habitat loss. Asian elephants are critically endangered with only 40,000-50,000 remaining.",
            "physical": "Elephants are the largest land mammals, weighing up to 14,000 pounds. Their trunks contain over 40,000 muscles.",
            "reproduction": "Elephants have a 22-month gestation period, the longest of any mammal, and give birth to calves weighing 200-300 pounds."
        },
        "lion": {
            "habitat": "Lions primarily live in African savannas and grasslands. A small population of Asiatic lions exists in India's Gir Forest.",
            "diet": "Lions are apex predators that hunt large ungulates like zebras, wildebeest, and buffalo. They require 11-15 pounds of meat daily.",
            "behavior": "Lions are the only social cats, living in prides of 4-6 related females, their cubs, and 1-4 males. They hunt cooperatively.",
            "conservation": "Lions are vulnerable with populations declining 43% over the past 21 years. Only 20,000-25,000 remain in the wild.",
            "physical": "Male lions weigh 330-550 pounds and have distinctive manes. They can reach speeds of 50 mph in short bursts.",
            "reproduction": "Lions have a 3.5-month gestation period and give birth to 1-4 cubs. Cubs stay with the pride for about 2 years."
        },
        "cloudwhale": {
            "habitat": "Cloudwhales inhabit the upper atmosphere at altitudes of 15,000-25,000 feet, following jet streams and weather patterns.",
            "diet": "Cloudwhales feed on atmospheric moisture and electrical energy from lightning, which they absorb through specialized dorsal fins.",
            "behavior": "These ethereal beings migrate seasonally with weather patterns and perform synchronized aerial dances during mating season.",
            "conservation": "Critically Ethereal - only 47 individuals remain due to climate change and increased air traffic disrupting their habitat.",
            "physical": "Cloudwhales are 80-120 feet long, semi-translucent, and surprisingly light (2-3 tons) due to hollow, gas-filled bones.",
            "reproduction": "Cloudwhales reproduce through atmospheric crystallization during storm systems, with offspring emerging from cumulonimbus clouds."
        }
    }
    
    species_key = species.lower()
    category_key = category.lower()
    
    if species_key not in animal_facts:
        return f"No facts available for '{species}'. Available animals: {', '.join(animal_facts.keys())}"
    
    fact = animal_facts[species_key].get(category_key, f"No {category} facts available for {species}")
    
    return f"""# {species.title()} - {category.title()} Facts

**Species**: {species.title()}
**Category**: {category.title()}
**Resource URI**: animal://facts/{species}/{category}

## {category.title()} Information

{fact}

---
*This information was dynamically retrieved using MCP resource templates.*"""


# @server.resource("climate://{location}/{year}/{month}", name="climate-data", description="Get historical climate data for specific location and time")
# def get_climate_data(location: str, year: str, month: str) -> str:
#     """Get historical climate data for a specific location and time period."""
#     try:
#         year_int = int(year)
#         month_int = int(month)
        
#         if year_int < 1900 or year_int > 2024:
#             return "Error: Year must be between 1900 and 2024"
        
#         if month_int < 1 or month_int > 12:
#             return "Error: Month must be between 1 and 12"
        
#         month_names = ["", "January", "February", "March", "April", "May", "June",
#                       "July", "August", "September", "October", "November", "December"]
        
#         # Sample climate data (in real implementation, this would query historical weather APIs)
#         climate_report = f"""# Climate Data for {location.title()}

# **Location**: {location.title()}
# **Period**: {month_names[month_int]} {year}
# **Resource URI**: climate://{location}/{year}/{month}
# **Generated**: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

# ## Historical Climate Summary

# This is a demonstration of dynamic climate data retrieval using MCP resource templates. In a real implementation, this would provide:

# - **Average Temperature**: Historical temperature data for the specified month/year
# - **Precipitation**: Rainfall and snowfall records
# - **Weather Patterns**: Typical weather conditions for the period
# - **Climate Anomalies**: Unusual weather events during this time
# - **Seasonal Trends**: How this period compared to historical averages

## Resource Template Features

# - **Dynamic URI Resolution**: climate://{location}/{year}/{month}
# - **Parameter Validation**: Year (1900-2024), Month (1-12)
# - **On-Demand Generation**: Content created when accessed
# - **Scalable Content**: Can generate data for any valid parameter combination

# *This demonstrates how MCP resource templates enable infinite content combinations without pre-creating static files.*"""
        
#         return climate_report
        
#     except ValueError:
#         return "Error: Year and month must be valid numbers"
#     except Exception as e:
#         return f"Error generating climate data: {str(e)}"


# @server.prompt()
# def weather_briefing(location: str, include_alerts: bool = True) -> str:
#     """Generate a comprehensive weather briefing for a specific location.
    
#     Args:
#         location: The location to get weather for (e.g., "Providence, RI")
#         include_alerts: Whether to include weather alerts (default: True)
#     """
#     prompt = f"""You are a professional meteorologist. Please provide a comprehensive weather briefing for {location}.

# Your briefing should include:
# 1. Current conditions and temperature
# 2. Detailed forecast for the next 3-7 days
# 3. Any notable weather patterns or trends
# 4. Recommendations for outdoor activities
# """
    
#     if include_alerts:
#         prompt += """5. Any active weather alerts, warnings, or watches
# 6. Safety recommendations if severe weather is expected
# """
    
#     prompt += """
# Format your response in a clear, professional manner that would be suitable for a weather briefing.
# Use the available weather tools to get accurate, up-to-date information."""
    
#     return prompt


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
