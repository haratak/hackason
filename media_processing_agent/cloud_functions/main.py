"""
Cloud Function for Media Processing
HTTPトリガーとFirestoreトリガーの両方に対応
"""
import functions_framework
import os
import sys
from google.cloud import firestore
import json

# 現在のディレクトリをパスに追加（agent.pyを使うため）
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agent import process_media_for_cloud_function

# 環境変数
PROJECT_ID = os.environ.get('GOOGLE_CLOUD_PROJECT', 'hackason-464007')


@functions_framework.http
def process_media_upload(request):
    """HTTPトリガーでメディア処理を実行"""
    try:
        # リクエストボディを取得
        request_json = request.get_json(silent=True)
        
        if not request_json:
            return {'error': 'Request body is required'}, 400
            
        # 必要なパラメータを取得
        doc_id = request_json.get('doc_id')
        media_uri = request_json.get('media_uri')
        user_id = request_json.get('user_id', '')
        child_id = request_json.get('child_id', '')
        
        if not media_uri:
            return {'error': 'media_uri is required'}, 400
            
        print(f"Processing media: {media_uri}")
        print(f"User: {user_id}, Child: {child_id}")
        
        # Firestoreクライアント
        db = firestore.Client(project=PROJECT_ID, database="database")
        
        # ドキュメントIDがある場合は処理ステータスを更新
        if doc_id:
            db.collection('media_uploads').document(doc_id).update({
                'processing_status': 'processing',
                'updated_at': firestore.SERVER_TIMESTAMP
            })
        
        # メディア分析を実行
        result = process_media_for_cloud_function(
            media_uri=media_uri,
            user_id=user_id,
            child_id=child_id
        )
        
        if result.get("status") == "success":
            episode_id = result.get("episode_id")
            indexed = result.get("indexed", False)
            
            # ドキュメントIDがある場合は処理完了を記録
            if doc_id:
                db.collection('media_uploads').document(doc_id).update({
                    'processing_status': 'completed',
                    'processed_at': firestore.SERVER_TIMESTAMP,
                    'episode_id': episode_id,
                    'updated_at': firestore.SERVER_TIMESTAMP
                })
            
            # 処理ログを記録
            db.collection('processing_logs').add({
                'media_upload_id': doc_id,
                'episode_id': episode_id,
                'event_type': 'media_analysis',
                'status': 'success',
                'timestamp': firestore.SERVER_TIMESTAMP,
                'details': {
                    'user_id': user_id,
                    'child_id': child_id,
                    'media_uri': media_uri,
                    'indexed': indexed
                }
            })
            
            return {
                'status': 'success',
                'episode_id': episode_id,
                'indexed': indexed
            }, 200
        else:
            # エラーの場合
            error_message = result.get("error_message", "Unknown error")
            
            # ドキュメントIDがある場合はエラー状態を記録
            if doc_id:
                db.collection('media_uploads').document(doc_id).update({
                    'processing_status': 'failed',
                    'processing_error': error_message,
                    'updated_at': firestore.SERVER_TIMESTAMP
                })
            
            # エラーログを記録
            db.collection('processing_logs').add({
                'media_upload_id': doc_id,
                'event_type': 'media_analysis',
                'status': 'error',
                'error': error_message,
                'timestamp': firestore.SERVER_TIMESTAMP,
                'details': {
                    'user_id': user_id,
                    'child_id': child_id,
                    'media_uri': media_uri
                }
            })
            
            return {
                'status': 'error',
                'error': error_message
            }, 500
            
    except Exception as e:
        print(f"Error processing media: {str(e)}")
        return {
            'status': 'error',
            'error': str(e)
        }, 500


@functions_framework.cloud_event
def process_media_upload_firestore(cloud_event):
    """Firestoreトリガーでメディア処理を実行"""
    # デバッグ: イベント全体をログ出力
    print(f"Cloud Event Type: {cloud_event['type']}")
    print(f"Cloud Event Subject: {cloud_event.get('subject', 'N/A')}")
    
    # イベントデータの全体構造を取得
    event_data = cloud_event.data
    print(f"Event data keys: {list(event_data.keys())}")
    
    # ドキュメントパスを取得
    document_name = event_data.get("name", "")
    print(f"Event triggered for document: {document_name}")
    
    # パスから情報を抽出（例: projects/{project}/databases/{database}/documents/media_uploads/{docId}）
    if "/media_uploads/" not in document_name:
        print(f"Skipping document not in media_uploads collection: {document_name}")
        return
    
    # ドキュメントIDを抽出
    doc_id = document_name.split("/media_uploads/")[-1]
    
    print(f"Function triggered for media_uploads document: {doc_id}")
    
    # oldValueがある場合は更新なのでスキップ（新規作成のみ処理）
    if "oldValue" in event_data and event_data["oldValue"]:
        print("Skipping update event (only processing create events)")
        return
    
    # valueフィールドからドキュメントデータを取得
    value = event_data.get("value", {})
    if not value:
        print("No value in event data")
        return
        
    fields = value.get("fields", {})
    
    # 必要なフィールドを抽出
    media_uri = fields.get("media_uri", {}).get("stringValue", "")
    user_id = fields.get("user_id", {}).get("stringValue", "")
    child_id = fields.get("child_id", {}).get("stringValue", "")
    processing_status = fields.get("processing_status", {}).get("stringValue", "pending")
    
    # 既に処理済みまたは処理中の場合はスキップ
    if processing_status in ["processing", "completed"]:
        print(f"Skipping document with status: {processing_status}")
        return
    
    if not media_uri:
        print("No media_uri found in document")
        return
    
    print(f"Processing media: {media_uri}")
    print(f"User: {user_id}, Child: {child_id}")
    
    # Firestoreクライアント
    db = firestore.Client(project=PROJECT_ID, database="database")
    
    try:
        # 処理ステータスを更新
        db.collection('media_uploads').document(doc_id).update({
            'processing_status': 'processing',
            'updated_at': firestore.SERVER_TIMESTAMP
        })
        
        # メディア分析を実行
        result = process_media_for_cloud_function(
            media_uri=media_uri,
            user_id=user_id,
            child_id=child_id
        )
        
        if result.get("status") == "success":
            episode_id = result.get("episode_id")
            indexed = result.get("indexed", False)
            
            # 処理完了を記録
            db.collection('media_uploads').document(doc_id).update({
                'processing_status': 'completed',
                'processed_at': firestore.SERVER_TIMESTAMP,
                'episode_id': episode_id,
                'updated_at': firestore.SERVER_TIMESTAMP
            })
            
            # 処理ログを記録
            db.collection('processing_logs').add({
                'media_upload_id': doc_id,
                'episode_id': episode_id,
                'event_type': 'media_analysis',
                'status': 'success',
                'timestamp': firestore.SERVER_TIMESTAMP,
                'details': {
                    'user_id': user_id,
                    'child_id': child_id,
                    'media_uri': media_uri,
                    'indexed': indexed
                }
            })
            
            print(f"Successfully processed. Episode ID: {episode_id}")
            
        else:
            # エラーの場合
            error_message = result.get("error_message", "Unknown error")
            
            # エラー状態を記録
            db.collection('media_uploads').document(doc_id).update({
                'processing_status': 'failed',
                'processing_error': error_message,
                'updated_at': firestore.SERVER_TIMESTAMP
            })
            
            # エラーログを記録
            db.collection('processing_logs').add({
                'media_upload_id': doc_id,
                'event_type': 'media_analysis',
                'status': 'error',
                'error': error_message,
                'timestamp': firestore.SERVER_TIMESTAMP,
                'details': {
                    'user_id': user_id,
                    'child_id': child_id,
                    'media_uri': media_uri
                }
            })
            
            print(f"Processing failed: {error_message}")
            
    except Exception as e:
        error_message = str(e)
        print(f"Error processing media: {error_message}")
        
        # エラー状態を記録
        try:
            db.collection('media_uploads').document(doc_id).update({
                'processing_status': 'failed',
                'processing_error': error_message,
                'updated_at': firestore.SERVER_TIMESTAMP
            })
        except:
            pass