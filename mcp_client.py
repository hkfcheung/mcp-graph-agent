import requests
import json

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

def main():
    client = MCPHttpClient("http://localhost:8090/mcp")

    # List contents
    result = client.send_request("listDir", {"path": "/Users/ethancheung/Downloads"})
    print("📁 Downloads:", result)

    # Optional: read a file
    # content = client.send_request("readFile", {"path": "/Users/ethancheung/Downloads/example.txt"})
    # print("📄 example.txt contents:", content)

if __name__ == "__main__":
    main()
