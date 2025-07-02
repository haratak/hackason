# dairy_publisher アーキテクチャ概要

## 概要
dairy_publisherは、子どもの成長記録を新聞風のレイアウトで表示するWebアプリケーションです。Firebase Hostingで配信され、Firestoreからデータを取得して表示します。

## 主な機能
- 成長記録（ノートブック）の閲覧
- 新聞風レイアウトでの表示
- URLベースの共有機能
- レスポンシブデザイン

## アーキテクチャ図

```mermaid
graph TB
    subgraph "dairy_publisher コンポーネント"
        subgraph "Frontend (Firebase Hosting)"
            HTML[index.html<br/>- SPA エントリポイント<br/>- ルーティング処理]
            CSS[style.css<br/>- 新聞風スタイリング<br/>- レスポンシブ対応]
            JS[埋め込みJavaScript<br/>- Firestore連携<br/>- データ表示処理]
        end
        
        subgraph "Configuration"
            FIREBASE[firebase.json<br/>- Hosting設定<br/>- URL書き換えルール]
            ENV[.env<br/>- GCPプロジェクト設定<br/>- Vertex AI設定]
        end
    end
    
    subgraph "外部サービス"
        FIRESTORE[(Firestore<br/>データベース)]
        HOSTING[Firebase<br/>Hosting]
    end
    
    subgraph "データ構造"
        DATA[children/{childId}/<br/>notebooks/{notebookId}/<br/>- nickname<br/>- date<br/>- topics[5]]
    end
    
    USER[ユーザー] -->|URLアクセス| HOSTING
    HOSTING -->|静的ファイル配信| HTML
    HTML --> CSS
    HTML --> JS
    JS -->|データ取得| FIRESTORE
    FIRESTORE --> DATA
    
    style HTML fill:#f9f,stroke:#333,stroke-width:2px
    style FIRESTORE fill:#ffa,stroke:#333,stroke-width:2px
    style HOSTING fill:#aff,stroke:#333,stroke-width:2px
```

## コンポーネント詳細

### 1. フロントエンド層
- **index.html**: メインのHTMLファイル
  - URLパラメータから子どもIDとノートブックIDを取得
  - Firebase SDKの初期化と設定
  - データ取得とレンダリング処理
  
- **style.css**: スタイルシート
  - 新聞風の2カラムレイアウト
  - 3種類の写真サイズ（large, medium, small）
  - モバイル対応のレスポンシブデザイン

### 2. データフロー
1. ユーザーがURL（`/children/{childId}/notebooks/{notebookId}`）にアクセス
2. Firebase HostingがSPAを配信
3. JavaScriptがURLからパラメータを抽出
4. FirestoreからノートブックデータをフェッチPro
5. 5つのトピックを新聞風レイアウトで表示

### 3. トピック構成
- **トピック1**: 大きな写真付きメインストーリー
- **トピック2**: テキストのみのセクション
- **トピック3**: 小さな写真付きストーリー
- **トピック4**: 中サイズの写真セクション
- **トピック5**: 達成事項・マイルストーン

### 4. 環境設定
- Firebase プロジェクト: hackason-464007
- GCP プロジェクトとの連携
- Vertex AI設定（将来の拡張用）

## セキュリティ考慮事項
- Firebase APIキーはフロントエンドに埋め込み（Firebase標準）
- データアクセス制御はFirestoreセキュリティルールに依存
- 現在は認証機能なし（公開URLでアクセス可能）

## 今後の拡張可能性
- Firebase Functions（サーバーサイド処理）
- 認証機能の追加
- PDFエクスポート機能
- 共有機能の強化