# Content Generator

Content Generatorは、Google Cloud Platform上でGoogle ADK (Agent Development Kit) を利用し、AIエージェントがコンテンツを自動生成するプロジェクトです。

## 機能

### 1. ノートブックの生成

- Firestoreドキュメントの作成をトリガーにノートブックを生成
- Cloud Schedulerによる定期実行（毎週）
- 複数ソースからの情報収集
- カスタマイズ可能なトピック

### 2. テーマ分析とメディア収集

- 過去のテーマを分析し、新しいトピックを提案
- `analysis_results`コレクションからメディアを収集
- 重要な出来事を抽出
- LLMを活用したメディア選定

### 3. AIによる要約作成

- Gemini 1.5 Flash を利用して要約を作成
- プロンプトによるトーン調整
- トピックに沿った内容の絞り込み
- 生成されたコンテンツの品質評価

## アーキテクチャ

### トリガー

#### 1. Firestoreトリガー

```
children/{childId}/notebooks/{notebookId}
```

- 上記ドキュメントの作成をトリガーに実行
- ステータス: `requested` → `processing` → `completed`/`failed`

#### 2. 定期実行トリガー

- 毎週日曜日の朝9時(JST)に実行
- アカウントごとにノートブック作成をリクエスト

### 処理フロー

1. **リクエスト受付**
   - Firestoreにドキュメントを作成
   - `period`（期間）を指定
   - `customization`（`tone`/`focus`）で内容を調整
   - `sources`で使用するメディアを指定

2. **メディア収集**
   - `analysis_results`コレクションから情報を収集
   - `analysis_id`をもとにメディアを特定
   - テーマに沿った内容か判定

3. **要約作成**
   - 収集した情報から重要な出来事を抽出
   - プロンプトを動的に生成し、コンテンツ作成を指示
   - プロンプトによる出力調整

4. **結果の保存**
   - Firestoreへ結果を保存
   - ステータスを更新
   - エラー時のログ記録

## 技術スタック

- **言語**: Python 3.12
- **プラットフォーム**: Google Cloud Platform
  - Cloud Functions (Gen2)
  - Firestore
  - Vertex AI
  - Cloud Storage
- **AI/ML**:
  - Gemini 1.5 Flash（コンテンツ生成）
  - Text Embedding Model（類似コンテンツ検索）
- **その他**: Firebase Functions

## 環境変数

### 設定

```bash
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_CLOUD_LOCATION=us-central1
VERTEX_AI_INDEX_ID=your-index-id
VERTEX_AI_INDEX_ENDPOINT_ID=your-endpoint-id
```

### デプロイ

```bash
# Firebase Functions をデプロイ
firebase deploy --only functions
```

## 利用方法

### 1. Firestoreドキュメントの作成

Firestoreに新しいドキュメントを作成してリクエストします。

```javascript
// リクエストの例
{
  status: "requested",
  period: {
    start: "2024-01-01",
    end: "2024-01-07"
  },
  customization: {
    tone: "フレンドリーな感じで", // 内容を調整
    focus: "楽しかった思い出"     // 内容を調整
  },
  sources: [
    {
      analysisId: "analysis_123",
      mediaId: "media_456",
      included: true
    }
  ]
}
```

### 2. 定期実行

Cloud Schedulerが毎週実行をトリガーします。

## ディレクトリ構成

### ファイル構成

```
content_generator/
├── functions/
│   ├── main.py         # Cloud Functionsのエントリーポイント
│   └── agent.py        # エージェントロジック
├── requirements.txt    # 依存ライブラリ
├── firebase.json       # Firebase設定
└── README.md           # このファイル
```

### 主要な関数

- `generate_notebook_on_create`: Firestoreトリガーで起動
- `generate_weekly_notebooks`: 定期実行で起動
- `analyze_period_and_themes`: テーマ分析
- `collect_episodes_by_theme`: メディア収集
- `orchestrate_notebook_generation`: ノートブック生成の全体管理
- `validate_and_save_notebook`: バリデーションと保存

## デバッグ・動作確認

### ログの確認方法

1. **メディア収集のログ**
   - `analysis_results`コレクションのどのデータが参照されたか
   - フィルタリング条件の確認
   - `selected_media_ids`の確認

2. **画像URLの確認**
   - `gs://URL`だけでなくHTTPSに変換されているか確認
   - Firebase Storageのパスを確認

3. **生成ログ**
   - Cloud Functionsの実行ログを確認
   - Vertex AIのAPI呼び出しログを確認
