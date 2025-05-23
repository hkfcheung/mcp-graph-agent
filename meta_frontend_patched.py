# -*- coding: utf-8 -*-
import os
import requests
import streamlit as st
import json
import urllib3
import traceback

# --- Configuration ---
DEBUG_MODE = True
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

API_URL = "https://api.llama.com/v1/chat/completions"
MODEL = "Llama-4-Maverick-17B-128E-Instruct-FP8"
SYSTEM_PROMPT = """
You are a helpful assistant. When appropriate, respond by calling tools using this exact JSON format:

{"tool_call": {"name": "listDir", "arguments": {"path": "/Users/ethancheung/Downloads"}}}
{"tool_call": {"name": "get_weather", "arguments": {"location": "Beijing"}}}

Available tools:
- saveToNeo4j(cypher): save Cypher query to Neo4j HTTP endpoint
- listDir(path): list files in a directory
- readTextFile(path): read plain text files
- readPDF(path): extract text from PDF files
- readDocx(path): extract text from Word documents
- readExcel(path): extract rows from Excel spreadsheets
- readImageText(path): extract text from images (OCR)
- get_weather(location): get the current weather conditions for a city or location

Use these tools to:
- Read and process files from the Downloads directory.
- Categorize documents by type and check for personal or protected information (PII).
- Answer user questions about the current weather using `get_weather`.

Your goals:
- If the user only asks to view or list directory contents, use listDir and stop there.
- If the user requests categorization or graph building:
  - First, call listDir to get all files.
  - Then, for each file, call the appropriate read tool (e.g., readPDF for .pdf).
  - Categorize the document by theme (e.g., resume, invoice, menu).
  - Identify any personal or protected information (e.g., names, contact info, SSNs, medical terms).
  - Generate a Cypher `CREATE` or `MERGE` statement with:
    - file name
    - category
    - pii_flag (true/false)
    - summary text if applicable.
- If the user asks about the weather in a location, use the `get_weather` tool.

Only continue to the next step after receiving tool results. Do not attempt to do everything in one response.

If a file cannot be processed (e.g., not supported), skip it and continue.

Example tool usages:
{"tool_call": {"name": "readPDF", "arguments": {"path": "/Users/ethancheung/Downloads/file.pdf"}}}
{"tool_call": {"name": "readDocx", "arguments": {"path": "/Users/ethancheung/Downloads/resume.docx"}}}
{"tool_call": {"name": "readExcel", "arguments": {"path": "/Users/ethancheung/Downloads/ChatGPT License Justification Intake(1-2).xlsx"}}}
{"tool_call": {"name": "get_weather", "arguments": {"location": "Beijing"}}}

Respond in plain text when no tool is needed.
"""


MAX_CONVERSATION_TURNS = 10

# --- MCP Tool Client ---
class MCPHttpClient:
    def __init__(self, url):
        self.url = url
        self.request_id = 0

    def send_request(self, method, params=None):
        self.request_id += 1
        payload = {
            "jsonrpc": "2.0",
            "id": self.request_id,
            "method": method,
            "params": params or {}
        }
        response = requests.post(self.url, json=payload)
        response.raise_for_status()
        result = response.json()
        if 'error' in result:
            raise Exception(f"[{result['error']['code']}] {result['error']['message']}")
        return result['result']

mcp_client = MCPHttpClient("http://localhost:8090/mcp")

# --- Get API key ---
api_key = os.getenv("LLAMA_API_KEY")
if not api_key:
    st.error("\U0001F6A8 Missing LLAMA_API_KEY environment variable.")
    st.warning("Please set the LLAMA_API_KEY environment variable and restart.")
    st.stop()

# --- Initialize session state ---
if "conversation_history" not in st.session_state:
    st.session_state.conversation_history = []

# --- UI ---
st.title("\U0001F9E0 Llama Chat")
st.caption(f"Using model: {MODEL}")
if DEBUG_MODE:
    st.caption(f"API Endpoint: {API_URL}")
    st.caption("\U0001F41E DEBUG MODE IS ON")

chat_container = st.container()
with chat_container:
    for message_dict in st.session_state.conversation_history:
        role = message_dict.get("role")
        content = message_dict.get("content", "[No content found]")
        if role and content:
            with st.chat_message(role):
                st.markdown(content)

if prompt := st.chat_input("What would you like to ask?"):
    user_message = {"role": "user", "content": prompt}
    st.session_state.conversation_history.append(user_message)

    history_to_send = st.session_state.conversation_history[-(MAX_CONVERSATION_TURNS * 2):]
    messages_payload = [{"role": "system", "content": SYSTEM_PROMPT}] + history_to_send

    tools = [
        {
            "type": "function",
            "function": {
                "name": "listDir",
                "description": "List files in a directory.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Directory path to list"
                        }
                    },
                    "required": ["path"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "readTextFile",
                "description": "Read plain text files.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Path to the .txt file"
                        }
                    },
                    "required": ["path"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "readPDF",
                "description": "Extract text from PDF files.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Path to the PDF file"
                        }
                    },
                    "required": ["path"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "readDocx",
                "description": "Extract text from Word documents (.docx).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Path to the DOCX file"
                        }
                    },
                    "required": ["path"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "readExcel",
                "description": "Extract rows from Excel spreadsheets.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Path to the Excel file"
                        }
                    },
                    "required": ["path"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "readImageText",
                "description": "Extract text from images using OCR.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Path to the image file"
                        }
                    },
                    "required": ["path"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Get the current weather conditions for a location.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "location": {
                            "type": "string",
                            "description": "The city or location to get the weather for"
                        }
                    },
                    "required": ["location"]
                }
            }
        }
    ]

    payload = {
        "model": MODEL,
        "messages": messages_payload,
        "max_tokens": 512,
        "tool_choice": "auto",
        "tools": tools  # use the full list above
    }



    if DEBUG_MODE:
        st.warning("\U0001F41E DEBUG: Sending Payload to API:")
        try:
            st.json(payload)
        except Exception as json_err:
            st.error(f"Error displaying payload as JSON: {json_err}")
            st.text(str(payload))

    try:
        with st.spinner("Llama is thinking..."):
            response = requests.post(
                API_URL,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json=payload,
                verify=False,
                timeout=180
            )
            if DEBUG_MODE:
                st.info(f"\U0001F41E DEBUG: API Response Status Code: {response.status_code}")
            response.raise_for_status()
            result = response.json()

        if DEBUG_MODE:
            st.info("\U0001F41E DEBUG: Raw API Response JSON:")
            st.json(result)

        completion_message = result.get("completion_message", {})
        if not completion_message:
            st.error("⚠️ Empty response from model. Please try again or rephrase your request.")
            st.stop()
        content_data = completion_message.get("content", {})
        tool_call = completion_message.get("tool_call")

        # Normalize content and attempt to extract tool_call from content string
        content_text = ""
        if isinstance(content_data, dict):
            content_text = content_data.get("text", "").strip()
        elif isinstance(content_data, str):
            content_text = content_data.strip()
        else:
            content_text = str(content_data)

        if not tool_call:
            try:
                parsed = json.loads(content_text)
                if isinstance(parsed, dict) and "tool_call" in parsed:
                    tool_call = parsed["tool_call"]
                    if DEBUG_MODE:
                        st.info("🛠 Parsed tool_call from stringified JSON:")
                        st.json(tool_call)
            except Exception as parse_err:
                if DEBUG_MODE:
                    st.warning("⚠️ Could not parse tool_call from content:")
                    st.code(str(parse_err))

        if tool_call:
            tool_name = tool_call.get("name")
            tool_args = tool_call.get("arguments", {})
            try:
                tool_result = mcp_client.send_request(tool_name, tool_args)
                if tool_name == "listDir" and isinstance(tool_result, list):
                    file_tool_calls = []
                    for filename in tool_result:
                        path = f"/Users/ethancheung/Downloads/{filename}"
                        if filename.endswith(".pdf"):
                            tool = "readPDF"
                        elif filename.endswith(".docx"):
                            tool = "readDocx"
                        elif filename.endswith(".xlsx"):
                            tool = "readExcel"
                        elif filename.endswith(".txt"):
                            tool = "readTextFile"
                        elif filename.lower().endswith(('.png', '.jpg', '.jpeg')):
                            tool = "readImageText"
                        else:
                            continue
                        file_tool_calls.append({"tool_call": {"name": tool, "arguments": {"path": path}}})
                    assistant_content = (
                        f"✅ `{tool_name}` result:\n\n"
                        f"{json.dumps(tool_result, indent=2)}\n\n"
                        f"Ready to analyze each file: {len(file_tool_calls)} tool calls planned."
                    )
                    for call in file_tool_calls:
                        st.session_state.conversation_history.append({"role": "user", "content": json.dumps(call)})
                else:
                    assistant_content = (
                        f"✅ `{tool_name}` result:\n\n"
                        f"{json.dumps(tool_result, indent=2)}"
                    )
            except Exception as tool_err:
                assistant_content = f"❌ Tool call error: {tool_err}"
        else:
            if isinstance(content_data, dict):
                assistant_content = content_data.get("text", "").strip()
            elif isinstance(content_data, str):
                assistant_content = content_data.strip()
            else:
                assistant_content = "[Unrecognized content type]"

        assistant_message_dict = {
            "role": "assistant",
            "content": assistant_content,
            "stop_reason": completion_message.get("stop_reason", "tool_or_response")
        }

        st.session_state.conversation_history.append(assistant_message_dict)
        st.rerun()

    except requests.exceptions.HTTPError as http_err:
        st.error(f"HTTP Error Occurred: {http_err}")
        if DEBUG_MODE and http_err.response is not None:
            try:
                error_details = http_err.response.json()
                st.error("\U0001F41E DEBUG: Detailed API Error Response (JSON):")
                st.json(error_details)
            except json.JSONDecodeError:
                st.error("\U0001F41E DEBUG: Raw API Error Response Text:")
                st.code(http_err.response.text)

    except requests.exceptions.RequestException as e:
        st.error(f"API Request Error: {e}")
        if DEBUG_MODE and hasattr(e, 'response') and e.response is not None:
            st.error(f"Status Code: {e.response.status_code}")
            st.error(f"Response Text: {e.response.text}")

    except Exception as e:
        st.error(f"An unexpected error occurred: {e}")
        if DEBUG_MODE:
            st.error("Traceback:")
            st.code(traceback.format_exc())

st.divider()
if st.button("Clear Conversation History"):
    st.session_state.conversation_history = []
    st.rerun()
