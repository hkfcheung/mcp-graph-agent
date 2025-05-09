import requests

class MCPFilesystemClient:
    def __init__(self, base_url):
        self.base_url = base_url.rstrip('/')

    def list_files(self, path):
        response = requests.post(
            f"{self.base_url}/listFiles",
            json={"path": path}
        )
        return response.json()

    def read_file(self, path):
        response = requests.post(
            f"{self.base_url}/readFile",
            json={"path": path}
        )
        return response.json()

    def write_file(self, path, content):
        response = requests.post(
            f"{self.base_url}/writeFile",
            json={"path": path, "content": content}
        )
        return response.json()

# Example usage:
if __name__ == '__main__':
    client = MCPFilesystemClient("http://localhost:3000")

    # List files
    print("Listing files:")
    print(client.list_files("/"))

    # Read file
    print("Reading file:")
    print(client.read_file("/example.txt"))

    # Write file
    print("Writing file:")
    print(client.write_file("/example.txt", "Hello, MCP!"))