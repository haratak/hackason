"""
Firestoreトリガーをテストするためのスクリプト（改良版）
処理状況を追跡する
"""
from google.cloud import firestore
import time
import datetime

# Firestoreクライアントを初期化
db = firestore.Client(project="hackason-464007")

# テスト用のダミーデータ（異なるファイルパスを使用）
test_data = {
    "media_uri": "gs://hackason-464007.appspot.com/test/demo_video_001.mp4",
    "user_id": "test_user_" + datetime.datetime.now().strftime("%Y%m%d_%H%M%S"),
    "child_id": "test_child_001",
    "processing_status": "pending",
    "created_at": firestore.SERVER_TIMESTAMP,
    "updated_at": firestore.SERVER_TIMESTAMP,
    "description": "テスト実行: " + datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
}

# media_uploadsコレクションにドキュメントを追加
print("🚀 Adding test document to media_uploads collection...")
print(f"📋 Test data: {test_data}")
doc_ref = db.collection('media_uploads').add(test_data)
doc_id = doc_ref[1].id

print(f"\n✅ Document created with ID: {doc_id}")
print(f"📍 Document path: media_uploads/{doc_id}")

# 処理状況を監視
print("\n⏳ Monitoring processing status...")
print("Press Ctrl+C to stop monitoring\n")

try:
    for i in range(30):  # 30秒間監視
        # ドキュメントの現在の状態を取得
        doc = db.collection('media_uploads').document(doc_id).get()
        if doc.exists:
            data = doc.to_dict()
            status = data.get('processing_status', 'unknown')
            print(f"[{i+1}/30] Status: {status}", end='')
            
            if status == 'processing':
                print(" 🔄 (Processing in progress...)")
            elif status == 'completed':
                print(" ✅ (Processing completed!)")
                episode_id = data.get('episode_id', 'N/A')
                print(f"📝 Episode ID: {episode_id}")
                break
            elif status == 'failed':
                print(" ❌ (Processing failed!)")
                error = data.get('processing_error', 'Unknown error')
                print(f"❗ Error: {error}")
                break
            else:
                print(" ⏳ (Waiting for trigger...)")
        
        time.sleep(1)
        
except KeyboardInterrupt:
    print("\n\n🛑 Monitoring stopped by user")

print("\n📊 Final document state:")
final_doc = db.collection('media_uploads').document(doc_id).get()
if final_doc.exists:
    import json
    print(json.dumps(final_doc.to_dict(), indent=2, default=str))

print("\n🔗 Check logs at:")
print("https://console.firebase.google.com/project/hackason-464007/functions/logs")