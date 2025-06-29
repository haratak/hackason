"""
実際の動画ファイルを使用してFirestoreトリガーをテスト
"""
from google.cloud import firestore
import time
import datetime

# Firestoreクライアントを初期化
db = firestore.Client(project="hackason-464007")

# URLからgs://パスを構築
# Firebase Storage URLから必要な情報を抽出
gs_path = "gs://hackason-464007.firebasestorage.app/users/TiMCkbmagjUhVmN3tCZZ9dHUBRl1/1751120542110_image_picker_A9DE88ED-0070-4071-BDF5-AE8952B54808-1858-00000132813B57CDIMG_0043.mov"

# テスト用のデータ
test_data = {
    "media_uri": gs_path,
    "user_id": "TiMCkbmagjUhVmN3tCZZ9dHUBRl1",  # URLから抽出したユーザーID
    "child_id": "test_child_video",
    "processing_status": "pending",
    "created_at": firestore.SERVER_TIMESTAMP,
    "updated_at": firestore.SERVER_TIMESTAMP,
    "description": "実際の動画ファイルでのテスト: " + datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
}

# media_uploadsコレクションにドキュメントを追加
print("🎥 Adding test document with actual video file...")
print(f"📹 Video URI: {test_data['media_uri']}")
print(f"👤 User ID: {test_data['user_id']}")
doc_ref = db.collection('media_uploads').add(test_data)
doc_id = doc_ref[1].id

print(f"\n✅ Document created with ID: {doc_id}")
print(f"📍 Document path: media_uploads/{doc_id}")

# 処理状況を監視
print("\n⏳ Monitoring processing status...")
print("This may take a few minutes for video processing...")
print("Press Ctrl+C to stop monitoring\n")

start_time = time.time()

try:
    for i in range(300):  # 5分間監視
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
                    print("  🔄 Processing video...")
            elif status == 'completed':
                print(f"\n  ✅ Processing completed after {elapsed} seconds!")
                episode_id = data.get('episode_id', 'N/A')
                print(f"  📝 Episode ID: {episode_id}")
                
                # エピソードの詳細を取得
                if episode_id != 'N/A':
                    episode_doc = db.collection('episodes').document(episode_id).get()
                    if episode_doc.exists:
                        episode_data = episode_doc.to_dict()
                        print("\n  📊 Episode Summary:")
                        print(f"    Title: {episode_data.get('episode_title', 'N/A')}")
                        print(f"    Description: {episode_data.get('description', 'N/A')[:100]}...")
                break
            elif status == 'failed':
                print(f"\n  ❌ Processing failed after {elapsed} seconds!")
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
    data = final_doc.to_dict()
    # 長いテキストを短縮
    if 'processing_error' in data and len(str(data['processing_error'])) > 200:
        data['processing_error'] = str(data['processing_error'])[:200] + '...'
    print(json.dumps(data, indent=2, default=str))

print(f"\n⏱️  Total elapsed time: {int(time.time() - start_time)} seconds")