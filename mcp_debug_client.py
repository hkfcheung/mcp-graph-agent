import subprocess
import json
import threading
import time

def log_stderr(stream):
    for line in iter(stream.readline, ''):
        print('[MCP SERVER STDERR]', line.strip())

class MCPClient:
    def __init__(self, server_cmd):
        self.server_process = subprocess.Popen(
            server_cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        threading.Thread(target=log_stderr, args=(self.server_process.stderr,), daemon=True).start()
        self.request_id = 0

    def send_raw_request(self, method, params=None):
        self.request_id += 1
        request = {
            'jsonrpc': '2.0',
            'id': self.request_id,
            'method': method,
            'params': params or {}
        }
        self._send_request_json(request)
        return self._get_response()

    def send_request(self, resource, tool, params=None):
        return self.send_raw_request('execute', {
            'resource': resource,
            'tool': tool,
            'params': params or {}
        })

    def _send_request_json(self, request):
        request_json = json.dumps(request) + '\n'
        self.server_process.stdin.write(request_json)
        self.server_process.stdin.flush()

    def _get_response(self):
        response_json = self.server_process.stdout.readline()
        response = json.loads(response_json)
        if 'error' in response:
            raise Exception(f"[{response['error']['code']}] {response['error']['message']}")
        return response['result']

    def close(self):
        self.server_process.kill()

def main():
    server_cmd = ['npx', '-y', '@modelcontextprotocol/server-filesystem', '/Users/ethancheung/Downloads']
    client = MCPClient(server_cmd)

    time.sleep(1)  # Allow server to fully initialize

    print('\n🔍 Attempting to list tools (if supported)...')
    try:
        tools_result = client.send_raw_request('list_tools', {'resource': 'file://'})
        print(json.dumps(tools_result, indent=2))
    except Exception as e:
        print('⚠️ list_tools not supported or failed:', e)

    print('\n📁 Attempting list_directory on /Users/ethancheung/Downloads...')
    try:
        list_dir_result = client.send_request('file://', 'list_directory', {
            'path': '/Users/ethancheung/Downloads'
        })
        print(json.dumps(list_dir_result, indent=2))
    except Exception as e:
        print('❌ list_directory failed:', e)

    client.close()

if __name__ == '__main__':
    main()
