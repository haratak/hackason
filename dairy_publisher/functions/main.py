"""
Firebase Cloud Functions エントリーポイント
メディア処理とノートブック生成の両方の機能を提供
"""

# メディア処理関数をインポート（もし存在する場合）
# from sample_funcsion import process_media_upload_firestore, process_media_upload_http

# ノートブック生成関数をインポート
from notebook_functions import generate_notebook_http, generate_weekly_notebooks