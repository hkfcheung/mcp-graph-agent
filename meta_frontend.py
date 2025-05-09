# -*- coding: utf-8 -*-
import os
import requests
import streamlit as st
import json
import urllib3
import traceback
import re

# --- Configuration ---
DEBUG_MODE = True
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

API_URL = "https://api.llama.com/v1/chat/completions"
MODEL = "Llama-4-Maverick-17B-128E-Instruct-FP8"

def format_cypher_for_json(cypher_block: str, use_newlines: bool = False) -> str:
    """
    Converts a multiline Cypher string into a JSON-safe string.
    If use_newlines=True, inserts \\n between lines for readability.
    """
    lines = [line.strip() for line in cypher_block.strip().splitlines() if line.strip()]
    joined = "\\n".join(lines) if use_newlines else " ".join(lines)
    escaped = joined.replace("\\", "\\\\").replace('"', '\\"')
    return escaped


def patch_tool_call(tool_call):
    if not isinstance(tool_call, dict):
        raise ValueError("Expected tool_call to be a dictionary.")
    
    if tool_call.get("name") == "saveToNeo4j":
        args = tool_call.get("arguments", {})
        cypher = args.get("cypher", "")

        if not isinstance(cypher, str) or not cypher.strip():
            raise ValueError("Cypher must be a non-empty string.")

        # Remove delimiters if present
        cypher = re.sub(r"\*{6,}.*?CYPHER BLOCK START.*?\*{6,}", "", cypher, flags=re.IGNORECASE)
        cypher = re.sub(r"\*{6,}.*?CYPHER BLOCK END.*?\*{6,}", "", cypher, flags=re.IGNORECASE)
        cypher = cypher.strip()

        args["cypher"] = cypher
        tool_call["arguments"] = args

    return tool_call



# SYSTEM_PROMPT = """
# You are a helpful assistant. When appropriate, respond by calling tools using this exact JSON format:

# {"tool_call": {"name": "listDir", "arguments": {"path": "/Users/ethancheung/Downloads"}}}
# {"tool_call": {"name": "get_weather", "arguments": {"location": "Beijing"}}}

# Available tools:
# - listDir(path): list files in a directory
# - readTextFile(path): read plain text files
# - readPDF(path): extract text from PDF files
# - readDocx(path): extract text from Word documents
# - readExcel(path): extract rows from Excel spreadsheets
# - readImageText(path): extract text from images (OCR)
# - get_weather(location): get the current weather conditions for a city or location
# - saveToNeo4j(cypher): send Cypher statements to Neo4j

# Use these tools to:
# - Read and process files from the Downloads directory.
# - Categorize documents by type and check for personal or protected information (PII).
# - Answer user questions about the current weather using `get_weather`.

# Your goals:
# - If the user only asks to view or list directory contents, use listDir and stop there.
# - If the user requests categorization or graph building:
#   - First, call listDir to get all files.
#   - Then, for each file, call the appropriate read tool (e.g., readPDF for .pdf).
#   - Categorize the document by theme (e.g., resume, invoice, menu).
#   - Identify any personal or protected information (e.g., names, contact info, SSNs, medical terms).
#   - Generate a **single** Cypher block wrapped in:
#     - `MATCH (n) DETACH DELETE n` to clear all existing data,
#     - `MERGE` and `SET` statements for:
#       - file name
#       - category
#       - pii_flag (true/false)
#       - summary text if applicable
#     - Use `MERGE (f)-[:BELONGS_TO]->(c)` for relationships.
#     - If multiple files belong to the same category, reuse that category variable.
#     - If applicable, generate additional `Entity` nodes and `MENTIONS` relationships.
#     - Use a unique variable for each node, such as `f1`, `c1`, `f2`, `c2`, etc.

# When generating Cypher code:
# - Always use `MERGE` instead of `CREATE` to avoid duplicates.
# - Use `MERGE (fX:File {name: ...})` and then `SET fX.category = ..., fX.pii_flag = ..., fX.summary = ...`.
# - Do not reuse the same variable name (`f`, `c`, etc.) more than once in the same query.
# - Group all related statements together in one block and send them in a **single tool_call to `saveToNeo4j`**.

# Example Cypher output format:
# MATCH (n) DETACH DELETE n
# MERGE (f1:File {name: "example.pdf"}) SET f1.category = "manual", f1.pii_flag = false, f1.summary = "Example summary"
# MERGE (c1:Category {name: "manual"}) MERGE (f1)-[:BELONGS_TO]->(c1)
# MERGE (f2:File {name: "another.pdf"}) SET f2.category = "manual", f2.pii_flag = false, f2.summary = "Another summary"
# MERGE (f2)-[:BELONGS_TO]->(c1)

# Only proceed to this final tool_call after all files have been processed. You do not need to wait for tool responses in between.

# If a file cannot be processed (e.g., unsupported format), skip it and continue.

# Example tool usages:
# {"tool_call": {"name": "readPDF", "arguments": {"path": "/Users/ethancheung/Downloads/file.pdf"}}}
# {"tool_call": {"name": "readDocx", "arguments": {"path": "/Users/ethancheung/Downloads/resume.docx"}}}
# {"tool_call": {"name": "readExcel", "arguments": {"path": "/Users/ethancheung/Downloads/license.xlsx"}}}
# {"tool_call": {"name": "get_weather", "arguments": {"location": "Beijing"}}}
# {"tool_call":{"name":"saveToNeo4j","arguments":{"cypher":"MATCH (n) DETACH DELETE n BEGIN MERGE (f1:File {name: \"example.pdf\"}) SET f1.category = \"manual\", f1.pii_flag = false, f1.summary = \"Example summary\" MERGE (c1:Category {name: \"manual\"}) MERGE (f1)-[:BELONGS_TO]->(c1) COMMIT"}}}

# Respond in plain text when no tool is needed.
# """

SYSTEM_PROMPT = """
You are a helpful assistant. When appropriate, respond by calling tools using this exact JSON format:

{"tool_call": {"name": "listDir", "arguments": {"path": "/Users/ethancheung/Downloads"}}}
{"tool_call": {"name": "get_weather", "arguments": {"location": "Beijing"}}}

Available tools:
- listDir(path): list files in a directory
- readTextFile(path): read plain text files
- readPDF(path): extract text from PDF files
- readDocx(path): extract text from Word documents
- readExcel(path): extract rows from Excel spreadsheets
- readImageText(path): extract text from images (OCR)
- get_weather(location): get the current weather conditions for a city or location
- saveToNeo4j(cypher): send Cypher statements to Neo4j
- processPdf(path): process a PDF file using an LLM and load extracted entities/relations into Neo4j

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
  - Generate a **single** Cypher block wrapped in:
    - `MERGE` and `SET` statements for:
      - file name
      - category
      - pii_flag (true/false)
      - summary text if applicable
    - Use `MERGE (f)-[:BELONGS_TO]->(c)` for relationships.
    - If multiple files belong to the same category, reuse that category variable.
    - If applicable, generate additional `Entity` nodes and `MENTIONS` relationships.
    - Use a unique variable for each node, such as `f1`, `c1`, `f2`, `c2`, etc.

When generating Cypher code:
- Wrap raw Cypher code intended for saveToNeo4j in ****** CYPHER BLOCK START ****** and ****** CYPHER BLOCK END ****** markers.
- Always use `MERGE` instead of `CREATE` to avoid duplicates.
- Use `MERGE (fX:File {name: ...})` and then `SET fX.category = ..., fX.pii_flag = ..., fX.summary = ...`.
- Do not reuse the same variable name (`f`, `c`, etc.) more than once in the same query.
- Group all related statements together in one block and send them in a **single tool_call to `saveToNeo4j`**.
- In Cypher strings, escape single quotes using two single quotes ('') instead of a backslash.
- In Cypher strings, always escape single quotes `'` using two single quotes `''`. Do **not** use backslashes (`\`).
- ⚠️ Do not double escape. For example: `'Alice''s file'` is correct. `'Alice''''s file'` is invalid.
- ❌ Do not wrap Cypher code in markdown syntax (e.g., triple backticks). Only include it as a raw string in JSON.


- When calling a tool, your response must be a pure JSON object with the `tool_call` field at the top level. Do not embed the tool call inside text. Do not return markdown, prose, or explanations around it.
- For example, return:
  {
    "tool_call": {
      "name": "saveToNeo4j",
      "arguments": {
        "cypher": "MATCH ... MERGE ..."
      }
    }
  }


Only proceed to this final tool_call after all files have been processed. You do not need to wait for tool responses in between.

If a file cannot be processed (e.g., unsupported format), skip it and continue.

Example tool usages:
{"tool_call": {"name": "readPDF", "arguments": {"path": "/Users/ethancheung/Downloads/file.pdf"}}}
{"tool_call": {"name": "processPdf", "arguments": {"path": "/Users/ethancheung/Downloads/10k.pdf"}}}
{"tool_call": {"name": "readDocx", "arguments": {"path": "/Users/ethancheung/Downloads/resume.docx"}}}
{"tool_call": {"name": "readExcel", "arguments": {"path": "/Users/ethancheung/Downloads/license.xlsx"}}}
{"tool_call": {"name": "get_weather", "arguments": {"location": "Beijing"}}}
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

        if DEBUG_MODE:
            st.subheader("📤 Sent MCP request")
            st.json(payload)

            st.subheader("📥 Received MCP response")
            try:
                st.json(response.json())  # ✅ This is what you want to log
            except Exception as e:
                st.error("⚠️ Could not parse response JSON")
                st.text(response.text)

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
        },
        {
            "type": "function",
            "function": {
                "name": "saveToNeo4j",
                "description": "Send Cypher statements to Neo4j.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "cypher": {
                            "type": "string",
                            "description": "The full Cypher query to execute."
                        }
                    },
                    "required": ["cypher"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "processPdf",
                "description": "Process a PDF file into Neo4j using the GraphRAG pipeline.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Full path to the PDF file to process."
                        }
                    },
                    "required": ["path"]
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
        assistant_content = "[No assistant response generated]"

        if tool_call:
            tool_call = patch_tool_call(tool_call)
            tool_name = tool_call.get("name")
            tool_args = tool_call.get("arguments", {})
        if tool_call:
            # process the tool call...
            assistant_content = f"✅ Tool `{tool_call['name']}` executed."
        elif isinstance(content_data, dict):
            assistant_content = content_data.get("text", "").strip()
        elif isinstance(content_data, str):
            assistant_content = content_data.strip()

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
        # Fallback: Look for a Cypher block delimited by custom markers
        if not tool_call:
            cypher_match = re.search(
                r"\*+.*?CYPHER BLOCK START.*?\*+\s*(.*?)\s*\*+.*?CYPHER BLOCK END.*?\*+",
                content_text,
                re.DOTALL | re.IGNORECASE
            )
            if cypher_match:
                cypher_raw = cypher_match.group(1).strip()
                cypher_raw = re.sub(r"''{2,}", "''", cypher_raw)
                cypher_raw = cypher_raw.encode('utf-8').decode('unicode_escape')  # <--- this line
                cypher_raw = "MATCH (n) DETACH DELETE n\n" + cypher_raw


                tool_call = {
                    "name": "saveToNeo4j",
                    "arguments": {"cypher": cypher_raw}
                }

                if DEBUG_MODE:
                    st.success("✅ Extracted Cypher from CYPHER BLOCK delimiters")
                    st.code(cypher_raw, language="cypher")

                print("CYPHER RAW *************** ", cypher_raw, "****************************")

        print("TOOL CALL *************** ",tool_call,"****************************")
        if tool_call:
            tool_name = tool_call.get("name")
            tool_args = tool_call.get("arguments", {})
            if DEBUG_MODE:
                st.write(f"🔍 Detected tool_name: {tool_name}")
                st.write(f"🔧 Tool arguments:", tool_args)

            try:
                # tool_result = mcp_client.send_request(tool_name, tool_args)
                tool_name = tool_call.get("name", "").strip()
                tool_args = tool_call.get("arguments", {})
                tool_result = mcp_client.send_request(tool_name, tool_args)
                # Optional: special postprocessing for known tools
                if tool_name == "saveToNeo4j":
                    tool_call = patch_tool_call(tool_call)

                    st.success("✅ Cypher query sent to Neo4j!")
                    st.json(tool_result)
                else:
                    st.success(f"✅ Tool `{tool_name}` executed successfully")
                    st.json(tool_result)
                


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
                elif tool_name == "saveToNeo4j":
                    cypher = tool_args.get("cypher", "")
                    if not cypher:
                        st.warning("⚠️ No Cypher code provided.")
                        st.stop()
                    if DEBUG_MODE:
                        st.code(cypher, language="cypher")
                    response = requests.post(
                        "http://localhost:8090/mcp",
                        json={
                            "jsonrpc": "2.0",
                            "method": "saveToNeo4j",
                            "params": {"cypher": cypher},
                            "id": 1
                        }
                    )
                    if response.ok:
                        st.success("✅ Cypher saved to Neo4j")
                        st.json(response.json())
                    else:
                        st.error("❌ Failed to save to Neo4j")
                        st.text(response.text)

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
