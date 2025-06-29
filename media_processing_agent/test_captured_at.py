"""
captured_atフィールドを含むデータでFirestoreトリガーをテスト
"""
from google.cloud import firestore
import time
import datetime
from datetime import timezone

# Firestoreクライアントを初期化
db = firestore.Client(project="hackason-464007")

# captured_atを過去の日付に設定（2025年6月15日）
captured_datetime = datetime.datetime(2025, 6, 15, 14, 30, 0, tzinfo=timezone.utc)

# テスト用のデータ（captured_atフィールドを含む）
test_data = {
    "media_uri": "gs://hackason-464007.firebasestorage.app/users/TiMCkbmagjUhVmN3tCZZ9dHUBRl1/1751120542110_image_picker_A9DE88ED-0070-4071-BDF5-AE8952B54808-1858-00000132813B57CDIMG_0043.mov",
    "user_id": "TiMCkbmagjUhVmN3tCZZ9dHUBRl1",
    "child_id": "test_child_with_captured_at",
    "processing_status": "pending",
    "captured_at": captured_datetime,  # 撮影日時を追加
    "created_at": firestore.SERVER_TIMESTAMP,
    "updated_at": firestore.SERVER_TIMESTAMP,
    "description": f"captured_atテスト - 撮影日: {captured_datetime.strftime('%Y-%m-%d %H:%M')}"
}

# media_uploadsコレクションにドキュメントを追加
print("📸 Adding test document with captured_at field...")
print(f"📅 Captured at: {captured_datetime.strftime('%Y-%m-%d %H:%M:%S %Z')}")
print(f"📹 Video URI: {test_data['media_uri']}")
doc_ref = db.collection('media_uploads').add(test_data)
doc_id = doc_ref[1].id

print(f"\n✅ Document created with ID: {doc_id}")
print(f"📍 Document path: media_uploads/{doc_id}")

# 処理状況を監視
print("\n⏳ Monitoring processing status...")
print("Press Ctrl+C to stop monitoring\n")

start_time = time.time()

try:
    for i in range(120):  # 2分間監視
        # ドキュメントの現在の状態を取得
        doc = db.collection('media_uploads').document(doc_id).get()
        if doc.exists:
            data = doc.to_dict()
            status = data.get('processing_status', 'unknown')
            elapsed = int(time.time() - start_time)
            
            if i % 10 == 0:  # 10秒ごとに詳細表示
                print(f"[{elapsed}s] Status: {status}")
                
            if status == 'processing':
                if i % 10 == 0:
                    print("  🔄 Processing...")
            elif status == 'completed':
                print(f"\n  ✅ Processing completed after {elapsed} seconds!")
                episode_id = data.get('episode_id', 'N/A')
                print(f"  📝 Episode ID: {episode_id}")
                
                # エピソードの詳細を確認
                if episode_id != 'N/A':
                    episode_doc = db.collection('episodes').document(episode_id).get()
                    if episode_doc.exists:
                        episode_data = episode_doc.to_dict()
                        print("\n  📊 Episode Details:")
                        print(f"    Media Upload ID: {episode_data.get('media_upload_id', 'N/A')}")
                        print(f"    Captured At: {episode_data.get('captured_at', 'N/A')}")
                        print(f"    Created At: {episode_data.get('created_at', 'N/A')}")
                        print(f"    Title: {episode_data.get('title', 'N/A')}")
                break
            elif status == 'failed':
                print(f"\n  ❌ Processing failed after {elapsed} seconds!")
                error = data.get('processing_error', 'Unknown error')
                print(f"  ❗ Error: {error}")
                break
        
        time.sleep(1)
        
except KeyboardInterrupt:
    print("\n\n🛑 Monitoring stopped by user")

print(f"\n⏱️  Total elapsed time: {int(time.time() - start_time)} seconds")