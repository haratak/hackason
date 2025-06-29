import subprocess
import json

# Generate a 768-dimensional test vector (all zeros except first few values)
test_vector = [0.0] * 768
test_vector[0] = 0.1
test_vector[1] = 0.2
test_vector[2] = 0.3

# Create request body
request_body = {
    "deployedIndexId": "media_analysis_1751159409638",
    "queries": [{
        "datapoint": {
            "featureVector": test_vector
        },
        "neighborCount": 5
    }],
    "returnFullDatapoint": False
}

# Save to file
with open('test_query_768.json', 'w') as f:
    json.dump(request_body, f, indent=2)

print("Created test_query_768.json with 768-dimensional vector")