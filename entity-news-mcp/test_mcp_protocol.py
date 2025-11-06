"""
Test script for MCP protocol endpoints
"""
import requests
import json

BASE_URL = "http://localhost:8000"

def test_mcp_tools_list():
    """Test MCP tools/list method"""
    print("Testing MCP tools/list...")
    
    payload = {
        "jsonrpc": "2.0",
        "method": "tools/list",
        "id": 1
    }
    
    response = requests.post(
        f"{BASE_URL}/mcp",
        json=payload,
        headers={"Content-Type": "application/json"}
    )
    
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    print()

def test_mcp_initialize():
    """Test MCP initialize method"""
    print("Testing MCP initialize...")
    
    payload = {
        "jsonrpc": "2.0",
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {
                "name": "test-client",
                "version": "1.0.0"
            }
        },
        "id": 2
    }
    
    response = requests.post(
        f"{BASE_URL}/mcp",
        json=payload,
        headers={"Content-Type": "application/json"}
    )
    
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    print()

def test_mcp_tool_call():
    """Test MCP tools/call method"""
    print("Testing MCP tools/call...")
    
    payload = {
        "jsonrpc": "2.0",
        "method": "tools/call",
        "params": {
            "name": "get_entity_news",
            "arguments": {
                "entity_name": "Apple"
            }
        },
        "id": 3
    }
    
    response = requests.post(
        f"{BASE_URL}/mcp",
        json=payload,
        headers={"Content-Type": "application/json"}
    )
    
    print(f"Status: {response.status_code}")
    result = response.json()
    print(f"Response: {json.dumps(result, indent=2)}")
    print()

if __name__ == "__main__":
    print("Testing MCP Protocol Endpoints\n")
    print("=" * 50)
    print()
    
    test_mcp_initialize()
    test_mcp_tools_list()
    test_mcp_tool_call()
    
    print("=" * 50)
    print("Tests completed!")

