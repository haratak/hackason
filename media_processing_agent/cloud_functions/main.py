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
        child_age_months = request_json.get('child_age_months')  # None if not provided
        
        if not media_uri:
            return {'error': 'media_uri is required'}, 400
            
        print(f"Processing media: {media_uri}")
        print(f"User: {user_id}, Child: {child_id}")
        
        # Firestoreクライアント
        db = firestore.Client(project=PROJECT_ID)
        
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
            child_id=child_id,
            child_age_months=child_age_months
        )
        
        if result.get("status") == "success":
            media_id = result.get("media_id")
            emotional_title = result.get("emotional_title", "")
            episode_count = result.get("episode_count", 0)
            indexed_count = result.get("indexed_count", 0)
            perspectives = result.get("perspectives", [])
            
            # ドキュメントIDがある場合は処理完了を記録
            if doc_id:
                db.collection('media_uploads').document(doc_id).update({
                    'processing_status': 'completed',
                    'processed_at': firestore.SERVER_TIMESTAMP,
                    'media_id': media_id,
                    'emotional_title': emotional_title,
                    'episode_count': episode_count,
                    'updated_at': firestore.SERVER_TIMESTAMP
                })
            
            # 処理ログを記録
            db.collection('processing_logs').add({
                'media_upload_id': doc_id,
                'media_id': media_id,
                'event_type': 'media_analysis',
                'status': 'success',
                'timestamp': firestore.SERVER_TIMESTAMP,
                'details': {
                    'user_id': user_id,
                    'child_id': child_id,
                    'child_age_months': child_age_months,
                    'media_uri': media_uri,
                    'episode_count': episode_count,
                    'indexed_count': indexed_count,
                    'perspectives': perspectives
                }
            })
            
            return {
                'status': 'success',
                'media_id': media_id,
                'emotional_title': emotional_title,
                'episode_count': episode_count,
                'indexed_count': indexed_count,
                'perspectives': perspectives
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


from cloudevents.http import from_http
from flask import Request
from google.events.cloud import firestore as firestore_events


@functions_framework.cloud_event
def process_media_upload_firestore(cloud_event):
    """Firestoreトリガーでメディア処理を実行"""
    # Firestoreイベントをパース
    firestore_payload = firestore_events.DocumentEventData()
    firestore_payload._pb.ParseFromString(cloud_event.data)
    
    # ドキュメントパスから情報を抽出
    document_name = firestore_payload.value.name
    print(f"Event triggered for document: {document_name}")
    
    # パスから情報を抽出（例: projects/{project}/databases/{database}/documents/media_uploads/{docId}）
    if "/media_uploads/" not in document_name:
        print(f"Skipping document not in media_uploads collection: {document_name}")
        return
    
    # ドキュメントIDを抽出
    doc_id = document_name.split("/media_uploads/")[-1]
    print(f"Function triggered for media_uploads document: {doc_id}")
    
    # oldValueがある場合は更新なのでスキップ（新規作成のみ処理）
    if firestore_payload.old_value:
        print("Skipping update event (only processing create events)")
        return
    
    # 新しいドキュメントのデータを取得
    if not firestore_payload.value:
        print("No document data found")
        return
    
    # ドキュメントフィールドを辞書形式に変換
    fields = {}
    for field_name, field_value in firestore_payload.value.fields.items():
        if hasattr(field_value, 'string_value'):
            fields[field_name] = field_value.string_value
        elif hasattr(field_value, 'integer_value'):
            fields[field_name] = field_value.integer_value
        elif hasattr(field_value, 'double_value'):
            fields[field_name] = field_value.double_value
        elif hasattr(field_value, 'boolean_value'):
            fields[field_name] = field_value.boolean_value
    
    # 必要なフィールドを抽出
    media_uri = fields.get("media_uri", "")
    user_id = fields.get("user_id", "")
    child_id = fields.get("child_id", "")
    child_age_months = fields.get("child_age_months")  # None if not provided
    processing_status = fields.get("processing_status", "pending")
    
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
    db = firestore.Client(project=PROJECT_ID)
    
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
            child_id=child_id,
            child_age_months=child_age_months
        )
        
        if result.get("status") == "success":
            media_id = result.get("media_id")
            emotional_title = result.get("emotional_title", "")
            episode_count = result.get("episode_count", 0)
            indexed_count = result.get("indexed_count", 0)
            perspectives = result.get("perspectives", [])
            
            # 処理完了を記録
            db.collection('media_uploads').document(doc_id).update({
                'processing_status': 'completed',
                'processed_at': firestore.SERVER_TIMESTAMP,
                'media_id': media_id,
                'emotional_title': emotional_title,
                'episode_count': episode_count,
                'updated_at': firestore.SERVER_TIMESTAMP
            })
            
            # 処理ログを記録
            db.collection('processing_logs').add({
                'media_upload_id': doc_id,
                'media_id': media_id,
                'event_type': 'media_analysis',
                'status': 'success',
                'timestamp': firestore.SERVER_TIMESTAMP,
                'details': {
                    'user_id': user_id,
                    'child_id': child_id,
                    'child_age_months': child_age_months,
                    'media_uri': media_uri,
                    'episode_count': episode_count,
                    'indexed_count': indexed_count,
                    'perspectives': perspectives
                }
            })
            
            print(f"Successfully processed. Media ID: {media_id}")
            
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