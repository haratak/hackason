import os
from dotenv import load_dotenv
import vertexai
from vertexai.language_models import TextEmbeddingModel
import json
import subprocess

# Load environment variables
load_dotenv()

# Initialize
project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
location = "us-central1"
vertexai.init(project=project_id, location=location)

# Initialize embedding model
embedding_model = TextEmbeddingModel.from_pretrained("text-embedding-004")

# Generate test query embedding
test_query = "アイスクリーム 食べる 子供"
print(f"Generating embedding for query: '{test_query}'")

embeddings = embedding_model.get_embeddings([test_query])
query_vector = embeddings[0].values

print(f"Generated {len(query_vector)}-dimensional vector")
print(f"First 5 values: {query_vector[:5]}")

# Prepare the curl command
endpoint_url = "https://458133176.us-central1-431161319367.vdb.vertexai.goog/v1/projects/431161319367/locations/us-central1/indexEndpoints/7364830149029658624:findNeighbors"

# Create the request body
request_body = {
    "deployedIndexId": "media_analysis_1751159409638",
    "queries": [{
        "datapoint": {
            "featureVector": query_vector
        },
        "neighborCount": 5
    }],
    "returnFullDatapoint": False
}

# Save request body to file
with open('request.json', 'w') as f:
    json.dump(request_body, f)

print("\nExecuting vector search query...")

# Execute curl command
curl_command = [
    'curl', '-X', 'POST',
    '-H', f'Authorization: Bearer $(gcloud auth print-access-token)',
    '-H', 'Content-Type: application/json',
    endpoint_url,
    '-d', '@request.json'
]

# Use shell=True to handle the command substitution
curl_command_str = f"""curl -X POST -H "Authorization: Bearer $(gcloud auth print-access-token)" -H "Content-Type: application/json" {endpoint_url} -d @request.json"""

result = subprocess.run(curl_command_str, shell=True, capture_output=True, text=True)

print("\nResponse:")
print(result.stdout)
if result.stderr:
    print("\nErrors:")
    print(result.stderr)

# Try to parse and format the response
try:
    response = json.loads(result.stdout)
    print("\nFormatted results:")
    if 'nearestNeighbors' in response:
        for i, result in enumerate(response['nearestNeighbors']):
            if 'neighbors' in result:
                print(f"\nQuery {i} results:")
                for neighbor in result['neighbors']:
                    print(f"  - ID: {neighbor.get('datapoint', {}).get('datapointId', 'N/A')}")
                    print(f"    Distance: {neighbor.get('distance', 'N/A')}")
except json.JSONDecodeError:
    print("Could not parse response as JSON")