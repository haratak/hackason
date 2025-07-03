"""
Video thumbnail generation module for Cloud Functions
"""
import os
import tempfile
import logging
from typing import Optional, Tuple
from google.cloud import storage
from PIL import Image
import cv2
import numpy as np
from datetime import datetime
import uuid

logger = logging.getLogger(__name__)


def is_video_file(file_path: str) -> bool:
    """
    ファイルパスが動画ファイルかどうかを判定
    
    Args:
        file_path: チェックするファイルパス
        
    Returns:
        動画ファイルの場合True
    """
    if not file_path:
        return False
    
    video_extensions = ['.mov', '.mp4', '.avi', '.wmv', '.flv', '.webm', '.m4v', '.mkv']
    file_path_lower = file_path.lower()
    return any(ext in file_path_lower for ext in video_extensions)

def calculate_frame_quality(frame: np.ndarray) -> float:
    """
    フレームの品質スコアを計算
    
    Args:
        frame: OpenCVのフレーム（BGR形式）
        
    Returns:
        品質スコア（0.0〜1.0）
    """
    score = 0.0
    
    # 1. 明るさチェック（暗すぎず明るすぎない）
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    brightness = np.mean(gray)
    # 理想的な明るさは128前後
    brightness_score = 1.0 - abs(brightness - 128) / 128
    score += brightness_score * 0.3
    
    # 2. コントラストチェック
    contrast = np.std(gray)
    # コントラストは高い方が良い（最大255）
    contrast_score = min(contrast / 80, 1.0)
    score += contrast_score * 0.3
    
    # 3. シャープネス（ブレの検出）
    laplacian = cv2.Laplacian(gray, cv2.CV_64F)
    sharpness = np.var(laplacian)
    # シャープネススコア（経験的な値）
    sharpness_score = min(sharpness / 1000, 1.0)
    score += sharpness_score * 0.2
    
    # 4. 顔検出ボーナス
    face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
    faces = face_cascade.detectMultiScale(gray, 1.1, 4)
    if len(faces) > 0:
        score += 0.2
    
    return min(score, 1.0)


def extract_frame_at_timestamp(video_path: str, timestamp: float) -> Tuple[Optional[np.ndarray], dict]:
    """
    指定されたタイムスタンプのフレームを抽出
    
    Returns:
        (frame, metadata) のタプル
    """
    try:
        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = total_frames / fps if fps > 0 else 0
        
        # タイムスタンプが動画の長さを超えている場合は調整
        if timestamp > duration:
            timestamp = duration * 0.5
        
        frame_number = int(fps * timestamp)
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
        
        ret, frame = cap.read()
        cap.release()
        
        if ret:
            metadata = {
                'timestamp': timestamp,
                'frame_number': frame_number,
                'total_frames': total_frames,
                'duration': duration
            }
            return frame, metadata
        
        return None, {}
        
    except Exception as e:
        logger.error(f"Error extracting frame: {str(e)}")
        return None, {}


def generate_video_thumbnail(
    video_url: str,
    bucket_name: str,
    output_path: str,
    time_offset: float = None
) -> Optional[str]:
    """
    動画ファイルからサムネイル画像を生成してCloud Storageに保存
    複数のタイムスタンプから最適なフレームを選択
    
    Args:
        video_url: 動画ファイルのURL（gs://またはhttps://）
        bucket_name: 保存先のバケット名
        output_path: 保存先のパス（例: thumbnails/xxx.jpg）
        time_offset: サムネイルを生成する時間位置（秒）、Noneの場合は自動選択
        
    Returns:
        生成されたサムネイルのgs:// URL、失敗時はNone
    """
    try:
        # 一時ファイルとして動画をダウンロード
        with tempfile.NamedTemporaryFile(suffix='.mov', delete=False) as tmp_video:
            # gs:// URLをHTTPS URLに変換
            if video_url.startswith('gs://'):
                https_url = convert_gs_to_https(video_url)
            else:
                https_url = video_url
            
            # 動画をダウンロード
            import urllib.request
            urllib.request.urlretrieve(https_url, tmp_video.name)
            
            # 動画の長さを取得
            cap = cv2.VideoCapture(tmp_video.name)
            fps = cap.get(cv2.CAP_PROP_FPS)
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            duration = total_frames / fps if fps > 0 else 0
            cap.release()
            
            if duration == 0:
                logger.error(f"Failed to get video duration: {video_url}")
                return None
            
            # time_offsetが指定されていない場合は複数の候補から選択
            if time_offset is None:
                # 動画の長さに応じて候補タイムスタンプを生成
                if duration <= 2:
                    # 短い動画の場合
                    timestamps = [0.5, 1.0]
                elif duration <= 5:
                    # 5秒以下の動画
                    timestamps = [0.5, 1.0, 2.0, duration * 0.7]
                else:
                    # 長い動画の場合は20%, 30%, 40%, 50%, 60%の位置をサンプリング
                    timestamps = [
                        duration * 0.2,
                        duration * 0.3,
                        duration * 0.4,
                        duration * 0.5,
                        duration * 0.6
                    ]
                
                # 各タイムスタンプでフレームを抽出して品質を評価
                best_frame = None
                best_score = -1
                best_timestamp = timestamps[0]
                
                for ts in timestamps:
                    frame, metadata = extract_frame_at_timestamp(tmp_video.name, ts)
                    if frame is not None:
                        score = calculate_frame_quality(frame)
                        logger.info(f"Frame at {ts:.1f}s: quality score = {score:.3f}")
                        
                        if score > best_score:
                            best_score = score
                            best_frame = frame
                            best_timestamp = ts
                
                if best_frame is None:
                    logger.error(f"Failed to extract any frame from video: {video_url}")
                    return None
                
                frame = best_frame
                logger.info(f"Selected best frame at {best_timestamp:.1f}s with score {best_score:.3f}")
                
            else:
                # time_offsetが指定されている場合は単一フレーム抽出
                frame, _ = extract_frame_at_timestamp(tmp_video.name, time_offset)
                if frame is None:
                    logger.error(f"Failed to extract frame at {time_offset}s from video: {video_url}")
                    return None
            
            # BGRからRGBに変換
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            # PILイメージに変換
            image = Image.fromarray(frame_rgb)
            
            # サムネイルサイズにリサイズ（アスペクト比を維持）
            max_size = (800, 600)
            image.thumbnail(max_size, Image.Resampling.LANCZOS)
            
            # 一時ファイルとして保存
            with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp_thumb:
                image.save(tmp_thumb.name, 'JPEG', quality=85, optimize=True)
                
                # Cloud Storageにアップロード
                client = storage.Client()
                bucket = client.bucket(bucket_name)
                blob = bucket.blob(output_path)
                
                blob.upload_from_filename(tmp_thumb.name)
                blob.make_public()  # 公開アクセスを許可
                
                # 一時ファイルを削除
                os.unlink(tmp_thumb.name)
            
            # 一時動画ファイルを削除
            os.unlink(tmp_video.name)
            
            # gs:// URLを返す
            return f"gs://{bucket_name}/{output_path}"
            
    except Exception as e:
        logger.error(f"Error generating video thumbnail: {str(e)}")
        return None


def convert_gs_to_https(gs_url: str) -> str:
    """gs:// URLをHTTPS URLに変換"""
    if not gs_url.startswith('gs://'):
        return gs_url
    
    # gs://bucket-name/path/to/file の形式をパース
    parts = gs_url[5:].split('/', 1)
    if len(parts) != 2:
        return gs_url
    
    bucket_name, object_path = parts
    return f"https://storage.googleapis.com/{bucket_name}/{object_path}"


def get_thumbnail_path(video_path: str) -> str:
    """
    動画ファイルパスからサムネイルパスを生成
    
    例: videos/2025/01/video.mov -> thumbnails/2025/01/video_thumb.jpg
    """
    # パスを分解
    dir_path = os.path.dirname(video_path)
    filename = os.path.basename(video_path)
    name, _ = os.path.splitext(filename)
    
    # thumbnailsディレクトリに変更
    if dir_path.startswith('videos/'):
        thumb_dir = dir_path.replace('videos/', 'thumbnails/', 1)
    else:
        thumb_dir = f"thumbnails/{dir_path}" if dir_path else "thumbnails"
    
    # サムネイルファイル名
    thumb_filename = f"{name}_thumb.jpg"
    
    return os.path.join(thumb_dir, thumb_filename).replace('\\', '/')


def extract_video_metadata(video_path: str) -> dict:
    """動画のメタデータを抽出"""
    try:
        cap = cv2.VideoCapture(video_path)
        
        metadata = {
            'width': int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
            'height': int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
            'fps': cap.get(cv2.CAP_PROP_FPS),
            'frame_count': int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
            'duration': cap.get(cv2.CAP_PROP_FRAME_COUNT) / cap.get(cv2.CAP_PROP_FPS)
        }
        
        cap.release()
        return metadata
        
    except Exception as e:
        logger.error(f"Error extracting video metadata: {str(e)}")
        return {}