# Firestore セキュリティルールのデプロイ方法

## 概要
このドキュメントでは、Firestore セキュリティルールをデプロイする方法を説明します。

## 前提条件
- Firebase CLI がインストールされていること
- Firebase プロジェクトにログインしていること

## デプロイ手順

### 1. Firebase CLI のインストール（未インストールの場合）
```bash
npm install -g firebase-tools
```

### 2. Firebase にログイン
```bash
firebase login
```

### 3. Firebase プロジェクトの初期化（初回のみ）
```bash
firebase init firestore
```
- 既存のプロジェクトを選択
- `firestore.rules` ファイルの場所を確認（デフォルトでOK）

### 4. セキュリティルールのデプロイ
```bash
firebase deploy --only firestore:rules
```

## Firebase コンソールからの手動デプロイ

1. [Firebase Console](https://console.firebase.google.com) にアクセス
2. プロジェクトを選択
3. 左メニューから「Firestore Database」を選択
4. 上部タブから「ルール」を選択
5. `firestore.rules` ファイルの内容をコピー＆ペースト
6. 「公開」ボタンをクリック

## セキュリティルールの概要

作成したルールは以下の権限を提供します：

- **users コレクション**: 認証済みユーザーは自分のドキュメントのみ作成・更新可能
- **families コレクション**: 認証済みユーザーが作成可能、メンバーのみ読み取り・更新可能
- **children コレクション**: 家族のメンバーのみアクセス可能
- **episodes コレクション**: 作成者のみアクセス可能
- **media_uploads コレクション**: 作成者のみアクセス可能
- **file_uploads コレクション**: 作成者のみアクセス可能

## トラブルシューティング

### Permission-denied エラーが続く場合

1. ルールが正しくデプロイされているか確認
   ```bash
   firebase deploy --only firestore:rules --debug
   ```

2. Firebase コンソールでルールが反映されているか確認

3. クライアントアプリを再起動

4. 認証トークンをリフレッシュ（ログアウト → ログイン）

### デバッグモード

開発中は以下の簡易ルールを使用することも可能です（本番環境では使用しないでください）：

```javascript
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    match /{document=**} {
      allow read, write: if request.auth != null;
    }
  }
}
```