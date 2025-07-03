# DailyPublisher - 成長記録新聞風ビューアー

## 概要

DailyPublisherは、子どもの成長記録を新聞風のレイアウトで美しく表示するWebアプリケーションです。家族向けWebアプリケーションシステムの一部として、保護者が記録した5つのトピックを視覚的に魅力的な形式で共有できるようにします。

## システム全体における役割

本コンポーネントは、以下の役割を担います：

- **閲覧専用インターフェース**: Firestoreに保存された成長記録データの表示
- **共有機能**: URL経由での簡単な記録共有
- **ビジュアル変換**: 日々の記録を新聞スタイルの読みやすい形式に変換

## アーキテクチャ

```mermaid
graph TB
    subgraph "DailyPublisher Component"
        subgraph "Frontend (SPA)"
            HTML[index.html<br/>Entry Point]
            CSS[style.css<br/>Newspaper Layout]
            JS[JavaScript<br/>Firebase SDK v10.7.1]
        end
        
        subgraph "Routing"
            URL[URL Parser<br/>/children/:childId/notebooks/:notebookId]
        end
        
        subgraph "Data Layer"
            FS[Firestore Client<br/>Real-time Data]
        end
    end
    
    subgraph "External Services"
        FH[Firebase Hosting]
        DB[(Cloud Firestore<br/>Database)]
        ST[Firebase Storage<br/>Photos]
    end
    
    subgraph "Data Structure"
        DS[children/:childId/notebooks/:notebookId<br/>- nickname<br/>- date<br/>- topics[5]]
    end
    
    User[User/Browser] --> FH
    FH --> HTML
    HTML --> JS
    JS --> URL
    URL --> FS
    FS --> DB
    DB --> DS
    JS --> CSS
    
    DS -.-> |Photo URLs| ST
    ST -.-> |Images| JS
```

## 機能詳細

### 1. データ取得と表示
- URLパラメータから`childId`と`notebookId`を抽出
- Firestoreから対応するノートブックデータを取得
- 5つのトピックを新聞風レイアウトで表示
- Firebase設定はindex.html内にハードコード（環境変数未使用）

### 2. レイアウト構成
- **トピック1**: メインストーリー（大きな写真付き）
  - サブタイトル表示対応
- **トピック2**: テキストセクション（テキストのみ）
- **トピック3**: サイドストーリー（大きな写真付き）
  - キャプション表示対応
- **トピック4**: 写真セクション（大きな写真）
  - キャプション表示対応
- **トピック5**: 中央セクション（まとめ）

### 3. メディア処理機能
- **動画サポート**: .mov, .mp4, .avi, .wmv, .flv, .webm
- **動画サムネイル**: サーバー側で生成されたサムネイルを表示
- **gs://形式URL変換**: Firebase Storage URLをHTTPS形式に自動変換
- **縦長画像対応**: アスペクト比に応じて高さを自動調整
- **動画アイコン**: 動画サムネイルに再生アイコンをオーバーレイ表示

### 4. UI/UX機能
- ローディングアニメーション（スピナー付き）
- エラーハンドリング（データ未検出時の親切なメッセージ）
- レスポンシブデザイン（モバイル対応）
- 日本語日付フォーマット（年月日表示）
- WebView検出機能
- ニックネーム通信（子どもの名前を含むタイトル）

## 技術スタック

- **Frontend**: Vanilla JavaScript (ES6+)
- **Styling**: CSS3 (Grid Layout, Flexbox)
- **Database**: Cloud Firestore
- **Storage**: Firebase Storage（画像・動画）
- **Hosting**: Firebase Hosting
- **Firebase SDK**: v10.7.1 (compat mode)
- **Build**: 静的ファイル（ビルド不要）

## データフロー

```mermaid
sequenceDiagram
    participant U as User
    participant B as Browser
    participant FH as Firebase Hosting
    participant JS as JavaScript App
    participant FS as Firestore
    
    U->>B: アクセス (/children/123/notebooks/456)
    B->>FH: HTTP Request
    FH->>B: index.html, CSS, JS
    B->>JS: ページロード
    JS->>JS: URLパース (childId=123, notebookId=456)
    JS->>FS: データ取得要求
    FS->>JS: ノートブックデータ
    JS->>B: DOM更新（新聞レイアウト）
    B->>U: 成長記録を表示
```

## セットアップ

### 前提条件
- Firebase プロジェクトへのアクセス権
- Node.js（Firebase CLIのため）

### 設定
Firebase設定は`public/index.html`内にハードコードされています。プロジェクト固有の設定に変更する必要がある場合は、該当箇所を直接編集してください。

### デプロイ
```bash
firebase deploy --only hosting
```

## ディレクトリ構造

```
dairy_publisher/
├── README.md           # このファイル
├── architecture.md     # 詳細設計ドキュメント
├── firebase.json.backup # Firebase設定（バックアップ）※注：firebase.jsonは現在存在しません
├── .firebaserc.backup  # Firebaseプロジェクト設定（バックアップ）
├── .env.example       # 環境変数テンプレート
├── .gitignore         # Git除外設定
├── .python-version    # Pythonバージョン指定
├── .claude/           # Claude Code設定
│   └── settings.local.json
├── .firebase/         # Firebaseキャッシュ
│   └── hosting.cHVibGlj.cache
└── public/            # 公開ディレクトリ
    ├── index.html     # SPAエントリーポイント
    └── style.css      # スタイルシート
```

**注意**: `firebase.json`ファイルが現在存在しないため、デプロイ前に`firebase.json.backup`から復元する必要があります。

## 今後の拡張予定

- Firebase Functions による PDF エクスポート機能
- Vertex AI を使用した自動要約生成
- 認証機能の追加（プライベート共有）
- PWA 対応（オフライン閲覧）

## 関連コンポーネント

- **Photo Web App**: 写真のアップロードと管理
- **データ入力アプリ**: 成長記録の作成・編集
- **管理画面**: システム全体の管理

## ライセンス

プロジェクトのライセンスに準拠