"""
Firebase Cloud Functions for Media Processing
第2世代のFirestoreトリガーとHTTPトリガーに対応
"""
import os
from firebase_functions import firestore_fn, https_fn, options
from firebase_functions.firestore_fn import (
    on_document_created,
    Event,
    DocumentSnapshot,
)
from firebase_admin import initialize_app, firestore
from google.cloud import firestore as firestore_client
from agent import process_media_for_cloud_function

# Firebase Admin SDKの初期化
initialize_app()

# Firestoreクライアント
db = firestore.client()

# 環境変数
PROJECT_ID = os.environ.get('GCLOUD_PROJECT', 'hackason-464007')


@on_document_created(
    document="media_uploads/{docId}",
    timeout_sec=540,  # 9分のタイムアウト
    memory=options.MemoryOption.GB_2,  # 2GBのメモリ
)
def process_media_upload_firestore(event: Event[DocumentSnapshot]) -> None:
    """Firestoreトリガーでメディア処理を実行"""
    # ドキュメントデータを取得
    doc_data = event.data.to_dict() if event.data else {}
    doc_id = event.params["docId"]
    
    print(f"Function triggered for media_uploads document: {doc_id}")
    
    # 必要なフィールドを抽出
    media_uri = doc_data.get("media_uri", "")
    user_id = doc_data.get("user_id", "")
    child_id = doc_data.get("child_id", "")
    processing_status = doc_data.get("processing_status", "pending")
    captured_at = doc_data.get("captured_at", None)
    
    # 既に処理済みまたは処理中の場合はスキップ
    if processing_status in ["processing", "completed"]:
        print(f"Skipping document with status: {processing_status}")
        return
    
    if not media_uri:
        print("No media_uri found in document")
        return
    
    print(f"Processing media: {media_uri}")
    print(f"User: {user_id}, Child: {child_id}")
    
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
            media_upload_id=doc_id,
            captured_at=captured_at
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


@https_fn.on_request(
    timeout_sec=540,  # 9分のタイムアウト
    memory=options.MemoryOption.GB_2,  # 2GBのメモリ
    cors=options.CorsOptions(
        cors_origins="*",
        cors_methods=["POST"],
    ),
)
def process_media_upload_http(req: https_fn.Request) -> https_fn.Response:
    """HTTPトリガーでメディア処理を実行"""
    try:
        # リクエストボディを取得
        request_json = req.get_json()
        
        if not request_json:
            return https_fn.Response(
                {"error": "Request body is required"},
                status=400
            )
            
        # 必要なパラメータを取得
        doc_id = request_json.get('doc_id')
        media_uri = request_json.get('media_uri')
        user_id = request_json.get('user_id', '')
        child_id = request_json.get('child_id', '')
        captured_at = request_json.get('captured_at', None)
        
        if not media_uri:
            return https_fn.Response(
                {"error": "media_uri is required"},
                status=400
            )
            
        print(f"Processing media: {media_uri}")
        print(f"User: {user_id}, Child: {child_id}")
        
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
            media_upload_id=doc_id,
            captured_at=captured_at
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
            
            return https_fn.Response({
                'status': 'success',
                'episode_id': episode_id,
                'indexed': indexed
            })
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
            
            return https_fn.Response(
                {
                    'status': 'error',
                    'error': error_message
                },
                status=500
            )
            
    except Exception as e:
        print(f"Error processing media: {str(e)}")
        return https_fn.Response(
            {
                'status': 'error',
                'error': str(e)
            },
            status=500
        )