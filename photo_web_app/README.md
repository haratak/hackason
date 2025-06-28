# 写真自動選別システム (Work in Progress)

Google Photosから特定の人物が写っている写真を自動的に選別し、将来的に連絡帳アプリケーションに活用するための技術検証プロジェクト

## ⚠️ 開発状況

**このプロジェクトは現在開発中（Work in Progress）です。**

本アプリケーションは、Google Photosの写真から顔認識技術を使って特定の人物（子供など）の写真を自動選別する機能の技術検証を目的としています。最終的には、選別された写真を使用して自動的に連絡帳を作成するアプリケーションの一部として機能することを想定していますが、現時点では以下の制限があります：

### 現在の実装状況
- ✅ Google OAuth2認証によるGoogle Photosへのアクセス
- ✅ Vertex AIを使用した顔特徴の抽出
- ✅ 類似度による写真の選別
- ❌ クラウドストレージへのデータ保存（現在はセッションのみ）
- ❌ 連絡帳作成機能
- ❌ 動画コンテンツの処理

### 主な課題と懸念点

1. **データの永続化**: 現在、顔特徴データはセッションにのみ保存されるため、ブラウザを閉じるとデータが失われます。クラウドストレージ（Firebase、Cloud Storageなど）への保存機能の実装が必要です。

2. **動画コンテンツの扱い**: Google Photosには大量の動画がアップロードされていますが、動画内の人物を判定することは計算コストが非常に高く、現実的ではありません。動画をどのように扱うか（スキップ、サムネイルのみ処理、特定フレームの抽出など）の方針決定が必要です。

3. **スケーラビリティ**: 大量の写真（数万枚規模）を処理する際のパフォーマンスとコストの最適化が必要です。

4. **プライバシーとセキュリティ**: 顔認識データの適切な管理と、ユーザーのプライバシー保護の仕組みが必要です。

## 機能

1. **Google OAuth2認証**: Google Photosへの読み取り専用アクセス
2. **顔特徴学習**: アップロードされた子供の写真から顔特徴を抽出
3. **自動スキャン**: Google Photos内の写真をスキャンして類似の顔を検索
4. **プライバシー重視**: 写真は保存せず、セッション中のみ顔特徴データを保持

## セットアップ

### 1. 必要な準備

- Python 3.8以上
- Google Cloud Projectの作成
- Google Photos API の有効化
- Vertex AI API の有効化

### 2. Google OAuth2の設定

1. [Google Cloud Console](https://console.cloud.google.com/)でプロジェクトを作成
2. APIとサービス > 認証情報 から OAuth 2.0 クライアント IDを作成
3. 承認済みのリダイレクトURIに `http://localhost:5000/callback` を追加

### 3. 環境変数の設定

```bash
cp .env.example .env
```

`.env`ファイルを編集して以下の値を設定:

- `GOOGLE_CLIENT_ID`: OAuth2クライアントID
- `GOOGLE_CLIENT_SECRET`: OAuth2クライアントシークレット
- `GCP_PROJECT_ID`: Google Cloud プロジェクトID
- `FLASK_SECRET_KEY`: Flaskのセッションキー（ランダムな文字列）

### 4. 依存関係のインストール

```bash
# uvを使用
uv sync
```

### 5. Google Cloud認証

```bash
gcloud auth application-default login
```

## 実行方法

```bash
uv run python app.py
```

ブラウザで `http://localhost:5000` にアクセス

## 使い方

1. トップページで「Googleでログイン」をクリック
2. Google Photosへのアクセスを許可
3. 対象の子供の写真を3枚程度アップロード
4. 「顔特徴を抽出」をクリック
5. 「Google Photosをスキャン」をクリックして検索開始

## 注意事項

- Vertex AI Multimodal Embedding APIの利用料金が発生します
- 大量の写真をスキャンする場合は時間がかかります
- 類似度のしきい値（デフォルト: 75%）は調整可能です

## トラブルシューティング

### Vertex AI APIエラー

- GCPプロジェクトでVertex AI APIが有効になっているか確認
- 適切な権限があるか確認
- リージョンが正しいか確認（デフォルト: us-central1）

### Google Photos APIエラー

- OAuth2の同意画面で適切なスコープが設定されているか確認
- リフレッシュトークンが有効か確認