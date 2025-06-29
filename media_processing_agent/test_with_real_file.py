"""
実際のファイルを使用してFirestoreトリガーをテスト
"""
from google.cloud import firestore
import time
import datetime

# Firestoreクライアントを初期化
db = firestore.Client(project="hackason-464007")

# テスト用のデータ（実際にアップロードしたファイルを使用）
test_data = {
    "media_uri": "gs://hackason-464007.firebasestorage.app/test/test_file.txt",
    "user_id": "test_user_" + datetime.datetime.now().strftime("%Y%m%d_%H%M%S"),
    "child_id": "test_child_002",
    "processing_status": "pending",
    "created_at": firestore.SERVER_TIMESTAMP,
    "updated_at": firestore.SERVER_TIMESTAMP,
    "description": "実際のファイルでのテスト: " + datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
}

# media_uploadsコレクションにドキュメントを追加
print("🚀 Adding test document with real file...")
print(f"📄 File URI: {test_data['media_uri']}")
doc_ref = db.collection('media_uploads').add(test_data)
doc_id = doc_ref[1].id

print(f"\n✅ Document created with ID: {doc_id}")
print(f"📍 Document path: media_uploads/{doc_id}")

# 処理状況を監視
print("\n⏳ Monitoring processing status...")
print("Press Ctrl+C to stop monitoring\n")

try:
    for i in range(60):  # 60秒間監視
        # ドキュメントの現在の状態を取得
        doc = db.collection('media_uploads').document(doc_id).get()
        if doc.exists:
            data = doc.to_dict()
            status = data.get('processing_status', 'unknown')
            
            if i % 5 == 0:  # 5秒ごとに詳細表示
                print(f"\n[{i+1}/60] Status: {status}")
                
            if status == 'processing':
                print("  🔄 Processing in progress...")
            elif status == 'completed':
                print("  ✅ Processing completed!")
                episode_id = data.get('episode_id', 'N/A')
                print(f"  📝 Episode ID: {episode_id}")
                break
            elif status == 'failed':
                print("  ❌ Processing failed!")
                error = data.get('processing_error', 'Unknown error')
                print(f"  ❗ Error: {error}")
                break
        
        time.sleep(1)
        
except KeyboardInterrupt:
    print("\n\n🛑 Monitoring stopped by user")

print("\n📊 Final document state:")
final_doc = db.collection('media_uploads').document(doc_id).get()
if final_doc.exists:
    import json
    print(json.dumps(final_doc.to_dict(), indent=2, default=str))