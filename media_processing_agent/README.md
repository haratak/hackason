# Media Processing Agent

子供の写真や動画から思い出のエピソードを自動生成するGoogle ADKエージェントです。

## 概要

このエージェントは、メディアファイル（画像・動画）を分析し、以下の処理を行います：

1. **客観的分析**: メディアから観察できる事実を抽出
2. **ハイライト特定**: 最も印象的な瞬間を識別
3. **データ保存**: Firestoreにエピソードを保存
4. **ベクトル化**: 意味検索のためのインデックス作成

## 前提条件

### 1. Google Cloud環境
- Google Cloud Projectが作成済み
- 以下のAPIが有効化されている：
  - Vertex AI API
  - Firestore API
  - Cloud Storage API

### 2. ローカル環境
- Python 3.12以上
- [uv](https://github.com/astral-sh/uv) (Pythonパッケージ管理)
- [Google Cloud CLI](https://cloud.google.com/sdk/docs/install)

## セットアップ

### 1. Google Cloud CLIの設定

```bash
# Google Cloudにログイン
gcloud auth login

# アプリケーションのデフォルト認証を設定
gcloud auth application-default login

# プロジェクトを設定
gcloud config set project YOUR_PROJECT_ID

```
```

### 2. Python仮想環境のセットアップ

```bash
# uvで仮想環境を作成
uv venv

# 仮想環境をアクティベート
# macOS/Linux:
source .venv/bin/activate
# Windows:
# .venv\Scripts\activate

# 依存関係をインストール
uv sync
```

### 3. 環境変数の設定

`.env`ファイルを作成し、以下の環境変数を設定：

```
# Google Cloud設定
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_CLOUD_LOCATION=us-central1

# Vertex AI Vector Search設定（オプション）
VERTEX_AI_INDEX_ID=your-index-id

# 開発モード（オプション）
DEVELOPMENT_MODE=false
```

### 4. ADK CLIのインストール

```bash
# 仮想環境内でADK CLIをインストール
pip install google-genai-agent-dev-kit

# インストール確認
adk --version
```

## 使用方法

### 1. ADK Webでの実行

```bash
# 仮想環境がアクティベートされていることを確認
# (プロンプトに (.venv) が表示されているはず)

# ADK Webサーバーを起動
# 注意: 親ディレクトリから実行する必要があります
cd ..
adk web

# ブラウザで http://localhost:8080 を開く
```

### 2. エージェントの使用

ADK Web UIで：

1. **エージェントを選択**: `episode_generator_agent`を選択

2. **初期プロンプトを入力**: 
   ```
   以下の画像を分析してください：
   https://storage.googleapis.com/your-bucket/child-playing.jpg
   ```
   または動画の場合：
   ```
   この動画から子供の様子を分析してください：
   https://storage.googleapis.com/your-bucket/birthday-party.mp4
   ```

3. **実行後の流れ**:

#### ツール実行順序と出力例

**① objective_analyzer の実行**
```json
{
  "status": "success",
  "report": {
    "all_observed_actions": ["ケーキを見つめる", "手を叩く", "笑う"],
    "observed_emotions": ["喜び", "興奮", "期待"],
    "spoken_words": ["わー！", "ケーキ！"],
    "environment": "室内、誕生日パーティーの装飾あり",
    "physical_interactions": ["テーブルに手をつく", "ケーキを指差す"],
    "body_movements": ["前のめりになる", "体を揺らす"]
  }
}
```

**② highlight_identifier の実行**
```json
{
  "status": "success",
  "report": {
    "title": "初めてのバースデーケーキ",
    "summary": "誕生日パーティーで、ケーキを見て「わー！」と歓声を上げ、手を叩いて喜ぶ様子。",
    "emotion": "喜び",
    "activities": ["ケーキを見る", "手を叩く", "歓声を上げる"],
    "development_milestones": ["感情表現の発達", "言語発達"],
    "vector_tags": ["誕生日", "ケーキ", "喜び", "パーティー", "手を叩く"]
  }
}
```

**③ save_summary の実行**
- 本番モード：
```json
{
  "status": "success",
  "episode_id": "AbC123DefG456",
  "message": "Episode saved with ID: AbC123DefG456"
}
```
- 開発モード：
```
📝 [DEVELOPMENT MODE] Episode data that would be saved:
Episode ID: dev_12345678
{
  "child_id": "demo",
  "title": "初めてのバースデーケーキ",
  "content": "誕生日パーティーで、ケーキを見て「わー！」と歓声を上げ...",
  ...
}
```

**④ index_media_analysis の実行**
- 本番モード：
```json
{
  "status": "success",
  "message": "Episode indexed with ID: AbC123DefG456"
}
```
- 開発モード：
```
🔍 [DEVELOPMENT MODE] Vector indexing skipped
Would index episode: dev_12345678 for child: demo
```

### 3. 開発モードでの実行

Firestoreやベクトル保存をスキップしてログ出力のみ行う場合：

```python
# コード内で設定
from agent import set_development_mode
set_development_mode(True)

# または環境変数で設定
export DEVELOPMENT_MODE=true
```

## プロジェクト構造

```
media_processing_agent/
├── agent.py           # メインのエージェント実装
├── pyproject.toml     # Python依存関係定義
├── uv.lock           # uvのロックファイル
├── .env              # 環境変数（要作成）
└── README.md         # このファイル
```

## 主な機能

### 1. objective_analyzer
- メディアファイルから客観的な事実を抽出
- 子供の行動、感情、環境などを分析

### 2. highlight_identifier
- 最も印象的な瞬間を特定
- エピソードログを構造化データとして生成

### 3. save_summary
- FirestoreにエピソードデータをJSON形式で保存
- 開発モードではログ出力のみ

### 4. index_media_analysis
- テキストデータをベクトル化
- Vertex AI Vector Searchにインデックス
- 意味検索を可能に

## データ構造

### エピソードログ
```json
{
  "title": "ハイライトのタイトル",
  "summary": "具体的な状況説明",
  "emotion": "主な感情",
  "activities": ["活動のリスト"],
  "development_milestones": ["発達の兆候"],
  "vector_tags": ["検索用タグ"]
}
```

### Firestoreドキュメント
- コレクション: `episodes`
- フィールド: title, content, child_id, created_at, etc.

## トラブルシューティング

### 認証エラー
```bash
# Google Cloud認証を再設定
gcloud auth application-default login
```

### Vertex AI APIエラー
```bash
# APIを有効化
gcloud services enable aiplatform.googleapis.com
```

### Firestoreエラー
```bash
# Firestoreを有効化
gcloud services enable firestore.googleapis.com
```

## 注意事項

- メディアファイルはGoogle Cloud Storageまたは公開URLでアクセス可能である必要があります
- 大きな動画ファイルは処理に時間がかかる場合があります
- ベクトル検索機能を使用するには、事前にVertex AI Vector Search Indexの作成が必要です

## ライセンス

このプロジェクトは内部使用を目的としています。
