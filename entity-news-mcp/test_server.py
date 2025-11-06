import requests
import json

BASE_URL = "http://localhost:8000"

# Test 1: Health check
print("Testing health check...")
response = requests.get(f"{BASE_URL}/")
print(f"Status: {response.status_code}")
print(f"Response: {json.dumps(response.json(), indent=2)}")
print()

# Test 2: Get entity news
print("Testing get_entity_news...")
response = requests.post(
    f"{BASE_URL}/tools/get_entity_news",
    json={"entity_name": "Meta"}
)
print(f"Status: {response.status_code}")
result = response.json()
print(f"Success: {result.get('success')}")
print(f"Articles found: {len(result.get('data', []))}")
if result.get('data'):
    print(f"First article: {result['data'][0].get('title', 'N/A')}")
print()