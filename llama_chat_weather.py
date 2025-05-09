# -*- coding: utf-8 -*-
import os
import requests
import streamlit as st
import json
import urllib3
import traceback
from dotenv import load_dotenv

# --- Load environment variables ---
load_dotenv()

# --- Configuration ---
DEBUG_MODE = False
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

API_URL = "https://api.llama.com/v1/chat/completions"
MODEL = "Llama-4-Maverick-17B-128E-Instruct-FP8"
SYSTEM_PROMPT = "You are a helpful assistant that provides concise answers."
MAX_CONVERSATION_TURNS = 10

# --- Get API keys ---
LLAMA_API_KEY = os.getenv("LLAMA_API_KEY")
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")
if not LLAMA_API_KEY:
    st.error("🚨 Missing LLAMA_API_KEY environment variable.")
    st.stop()

# --- Weather Tool Function ---
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
        return {
            "location": f"{data['name']}, {data['sys']['country']}",
            "temperature": f"{data['main']['temp']} °F",
            "description": data['weather'][0]['description'].capitalize(),
            "humidity": f"{data['main']['humidity']}%",
            "wind_speed": f"{data['wind']['speed']} mph"
        }
    else:
        return {
            "error": f"HTTP {response.status_code}: {response.text}"
        }

# --- Initialize session state ---
if "conversation_history" not in st.session_state:
    st.session_state.conversation_history = []

# --- UI ---
st.title("🧠 Llama Chat")
st.caption(f"Using model: {MODEL}")

chat_container = st.container()
with chat_container:
    for message in st.session_state.conversation_history:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

if prompt := st.chat_input("What would you like to ask?"):
    user_message = {"role": "user", "content": prompt}
    st.session_state.conversation_history.append(user_message)

    # --- Manual weather detection ---
    if "weather in" in prompt.lower():
        try:
            city = prompt.lower().split("weather in")[1].strip().rstrip("?")
            weather = get_weather(city)
            assistant_content = json.dumps(weather, indent=2)
            assistant_message = {"role": "assistant", "content": assistant_content}
            st.session_state.conversation_history.append(assistant_message)
            st.rerun()
        except Exception as e:
            st.error(f"Weather lookup failed: {e}")
    else:
        history_to_send = st.session_state.conversation_history[-(MAX_CONVERSATION_TURNS * 2):]
        messages_payload = [{"role": "system", "content": SYSTEM_PROMPT}] + history_to_send

        payload = {
            "model": MODEL,
            "messages": messages_payload,
            "max_tokens": 512
        }

        try:
            with st.spinner("Llama is thinking..."):
                response = requests.post(
                    API_URL,
                    headers={
                        "Authorization": f"Bearer {LLAMA_API_KEY}",
                        "Content-Type": "application/json"
                    },
                    json=payload,
                    verify=False,
                    timeout=180
                )
                response.raise_for_status()
                result = response.json()

            content_data = result.get('completion_message', {}).get('content', {})
            assistant_content = content_data.get('text', '[No response]') if isinstance(content_data, dict) else str(content_data).strip()

            assistant_message = {"role": "assistant", "content": assistant_content}
            st.session_state.conversation_history.append(assistant_message)
            st.rerun()

        except Exception as e:
            st.error(f"Error: {e}")
            if DEBUG_MODE:
                st.code(traceback.format_exc())

if st.button("Clear Conversation History"):
    st.session_state.conversation_history = []
    st.rerun()
