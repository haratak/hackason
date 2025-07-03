"""
Cloud Function to handle video uploads and generate thumbnails
"""
from firebase_functions import storage_fn, options
from firebase_admin import initialize_app
from google.cloud import storage as gcs
import logging
import os

# ローカルの関数をインポート
from video_thumbnail import generate_video_thumbnail, get_thumbnail_path, is_video_file

# Firebase Admin SDKの初期化
initialize_app()

logger = logging.getLogger(__name__)

@storage_fn.on_object_finalized(
    bucket="hackason-464007.firebasestorage.app",
    timeout_sec=300,  # 5分のタイムアウト
    memory=options.MemoryOption.GB_1
)
def generate_thumbnail_on_upload(event: storage_fn.CloudEvent[storage_fn.StorageObjectData]) -> None:
    """
    動画ファイルがアップロードされた時に自動的にサムネイルを生成
    """
    try:
        # イベントデータを取得
        file_path = event.data.name
        bucket_name = event.data.bucket
        
        logger.info(f"File uploaded: gs://{bucket_name}/{file_path}")
        
        # 動画ファイルかチェック
        if not is_video_file(file_path):
            logger.info(f"Not a video file, skipping: {file_path}")
            return
        
        # サムネイルのパスを生成
        thumbnail_path = get_thumbnail_path(file_path)
        
        # サムネイルが既に存在するかチェック
        storage_client = gcs.Client()
        bucket = storage_client.bucket(bucket_name)
        thumbnail_blob = bucket.blob(thumbnail_path)
        
        if thumbnail_blob.exists():
            logger.info(f"Thumbnail already exists: gs://{bucket_name}/{thumbnail_path}")
            return
        
        # 動画のgs:// URLを構築
        video_url = f"gs://{bucket_name}/{file_path}"
        
        # サムネイルを生成（自動的に最適なフレームを選択）
        logger.info(f"Generating thumbnail for video: {video_url}")
        thumbnail_url = generate_video_thumbnail(
            video_url=video_url,
            bucket_name=bucket_name,
            output_path=thumbnail_path,
            time_offset=None  # 自動選択モード
        )
        
        if thumbnail_url:
            logger.info(f"Successfully generated thumbnail: {thumbnail_url}")
        else:
            logger.error(f"Failed to generate thumbnail for: {video_url}")
            
    except Exception as e:
        logger.error(f"Error in generate_thumbnail_on_upload: {str(e)}")
        # エラーをre-raiseしない（他の処理をブロックしないため）


@storage_fn.on_object_deleted(
    bucket="hackason-464007.firebasestorage.app",
    timeout_sec=60
)
def delete_thumbnail_on_video_delete(event: storage_fn.CloudEvent[storage_fn.StorageObjectData]) -> None:
    """
    動画ファイルが削除された時に対応するサムネイルも削除
    """
    try:
        # イベントデータを取得
        file_path = event.data.name
        bucket_name = event.data.bucket
        
        # 動画ファイルかチェック
        if not is_video_file(file_path):
            return
        
        # サムネイルのパスを生成
        thumbnail_path = get_thumbnail_path(file_path)
        
        # サムネイルを削除
        storage_client = gcs.Client()
        bucket = storage_client.bucket(bucket_name)
        thumbnail_blob = bucket.blob(thumbnail_path)
        
        if thumbnail_blob.exists():
            thumbnail_blob.delete()
            logger.info(f"Deleted thumbnail: gs://{bucket_name}/{thumbnail_path}")
        
    except Exception as e:
        logger.error(f"Error in delete_thumbnail_on_video_delete: {str(e)}")