import firebase_admin
import json
from firebase_admin import credentials, firestore

# サービスアカウントキーのパスを設定
SECRET_KEY_PATH = 'hackason-464007-firebase-adminsdk-fbsvc-5e846f6c78.json'
DATA_FILE_PATH = 'upload_data.json'

COLLECTION_NAME = 'notebooks'

# Firebase Admin SDK を初期化
cred = credentials.Certificate(SECRET_KEY_PATH)
firebase_admin.initialize_app(cred)

db = firestore.client()

# データを読み込み
with open(DATA_FILE_PATH, 'r', encoding='utf-8') as f:
    notebook_data = json.load(f)

# Firestoreにデータをアップロード
for notebook in notebook_data:
    # notebook_idを取得してドキュメントIDとして使用
    notebook_id = notebook.pop('notebook_id')
    
    # データをFirestoreに保存
    print(f"Uploading {notebook_id}...")
    db.collection(COLLECTION_NAME).document(notebook_id).set(notebook)
    print(f"Successfully uploaded {notebook_id}")

print("All data uploaded successfully!")