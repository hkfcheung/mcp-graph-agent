# -*- coding: utf-8 -*-
import os
import requests
import streamlit as st
import json
import urllib3
import traceback # Import traceback for detailed error logging

# --- Configuration ---
DEBUG_MODE = False # Set to True to see debug prints, False to hide them

# --- Disable SSL warnings for verify=False ---
# Note: Disabling SSL verification is insecure. Use only if necessary.
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- Constants ---
API_URL = "https://api.llama.com/v1/chat/completions" # Replace if necessary
MODEL = "Llama-4-Maverick-17B-128E-Instruct-FP8"    # Replace if necessary - CHECK THIS NAME CAREFULLY!
SYSTEM_PROMPT = "You are a helpful assistant that provides concise answers."
MAX_CONVERSATION_TURNS = 10  # Limit conversation history length (user + assistant pairs)

# --- Get API key ---
api_key = os.getenv("LLAMA_API_KEY")
if not api_key:
    st.error("🚨 Missing LLAMA_API_KEY environment variable.")
    st.warning("Please set the LLAMA_API_KEY environment variable and restart.")
    st.stop()

# --- Initialize session state ---
# Stores a list of message dictionaries
if "conversation_history" not in st.session_state:
    st.session_state.conversation_history = []

# --- UI ---
st.title("🧠 Llama Chat")
st.caption(f"Using model: {MODEL}")
if DEBUG_MODE:
    st.caption(f"API Endpoint: {API_URL}")
    st.caption("🐞 DEBUG MODE IS ON")

# --- Container for Chat History ---
# This helps structure the app but doesn't force scrolling by itself.
# Streamlit's default behavior with st.chat_input usually keeps the latest messages visible.
chat_container = st.container()

with chat_container:
    # --- Display conversation history ---
    # Iterate through the list of message dictionaries stored in session state
    for message_dict in st.session_state.conversation_history:
        role = message_dict.get("role")
        content = message_dict.get("content", "[No content found]")
        if role and content: # Basic check
            with st.chat_message(role):
                st.markdown(content)

# --- Input field for user message using st.chat_input ---
# Note: st.chat_input submits on Enter key. Cmd/Ctrl+Enter is not natively supported.
if prompt := st.chat_input("What would you like to ask?"):

    # 1. Create user message dictionary and append to history
    user_message = {"role": "user", "content": prompt}
    st.session_state.conversation_history.append(user_message)

    # 2. Display user message (will be shown on rerun inside the container)
    # Optional: Display immediately for perceived speed, but causes duplication on rerun
    # with st.chat_message("user"):
    #    st.markdown(prompt)

    # 3. Prepare payload for API request (including history)
    history_to_send = st.session_state.conversation_history[-(MAX_CONVERSATION_TURNS * 2):]
    messages_payload = [{"role": "system", "content": SYSTEM_PROMPT}] + history_to_send

    payload = {
        "model": MODEL,
        "messages": messages_payload,
        "max_tokens": 512
    }

    # --- DEBUG: Print Payload ---
    if DEBUG_MODE:
        st.warning("🐞 DEBUG: Sending Payload to API:")
        try:
            st.json(payload)
        except Exception as json_err:
            st.error(f"Error displaying payload as JSON: {json_err}")
            st.text(str(payload))
    # --- End DEBUG ---

    # 4. Send request to API and handle response
    try:
        with st.spinner("Llama is thinking..."):
            response = requests.post(
                API_URL,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json=payload,
                verify=False, # Insecure
                timeout=180
            )
            # --- DEBUG: Print Status Code ---
            if DEBUG_MODE:
                st.info(f"🐞 DEBUG: API Response Status Code: {response.status_code}")
            # --- End DEBUG ---

            response.raise_for_status() # Raises HTTPError for bad responses
            result = response.json()

        # --- DEBUG: Print Raw API Response ---
        if DEBUG_MODE:
            st.info("🐞 DEBUG: Raw API Response JSON:")
            st.json(result)
        # --- End DEBUG ---

        # 5. Parse the response
        assistant_content = "[Error: Could not parse content]"
        assistant_stop_reason = "[Error: Could not parse stop_reason]"
        assistant_message_dict = None

        try:
            completion_message = result.get("completion_message", {})
            content_data = completion_message.get("content", {})

            if isinstance(content_data, dict):
                 assistant_content = content_data.get("text", assistant_content).strip()
            elif isinstance(content_data, str):
                 assistant_content = content_data.strip()
            else:
                 if DEBUG_MODE: st.warning(f"Unexpected type for 'content': {type(content_data)}")

            assistant_stop_reason = completion_message.get("stop_reason", assistant_stop_reason)

            if DEBUG_MODE:
                st.info(f"🐞 DEBUG: Parsed Content: '{assistant_content}'")
                st.info(f"🐞 DEBUG: Parsed Stop Reason: '{assistant_stop_reason}'")

            assistant_message_dict = {
                "role": "assistant",
                "content": assistant_content,
                "stop_reason": assistant_stop_reason
            }

        except Exception as parse_err:
            st.error(f"Error parsing API response: {parse_err}")
            if DEBUG_MODE:
                st.error("Traceback:")
                st.code(traceback.format_exc())


        # 6. Append assistant message dictionary to conversation history
        if assistant_message_dict:
            st.session_state.conversation_history.append(assistant_message_dict)
            # Rerun the script to display the updated history including the assistant message
            st.rerun()
        else:
             st.error("Could not process assistant response due to parsing error.")


    except requests.exceptions.HTTPError as http_err:
        st.error(f"HTTP Error Occurred: {http_err}")
        # --- DEBUG: Print detailed error response ---
        if DEBUG_MODE and http_err.response is not None:
            try:
                error_details = http_err.response.json()
                st.error("🐞 DEBUG: Detailed API Error Response (JSON):")
                st.json(error_details)
            except json.JSONDecodeError:
                st.error("🐞 DEBUG: Raw API Error Response Text:")
                st.code(http_err.response.text)
        # --- End DEBUG ---

    except requests.exceptions.RequestException as e:
        st.error(f"API Request Error: {e}")
        # --- DEBUG: Print details if available ---
        if DEBUG_MODE and hasattr(e, 'response') and e.response is not None:
             st.error(f"Status Code: {e.response.status_code}")
             st.error(f"Response Text: {e.response.text}")
        # --- End DEBUG ---

    except Exception as e:
        st.error(f"An unexpected error occurred: {e}")
        if DEBUG_MODE:
            st.error("Traceback:")
            st.code(traceback.format_exc())

# --- Add a button to clear conversation history ---
st.divider()
if st.button("Clear Conversation History"):
    st.session_state.conversation_history = []
    st.rerun() # Rerun the app to reflect the cleared history