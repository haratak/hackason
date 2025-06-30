"""
Cloud Function for Media Processing
HTTPトリガーとFirestoreトリガーの両方に対応
"""
from firebase_functions import https_fn
from firebase_functions.firestore_fn import (
    on_document_created,
    Event,
    DocumentSnapshot,
)
from firebase_admin import initialize_app, firestore
import os
import sys
import json
from datetime import datetime

# Firebase Admin SDKの初期化
initialize_app()

# 現在のディレクトリをパスに追加（agent.pyを使うため）
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agent import process_media_for_cloud_function

# 環境変数
PROJECT_ID = os.environ.get('GOOGLE_CLOUD_PROJECT', 'hackason-464007')


@https_fn.on_request(timeout_sec=540, memory=2048)
def process_media_upload(req: https_fn.Request) -> https_fn.Response:
    """HTTPトリガーでメディア処理を実行"""
    try:
        # リクエストボディを取得
        request_json = req.get_json(silent=True)
        
        if not request_json:
            return https_fn.Response({'error': 'Request body is required'}, status=400)
            
        # 必要なパラメータを取得
        doc_id = request_json.get('doc_id')
        media_uri = request_json.get('media_uri')
        user_id = request_json.get('user_id', '')
        child_id = request_json.get('child_id', '')
        child_age_months = request_json.get('child_age_months')  # None if not provided
        captured_at = request_json.get('captured_at')  # None if not provided
        
        if not media_uri:
            return https_fn.Response({'error': 'media_uri is required'}, status=400)
            
        print(f"Processing media: {media_uri}")
        print(f"User: {user_id}, Child: {child_id}")
        
        # Firestoreクライアント
        db = firestore.client()
        
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
            child_age_months=child_age_months,
            captured_at=captured_at
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
            
            return https_fn.Response({
                'status': 'success',
                'media_id': media_id,
                'emotional_title': emotional_title,
                'episode_count': episode_count,
                'indexed_count': indexed_count,
                'perspectives': perspectives
            }, status=200)
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
            
            return https_fn.Response({
                'status': 'error',
                'error': error_message
            }, status=500)
            
    except Exception as e:
        print(f"Error processing media: {str(e)}")
        return https_fn.Response({
            'status': 'error',
            'error': str(e)
        }, status=500)


@on_document_created(
    document="media_uploads/{docId}",
    timeout_sec=540,
    memory=2048
)
def process_media_upload_firestore(event: Event[DocumentSnapshot]) -> None:
    """Firestoreトリガーでメディア処理を実行"""
    # ドキュメントのデータとIDを取得
    doc_id = event.params["docId"]
    doc_data = event.data.to_dict() if event.data else None
    
    print(f"Function triggered for media_uploads document: {doc_id}")
    
    if not doc_data:
        print("No document data found")
        return
    
    # 必要なフィールドを抽出
    media_uri = doc_data.get("media_uri", "")
    user_id = doc_data.get("user_id", "")
    child_id = doc_data.get("child_id", "")
    child_age_months = doc_data.get("child_age_months")  # None if not provided
    processing_status = doc_data.get("processing_status", "pending")
    captured_at = doc_data.get("captured_at")  # Firestore Timestamp or None
    
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
    db = firestore.client()
    
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
            child_age_months=child_age_months,
            captured_at=datetime.fromtimestamp(captured_at.timestamp()) if captured_at and hasattr(captured_at, 'timestamp') else None  # Convert Firestore Timestamp to datetime
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


@https_fn.on_request(timeout_sec=540, memory=2048)
def generate_notebook_http(req: https_fn.Request) -> https_fn.Response:
    """HTTPトリガーでノートブック生成を実行"""
    try:
        # リクエストボディを取得
        request_json = req.get_json(silent=True)
        
        if not request_json:
            return https_fn.Response({'error': 'Request body is required'}, status=400)
            
        # 必要なパラメータを取得
        child_id = request_json.get('child_id')
        start_date = request_json.get('start_date')
        end_date = request_json.get('end_date')
        child_info = request_json.get('child_info', {})
        
        if not child_id:
            return https_fn.Response({'error': 'child_id is required'}, status=400)
        if not start_date:
            return https_fn.Response({'error': 'start_date is required'}, status=400)
        if not end_date:
            return https_fn.Response({'error': 'end_date is required'}, status=400)
            
        print(f"Generating notebook for child: {child_id}")
        print(f"Date range: {start_date} to {end_date}")
        print(f"Child info: {child_info}")
        
        # Firestoreクライアント
        db = firestore.client()
        
        # ノートブック生成処理（簡単な実装）
        # 実際の実装では、指定期間のメディアデータを取得して
        # AIでノートブックコンテンツを生成する必要があります
        
        # 一時的なレスポンス（動作確認用）
        notebook_id = f"{child_id}_{start_date.replace('-', '_')}_notebook"
        
        # ノートブックを作成してFirestoreに保存
        notebook_data = {
            'id': notebook_id,
            'child_id': child_id,
            'start_date': start_date,
            'end_date': end_date,
            'title': f"週刊ノートブック ({start_date} - {end_date})",
            'topics': [
                {
                    'title': 'この週の成長記録',
                    'content': 'この期間の素敵な思い出や成長の様子をまとめました。',
                    'subtitle': '成長の記録'
                }
            ],
            'created_at': firestore.SERVER_TIMESTAMP,
            'updated_at': firestore.SERVER_TIMESTAMP
        }
        
        # Firestoreに保存
        db.collection('children').document(child_id).collection('notebooks').document(notebook_id).set(notebook_data)
        
        print(f"Successfully created notebook: {notebook_id}")
        
        return https_fn.Response({
            'status': 'success',
            'message': 'ノートブックを作成しました',
            'notebook_id': notebook_id,
            'data': notebook_data
        }, status=200)
        
    except Exception as e:
        print(f"Error generating notebook: {str(e)}")
        return https_fn.Response({
            'status': 'error',
            'message': 'ノートブック生成中にエラーが発生しました',
            'error': str(e)
        }, status=500)