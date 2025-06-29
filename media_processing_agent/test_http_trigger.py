"""
HTTPトリガーをテストするスクリプト
"""
import requests
import json

# Cloud FunctionのHTTPエンドポイント
url = "https://process-media-upload-http-626tqruela-uc.a.run.app"

# テストデータ
test_data = {
    "media_uri": "gs://hackason-464007.firebasestorage.app/test/sample_video.mp4",
    "user_id": "test_user_123", 
    "child_id": "test_child_456"
}

print("Sending POST request to HTTP trigger...")
print(f"URL: {url}")
print(f"Data: {json.dumps(test_data, indent=2)}")

try:
    response = requests.post(url, json=test_data, timeout=30)
    print(f"\nStatus Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
except Exception as e:
    print(f"\nError: {e}")
    if hasattr(e, 'response') and e.response is not None:
        print(f"Response text: {e.response.text}")