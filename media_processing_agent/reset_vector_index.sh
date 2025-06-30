#!/bin/bash

# Vertex AI Vector Searchのインデックスをリセットするスクリプト

# 環境変数の設定
PROJECT_ID=${GOOGLE_CLOUD_PROJECT:-"hackason-464007"}
LOCATION=${GOOGLE_CLOUD_LOCATION:-"us-central1"}
INDEX_ID=${VERTEX_AI_INDEX_ID}
INDEX_ENDPOINT_ID=${VERTEX_AI_INDEX_ENDPOINT_ID}

echo "Project ID: $PROJECT_ID"
echo "Location: $LOCATION"
echo "Index ID: $INDEX_ID"
echo "Index Endpoint ID: $INDEX_ENDPOINT_ID"

# インデックスIDが設定されていない場合は警告
if [ -z "$INDEX_ID" ]; then
    echo "ERROR: VERTEX_AI_INDEX_ID is not set in environment variables"
    exit 1
fi

# 現在のインデックス情報を表示
echo ""
echo "=== 現在のインデックス情報 ==="
gcloud ai indexes describe $INDEX_ID \
    --project=$PROJECT_ID \
    --region=$LOCATION

# ユーザーに確認
echo ""
echo "WARNING: This will delete all data in the vector index!"
echo "Do you want to continue? (yes/no)"
read -r response

if [ "$response" != "yes" ]; then
    echo "Operation cancelled."
    exit 0
fi

# オプション1: インデックス内のすべてのデータを削除（推奨）
echo ""
echo "=== インデックスのデータを削除中 ==="
echo "Note: This operation will remove all datapoints from the index."

# Python スクリプトを使用してデータポイントを削除
cat > temp_reset_index.py << 'EOF'
import os
from google.cloud import aiplatform

# Initialize
project_id = os.environ.get('GOOGLE_CLOUD_PROJECT', 'hackason-464007')
location = os.environ.get('GOOGLE_CLOUD_LOCATION', 'us-central1')
index_id = os.environ.get('VERTEX_AI_INDEX_ID')

if not index_id:
    print("ERROR: VERTEX_AI_INDEX_ID is not set")
    exit(1)

aiplatform.init(project=project_id, location=location)

# Get the index
index = aiplatform.MatchingEngineIndex(
    index_name=f"projects/{project_id}/locations/{location}/indexes/{index_id}"
)

print(f"Index: {index.resource_name}")

# Note: Vertex AI does not provide a direct way to list all datapoints
# You need to keep track of datapoint IDs or use a batch deletion approach

# For a complete reset, you might need to:
# 1. Delete and recreate the index (requires re-deployment to endpoints)
# 2. Or maintain a list of all datapoint IDs and delete them

print("To completely reset the index, you have two options:")
print("1. Delete and recreate the index (recommended for complete reset)")
print("2. Delete specific datapoints if you have their IDs")
print("")
print("For option 1, you would need to:")
print("- Undeploy the index from any endpoints")
print("- Delete the index")
print("- Create a new index with the same configuration")
print("- Redeploy to the endpoints")
EOF

python temp_reset_index.py
rm temp_reset_index.py

echo ""
echo "=== 代替案: Firestoreのanalysis_resultsコレクションをクリア ==="
echo "既存のベクトルインデックスを無視して、新しいデータから始めることもできます。"
echo ""
echo "Firestoreのanalysis_resultsコレクションを削除しますか？ (yes/no)"
read -r firestore_response

if [ "$firestore_response" = "yes" ]; then
    # Firestoreのデータを削除するPythonスクリプト
    cat > temp_clear_firestore.py << 'EOF'
from google.cloud import firestore
import os

project_id = os.environ.get('GOOGLE_CLOUD_PROJECT', 'hackason-464007')
db = firestore.Client(project=project_id)

# analysis_resultsコレクションのすべてのドキュメントを削除
print("Deleting all documents in analysis_results collection...")
docs = db.collection('analysis_results').stream()
deleted_count = 0

for doc in docs:
    doc.reference.delete()
    deleted_count += 1
    if deleted_count % 10 == 0:
        print(f"Deleted {deleted_count} documents...")

print(f"Total deleted: {deleted_count} documents from analysis_results")

# episodesコレクションも削除（旧形式のデータ）
print("\nDeleting all documents in episodes collection...")
docs = db.collection('episodes').stream()
deleted_count = 0

for doc in docs:
    doc.reference.delete()
    deleted_count += 1
    if deleted_count % 10 == 0:
        print(f"Deleted {deleted_count} documents...")

print(f"Total deleted: {deleted_count} documents from episodes")

# media_uploadsのprocessing_statusをリセット
print("\nResetting processing_status in media_uploads...")
docs = db.collection('media_uploads').stream()
reset_count = 0

for doc in docs:
    doc.reference.update({
        'processing_status': 'pending',
        'media_id': firestore.DELETE_FIELD,
        'emotional_title': firestore.DELETE_FIELD,
        'episode_count': firestore.DELETE_FIELD,
        'processing_error': firestore.DELETE_FIELD
    })
    reset_count += 1
    if reset_count % 10 == 0:
        print(f"Reset {reset_count} documents...")

print(f"Total reset: {reset_count} documents in media_uploads")
print("\nFirestore cleanup completed!")
EOF

    python temp_clear_firestore.py
    rm temp_clear_firestore.py
fi

echo ""
echo "=== 完了 ==="
echo "データがリセットされました。"
echo "media_uploadsコレクションのドキュメントが再処理されるのを待ってください。"
echo ""
echo "注意: captured_atフィールドを使用するには、以下を確認してください："
echo "1. media_uploadsドキュメントにcaptured_atフィールドが含まれている"
echo "2. Cloud Functionsが最新のコードにデプロイされている"
echo "3. analysis_resultsのドキュメントにcaptured_atが保存される"