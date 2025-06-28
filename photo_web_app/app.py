import os
import json
import pickle
import base64
from datetime import datetime
from flask import Flask, render_template, redirect, url_for, session, request, jsonify
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from google.cloud import aiplatform
import numpy as np
from dotenv import load_dotenv
import requests
from PIL import Image
from io import BytesIO
import tempfile
import uuid

# 環境変数を読み込む
load_dotenv()

# 開発環境でHTTPSチェックを無効化
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

# Google Cloud認証情報の設定
# ADCが設定されていない場合は、gcloud auth application-default loginを実行してください
if not os.getenv('GOOGLE_APPLICATION_CREDENTIALS'):
    print("Warning: GOOGLE_APPLICATION_CREDENTIALS not set. Using Application Default Credentials.")

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret-key")

# Google OAuth2の設定
SCOPES = [
    "https://www.googleapis.com/auth/photoslibrary.readonly",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "openid"
]
CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:5000/callback")

# GCPプロジェクトの設定
PROJECT_ID = os.getenv("GCP_PROJECT_ID")
LOCATION = os.getenv("GCP_LOCATION", "us-central1")

# quota projectを設定
os.environ["GOOGLE_CLOUD_QUOTA_PROJECT"] = PROJECT_ID

# 顔認識のしきい値
SIMILARITY_THRESHOLD = 0.75

# 埋め込みベクトルを一時的に保存する辞書（本番環境では Redis や DB を使用）
EMBEDDING_CACHE = {}


# OAuth2フローの設定
def get_flow():
    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [REDIRECT_URI],
            }
        },
        scopes=SCOPES,
    )
    flow.redirect_uri = REDIRECT_URI
    return flow


@app.route("/")
def index():
    """トップページ"""
    return render_template("index.html", authenticated="credentials" in session)


@app.route("/login")
def login():
    """Googleログイン開始"""
    flow = get_flow()
    authorization_url, state = flow.authorization_url(
        access_type="offline", include_granted_scopes="true"
    )
    session["state"] = state
    return redirect(authorization_url)


@app.route("/callback")
def callback():
    """Google OAuth2コールバック"""
    state = session.get("state")
    flow = get_flow()
    flow.fetch_token(authorization_response=request.url)

    # 認証情報を保存
    credentials = flow.credentials
    session["credentials"] = {
        "token": credentials.token,
        "refresh_token": credentials.refresh_token,
        "token_uri": credentials.token_uri,
        "client_id": credentials.client_id,
        "client_secret": credentials.client_secret,
        "scopes": credentials.scopes,
    }

    return redirect(url_for("upload"))


@app.route("/upload")
def upload():
    """子供の写真アップロードページ"""
    if "credentials" not in session:
        return redirect(url_for("login"))
    return render_template("upload.html")


@app.route("/upload_photos", methods=["POST"])
def upload_photos():
    """子供の写真をアップロードして顔特徴を抽出"""
    if "credentials" not in session:
        return jsonify({"error": "Not authenticated"}), 401

    uploaded_files = request.files.getlist("photos")
    face_embeddings = []

    # Vertex AI初期化
    aiplatform.init(project=PROJECT_ID, location=LOCATION)

    for file in uploaded_files:
        if file and file.filename:
            # 画像を読み込む
            image_bytes = file.read()

            # Vertex AIで顔特徴を抽出
            embeddings = get_face_embedding(base64.b64encode(image_bytes).decode())
            if embeddings:
                face_embeddings.extend(embeddings)

    if face_embeddings:
        # 平均的な顔特徴ベクトルを計算
        avg_embedding = np.mean(face_embeddings, axis=0)
        session["child_face_embedding"] = avg_embedding.tolist()
        return jsonify(
            {
                "success": True,
                "message": f"{len(uploaded_files)}枚の写真から顔特徴を抽出しました",
            }
        )
    else:
        return jsonify({"error": "顔を検出できませんでした"}), 400


@app.route("/scan_photos")
def scan_photos():
    """Google Photosから子供の写真を検索"""
    if "credentials" not in session:
        return redirect(url_for("login"))

    if "child_face_embedding" not in session:
        return redirect(url_for("upload"))

    return render_template("scan.html")


@app.route("/api/scan_photos", methods=["POST"])
def api_scan_photos():
    """Google Photosをスキャンして子供の写真を特定"""
    if "credentials" not in session:
        return jsonify({"error": "Not authenticated"}), 401

    if "child_face_embedding" not in session:
        return jsonify({"error": "No child face data"}), 400

    # Google Photos APIのクライアントを作成
    creds = Credentials(**session["credentials"])
    service = build("photoslibrary", "v1", credentials=creds, static_discovery=False)

    # お手本の顔特徴ベクトル
    child_embedding = np.array(session["child_face_embedding"])

    matched_photos = []
    page_token = None

    # Vertex AI初期化
    aiplatform.init(project=PROJECT_ID, location=LOCATION)

    try:
        while len(matched_photos) < 100:  # 最大100枚まで
            # Google Photosから写真を取得
            if page_token:
                response = (
                    service.mediaItems()
                    .search(
                        body={
                            "pageSize": 50,
                            "pageToken": page_token,
                            "filters": {"mediaTypeFilter": {"mediaTypes": ["PHOTO"]}},
                        }
                    )
                    .execute()
                )
            else:
                response = (
                    service.mediaItems()
                    .search(
                        body={
                            "pageSize": 50,
                            "filters": {"mediaTypeFilter": {"mediaTypes": ["PHOTO"]}},
                        }
                    )
                    .execute()
                )

            media_items = response.get("mediaItems", [])
            if not media_items:
                break

            # 各写真をチェック
            for item in media_items:
                # 写真をダウンロード
                image_url = f"{item['baseUrl']}=d"
                image_response = requests.get(image_url)

                if image_response.status_code == 200:
                    # 顔特徴を抽出
                    image_base64 = base64.b64encode(image_response.content).decode()
                    face_vectors = get_face_embedding(image_base64)

                    if face_vectors:
                        # 類似度チェック
                        for face_vector in face_vectors:
                            similarity = calculate_cosine_similarity(
                                child_embedding, face_vector
                            )
                            if similarity > SIMILARITY_THRESHOLD:
                                matched_photos.append(
                                    {
                                        "id": item["id"],
                                        "filename": item.get("filename", "Unknown"),
                                        "creationTime": item.get(
                                            "mediaMetadata", {}
                                        ).get("creationTime"),
                                        "baseUrl": item["baseUrl"],
                                        "similarity": float(similarity),
                                    }
                                )
                                break

            page_token = response.get("nextPageToken")
            if not page_token:
                break

        return jsonify(
            {
                "success": True,
                "matched_photos": matched_photos,
                "total": len(matched_photos),
            }
        )

    except Exception as e:
        return jsonify({"error": str(e)}), 500


def get_face_embedding(image_base64):
    """Vertex AIを使って画像から顔の埋め込みベクトルを取得"""
    try:
        from google.cloud import aiplatform_v1
        
        # クライアントを作成
        client = aiplatform_v1.PredictionServiceClient(
            client_options={"api_endpoint": f"{LOCATION}-aiplatform.googleapis.com"}
        )
        
        # エンドポイント名を正しい形式で構築
        endpoint = f"projects/{PROJECT_ID}/locations/{LOCATION}/publishers/google/models/multimodalembedding@001"
        
        print(f"Using endpoint: {endpoint}")

        # リクエストを作成
        instances = [{"image": {"bytesBase64Encoded": image_base64}}]
        
        # 予測を実行
        response = client.predict(
            endpoint=endpoint,
            instances=instances
        )

        print(f"Response: {response}")

        # 顔の埋め込みを抽出
        face_embeddings = []
        for prediction in response.predictions:
            # マルチモーダル埋め込みレスポンスから埋め込みベクトルを取得
            if "imageEmbedding" in prediction:
                embedding = prediction["imageEmbedding"]
                face_embeddings.append(np.array(embedding))
                print(f"Found embedding with {len(embedding)} dimensions")
            elif "embedding" in prediction:
                embedding = prediction["embedding"]
                face_embeddings.append(np.array(embedding))
                print(f"Found embedding with {len(embedding)} dimensions")

        print(f"Found {len(face_embeddings)} embeddings total")
        return face_embeddings if face_embeddings else None

    except Exception as e:
        print(f"Vertex AI APIエラー: {e}")
        import traceback
        traceback.print_exc()
        return None


def calculate_cosine_similarity(vec1, vec2):
    """2つのベクトル間のコサイン類似度を計算"""
    return np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2))


@app.route("/logout")
def logout():
    """ログアウト"""
    session.clear()
    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=8080)
