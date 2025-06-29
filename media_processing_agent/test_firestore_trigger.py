"""
Firestoreトリガーをテストするためのスクリプト
media_uploadsコレクションにダミーデータを追加する
"""
from google.cloud import firestore
import datetime

# Firestoreクライアントを初期化
db = firestore.Client(project="hackason-464007")

# テスト用のダミーデータ
test_data = {
    "media_uri": "gs://hackason-464007.firebasestorage.app/test/sample_video.mp4",
    "user_id": "test_user_123",
    "child_id": "test_child_456",
    "processing_status": "pending",
    "created_at": firestore.SERVER_TIMESTAMP,
    "updated_at": firestore.SERVER_TIMESTAMP,
    "description": "テスト用のダミービデオファイル"
}

# media_uploadsコレクションにドキュメントを追加
print("Adding test document to media_uploads collection...")
doc_ref = db.collection('media_uploads').add(test_data)
doc_id = doc_ref[1].id

print(f"✅ Document created with ID: {doc_id}")
print(f"📍 Document path: media_uploads/{doc_id}")
print("\n⏳ Firestore trigger should be executing now...")
print("Check the Firebase Console for function logs:")
print("https://console.firebase.google.com/project/hackason-464007/functions/logs")