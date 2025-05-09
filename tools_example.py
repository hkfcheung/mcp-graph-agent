import requests
import os
import json
from dotenv import load_dotenv

load_dotenv()

LLAMA_API_KEY = os.getenv("LLAMA_API_KEY")
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")

headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {LLAMA_API_KEY}"
}

# Function to retrieve weather information
def get_weather(location):
    endpoint = "https://api.openweathermap.org/data/2.5/weather"
    params = {
        "q": location,
        "appid": OPENWEATHER_API_KEY,
        "units": "imperial"
    }

    response = requests.get(endpoint, params=params, verify=False)

    if response.status_code == 200:
        data = response.json()
        weather = {
            "location": f"{data['name']}, {data['sys']['country']}",
            "temperature": f"{data['main']['temp']} °F",
            "description": data['weather'][0]['description'].capitalize(),
            "humidity": f"{data['main']['humidity']}%",
            "wind_speed": f"{data['wind']['speed']} mph"
        }
        return weather
    else:
        return {
            "error": f"HTTP {response.status_code}: {response.text}"
        }

# Initial LLM request with tool definition
data = {
    "messages": [
        {"role": "user", "content": "What's the weather in Beijing?"}
    ],
    "model": "Llama-4-Maverick-17B-128E-Instruct-FP8",
    "tools": [
        {
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Get the current weather conditions for a location.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "location": {"type": "string", "description": "The location to get weather information for."}
                    },
                    "required": ["location"]
                }
            }
        }
    ],
    "tool_choice": "auto"
}

response = requests.post(
    "https://api.llama.com/v1/chat/completions",
    headers=headers,
    json=data,
    verify=False
)

response_json = response.json()

# Check if a tool call is requested
tool_calls = response_json.get('completion_message', {}).get('tool_calls', [])

if tool_calls:
    for tool_call in tool_calls:
        if tool_call['function']['name'] == 'get_weather':
            args = json.loads(tool_call['function']['arguments'])
            weather_result = get_weather(args['location'])

            # Display the weather result clearly
            print(json.dumps(weather_result, indent=2))
else:
    print(response_json)