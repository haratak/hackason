# おまかせダイアリー - Kids Diary Platform

## 概要

おまかせダイアリーは、子どもの成長記録を自動的に整理し、新聞風のレイアウトで週次ノートブックとして提供するプラットフォームです。親が撮影した写真や動画をアップロードするだけで、AIが内容を分析し、子どもの成長や思い出を自動的に記録・整理します。

## 主な特徴

- 📱 **簡単な写真・動画アップロード**: モバイルアプリから簡単に思い出を記録
- 🤖 **AI による自動分析**: アップロードされたメディアから成長記録を自動抽出
- 📰 **週次ノートブックの自動生成**: 毎週月曜日に新聞風レイアウトで思い出をまとめ
- 👨‍👩‍👧‍👦 **家族での共有**: URLを共有するだけで、離れた家族も成長記録を閲覧可能
- 🔍 **賢い検索機能**: ベクトル検索により、関連する思い出を自動的に関連付け

## システム全体アーキテクチャ

```mermaid
graph TB
    subgraph "ユーザーインターフェース"
        USER[👤 ユーザー<br/>（親・家族）]
        MOBILE[📱 モバイルアプリ<br/>（Flutter）<br/>- 写真/動画アップロード<br/>- タイムライン閲覧<br/>- ノートブック共有]
        WEB[🌐 Dairy Publisher<br/>（Web SPA）<br/>- 新聞風レイアウト<br/>- 5つのトピック表示<br/>- 共有URL対応]
    end
    
    subgraph "AI処理層"
        MEDIA[🎬 Media Processing Agent<br/>- 画像/動画分析<br/>- エピソード抽出<br/>- 感情分析・タグ付け]
        CONTENT[📝 Content Generator<br/>- 週次ノートブック生成<br/>- 5つのテーマ整理<br/>- 温かい文章生成]
    end
    
    subgraph "データ基盤（Google Cloud Platform）"
        AUTH[🔐 Firebase Auth<br/>認証管理]
        FIRESTORE[(🗄️ Firestore<br/>- 家族データ<br/>- 子どもプロフィール<br/>- エピソード<br/>- ノートブック)]
        STORAGE[☁️ Cloud Storage<br/>写真・動画保存]
        VECTOR[🔍 Vertex AI<br/>Vector Search<br/>意味検索インデックス]
        FUNCTIONS[⚡ Cloud Functions<br/>イベントトリガー]
    end
    
    subgraph "将来の拡張"
        PHOTOS[📸 Photo Web App<br/>（開発中）<br/>- Google Photos連携<br/>- 自動写真選別]
    end
    
    %% ユーザーフロー
    USER -->|アプリ利用| MOBILE
    USER -->|URL共有| WEB
    
    %% モバイルアプリの接続
    MOBILE -->|認証| AUTH
    MOBILE -->|データ保存| FIRESTORE
    MOBILE -->|メディアアップロード| STORAGE
    MOBILE -->|ノートブック閲覧| FIRESTORE
    
    %% AI処理フロー
    STORAGE -->|トリガー| FUNCTIONS
    FUNCTIONS -->|起動| MEDIA
    MEDIA -->|メディア分析| STORAGE
    MEDIA -->|エピソード保存| FIRESTORE
    MEDIA -->|ベクトル生成| VECTOR
    
    %% コンテンツ生成フロー
    FUNCTIONS -->|週次実行| CONTENT
    CONTENT -->|エピソード取得| FIRESTORE
    CONTENT -->|類似検索| VECTOR
    CONTENT -->|ノートブック保存| FIRESTORE
    
    %% Web表示
    WEB -->|データ取得| FIRESTORE
    WEB -->|画像取得| STORAGE
    
    %% 将来の拡張
    PHOTOS -.->|将来統合| MEDIA
    
    style USER fill:#ffd,stroke:#333,stroke-width:2px
    style MOBILE fill:#bbf,stroke:#333,stroke-width:2px
    style WEB fill:#fbf,stroke:#333,stroke-width:2px
    style MEDIA fill:#bfb,stroke:#333,stroke-width:2px
    style CONTENT fill:#fbb,stroke:#333,stroke-width:2px
    style FIRESTORE fill:#ffa,stroke:#333,stroke-width:2px
    style PHOTOS fill:#ddd,stroke:#333,stroke-width:2px,stroke-dasharray: 5 5
```

## コンポーネント概要

### 1. モバイルアプリ（Mobile App）
- **役割**: メインのユーザーインターフェース
- **技術**: Flutter（クロスプラットフォーム対応）
- **機能**: 
  - 家族・子どもプロフィール管理
  - 写真・動画の選択とアップロード（Firebase Storage直接アップロード）
  - AIが分析したエピソードのタイムライン表示（動画サムネイル対応）
  - 週次ノートブックの閲覧と共有（WebView表示）
  - 感情的なタイトルでの思い出表示
  - 日付ごとのグルーピング機能

### 2. メディア処理エージェント（Media Processing Agent）
- **役割**: アップロードされたメディアをAIで分析
- **技術**: Python 3.12 + Google ADK + Gemini 2.5 Flash
- **機能**:
  - 写真・動画から子どもの行動や表情を分析
  - 年齢に応じた多角的分析（0-6ヶ月、6-12ヶ月、12-24ヶ月、24ヶ月+）
  - 感情的な日本語タイトルの生成
  - 検索用タグとベクトル埋め込みの作成（768次元）
  - 動画サムネイルの自動生成
  - Firebase Functions v2対応（HTTPトリガー/Firestoreトリガー）

### 3. コンテンツジェネレーター（Content Generator）
- **役割**: 週次ノートブックの自動生成
- **技術**: Python 3.12 + Google ADK + Gemini 1.5 Flash
- **機能**:
  - Firestoreトリガーまたは定期実行（毎週日曜朝9時JST）で起動
  - 1週間のエピソードを5つのテーマに整理
  - 親向けの温かい文章生成（200-300文字）
  - 関連エピソードの自動関連付け（Vertex AI Vector Search使用）
  - カスタマイズ可能なトーン・フォーカス設定
  - analysis_resultsコレクションからのメディア収集

### 4. ダイアリーパブリッシャー（Dairy Publisher）
- **役割**: 成長記録の新聞風ビューアー（閲覧専用インターフェース）
- **技術**: Vanilla JavaScript (ES6+) + CSS3 + Firebase Hosting
- **機能**:
  - 新聞風レイアウトで5つのトピックを美しく表示
  - URLパラメータベースのルーティング（/children/:childId/notebooks/:notebookId）
  - レスポンシブデザイン（モバイル対応）
  - Firebase SDK v10.7.1によるリアルタイムデータ取得
  - 動画サポート（.mov, .mp4, .avi, .wmv, .flv, .webm）
  - サーバー生成サムネイル表示
  - gs://形式URLの自動HTTPS変換
  - エラーハンドリングとローディングアニメーション

### 5. フォトWebアプリ（Photo Web App）※開発中
- **役割**: Google Photosからの自動写真収集
- **技術**: Python + Flask + Google Photos API
- **機能**:
  - 顔認識による特定の子どもの写真抽出
  - 将来的にメディア処理エージェントと統合予定

## データフロー

1. **メディアアップロード**: 親がモバイルアプリで写真・動画をアップロード
2. **AI分析**: Media Processing Agentが内容を分析し、成長記録を抽出
3. **データ保存**: エピソードとしてFirestoreに保存、検索用ベクトルも生成
4. **週次生成**: 毎週月曜日にContent Generatorが1週間分をまとめてノートブック作成
5. **閲覧・共有**: モバイルアプリやWebで閲覧、URLで家族と共有

## 技術スタック

- **フロントエンド**: Flutter（モバイル）、HTML/CSS/JS（Web）
- **バックエンド**: Python 3.12、Google ADK (Agent Development Kit)
- **AI/ML**: 
  - Gemini 2.5 Flash（メディア分析）
  - Gemini 1.5 Flash（コンテンツ生成）
  - text-embedding-004（768次元ベクトル化）
- **インフラ**: Google Cloud Platform
  - Firebase（Auth, Firestore, Storage, Hosting）
  - Firebase Functions v2（Cloud Functions）
  - Vertex AI Vector Search
  - Cloud Storage（サムネイル保存）
- **開発ツール**: Git、Firebase CLI、gcloud CLI、flutterfire

## セキュリティとプライバシー

- Google認証によるセキュアなログイン
- 家族単位でのデータ分離
- URLベースの共有（認証不要だが、URLを知っている人のみアクセス可能）
- 子どもの写真は家族メンバーのみがアクセス可能

## 今後の展望

- Google Photos連携による自動写真収集
- Firebase FunctionsによるPDFエクスポート機能
- 認証機能の追加（プライベート共有）
- PWA対応（オフライン閲覧）
- より高度なAI分析（発達段階の詳細な追跡など）
- 多言語対応
- プッシュ通知機能
- WebViewでのPDFエクスポート機能（モバイルアプリ）

## プロジェクト構成

```
hackason/
├── mobile/                    # Flutterモバイルアプリ
├── media_processing_agent/    # メディア分析AIエージェント
├── content_generator/         # ノートブック生成AIエージェント
├── dairy_publisher/          # Web表示用静的サイト
├── photo_web_app/           # Google Photos連携アプリ（開発中）
└── CLAUDE.md                # プロジェクト設定
```

各コンポーネントの詳細なアーキテクチャについては、それぞれのディレクトリ内のarchitecture.mdファイルを参照してください。

## 開発環境

- Python 3.12
- Flutter SDK
- Google Cloud Platform アカウント
- Firebase プロジェクト（hackason-464007）
- Node.js（Firebase CLI用）
- 必要な環境変数:
  - `GCP_PROJECT_ID`: hackason-464007
  - `GCP_LOCATION`: us-central1
  - `VERTEX_AI_VECTOR_SEARCH_INDEX_ID`
  - `VERTEX_AI_VECTOR_SEARCH_INDEX_ENDPOINT_ID`

## ライセンス

このプロジェクトは内部利用を目的としています。