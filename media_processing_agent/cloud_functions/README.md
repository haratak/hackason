# Media Processing Agent - Cloud Functions

このディレクトリには、Cloud Functionsにデプロイするためのファイルが含まれています。

## アーキテクチャ

```
クライアントアプリ → Cloud Storage (アップロード) 
      ↓
クライアントアプリ → Firestore (メタデータ保存) → Firestore Trigger Function → 分析処理
```

1. **クライアントアプリケーション**
   - Cloud Storageにメディアファイルをアップロード
   - Firestoreの`media_uploads`コレクションにメタデータを保存
   - user_id、child_id、その他の情報を含む

2. **Firestore Trigger Function** (`firestore_trigger.py`)
   - Firestoreの`media_uploads`コレクションへの新規ドキュメント作成をトリガー
   - `media_analyzer.py`を使用してメディアを分析
   - エピソードを生成し、ベクトル検索用にインデックス化

## ファイル構成

- `firestore_trigger.py` - Firestore ドキュメント作成トリガー
- `media_analyzer.py` - メディア分析のコア実装（agent.pyと共有）
- `requirements.txt` - Python依存関係
- `.gcloudignore` - デプロイ時に除外するファイル
- `cloudbuild.yaml` - Cloud Build設定（CI/CD用）

## デプロイ方法

プロジェクトルートから以下のコマンドを実行：

```bash
./deploy.sh
```

## 必要な環境変数

- `GOOGLE_CLOUD_PROJECT` - GCPプロジェクトID
- `GOOGLE_CLOUD_LOCATION` - リージョン（デフォルト: us-central1）
- `VERTEX_AI_INDEX_ID` - Vertex AIのインデックスID
- `VERTEX_AI_INDEX_ENDPOINT_ID` - Vertex AIのインデックスエンドポイントID

## データフロー

1. クライアントアプリケーション
   - Cloud Storageにメディアファイルをアップロード
   - Firestoreの`media_uploads`コレクションにメタデータを保存
   - user_id、child_id、その他の必要な情報を含む

2. Firestore Trigger Functionが起動
   - `media_uploads`コレクションの新規ドキュメントを検知
   - メディアファイルを分析
   - エピソードを生成
   - `episodes`コレクションに保存
   - ベクトル検索用にインデックス化

## Firestoreコレクション

### media_uploads
```json
{
  "user_id": "string",
  "child_id": "string",
  "media_uri": "gs://...",
  "media_type": "image|video",
  "file_size": 12345,
  "processing_status": "pending|processing|completed|failed",
  "episode_id": "string (after processing)",
  "uploaded_at": "timestamp",
  "processed_at": "timestamp"
}
```

### episodes
```json
{
  "user_id": "string",
  "child_id": "string",
  "title": "string",
  "content": "string",
  "media_source_uri": "gs://...",
  "emotion": "string",
  "activities": ["string"],
  "development_milestones": ["string"],
  "vector_tags": ["string"],
  "created_at": "timestamp"
}
```

### processing_logs
```json
{
  "media_upload_id": "string",
  "episode_id": "string",
  "event_type": "storage_upload|media_analysis",
  "status": "success|error",
  "error": "string (if error)",
  "timestamp": "timestamp",
  "details": {}
}
```