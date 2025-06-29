import os
import json
import subprocess
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import vertexai
from vertexai.language_models import TextEmbeddingModel

# Initialize
project_id = "431161319367"
location = "us-central1"
vertexai.init(project=project_id, location=location)

# Initialize embedding model
embedding_model = TextEmbeddingModel.from_pretrained("text-embedding-004")

# Fun episode queries
queries = [
    "楽しい 笑顔 遊ぶ 子供",
    "アイスクリーム 食べる 満足 幸せ",
    "公園 滑り台 走る 元気",
    "おもちゃ 遊ぶ 夢中 集中"
]

endpoint_url = "https://458133176.us-central1-431161319367.vdb.vertexai.goog/v1/projects/431161319367/locations/us-central1/indexEndpoints/7364830149029658624:findNeighbors"

for query_text in queries:
    print(f"\n{'='*60}")
    print(f"検索クエリ: '{query_text}'")
    print(f"{'='*60}")
    
    # Generate embedding
    embeddings = embedding_model.get_embeddings([query_text])
    query_vector = embeddings[0].values
    
    # Create request
    request_body = {
        "deployedIndexId": "media_analysis_1751159409638",
        "queries": [{
            "datapoint": {
                "featureVector": query_vector
            },
            "neighborCount": 3
        }],
        "returnFullDatapoint": False
    }
    
    # Save to temp file
    with open('temp_query.json', 'w') as f:
        json.dump(request_body, f)
    
    # Execute search
    curl_command = f'curl -s -X POST -H "Authorization: Bearer $(gcloud auth print-access-token)" -H "Content-Type: application/json" {endpoint_url} -d @temp_query.json'
    result = subprocess.run(curl_command, shell=True, capture_output=True, text=True)
    
    try:
        response = json.loads(result.stdout)
        if 'nearestNeighbors' in response and response['nearestNeighbors']:
            neighbors = response['nearestNeighbors'][0].get('neighbors', [])
            if neighbors:
                print(f"\n見つかったエピソード（上位3件）:")
                for i, neighbor in enumerate(neighbors, 1):
                    episode_id = neighbor.get('datapoint', {}).get('datapointId', 'N/A')
                    distance = neighbor.get('distance', 'N/A')
                    # Note: Higher distance (closer to 1) means more similar for cosine similarity
                    similarity = f"{(1 - abs(distance)) * 100:.1f}%" if isinstance(distance, (int, float)) else "N/A"
                    print(f"{i}. エピソードID: {episode_id}")
                    print(f"   類似度: {similarity} (距離: {distance:.4f})")
            else:
                print("エピソードが見つかりませんでした")
        else:
            print("検索結果が空です")
    except json.JSONDecodeError:
        print(f"エラー: {result.stdout}")

print("\n\n✅ 検索完了")