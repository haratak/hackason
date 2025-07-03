# Firebase 統合デプロイガイド

このプロジェクトは、複数のFirebaseサービスを統合して管理しています。

## プロジェクト構成

```
hackason/
├── firebase.json                    # 統合Firebase設定
├── .firebaserc                      # Firebaseプロジェクト設定
├── content_generator/               # コンテンツ生成Functions
│   └── functions/
├── media_processing_agent/          # メディア処理Functions  
│   └── functions/
├── dairy_publisher/                 # Webホスティング
│   └── public/
└── mobile/                         # Flutterアプリ（別管理）
```

## デプロイコマンド

### すべてをデプロイ
```bash
cd /Users/harataku/dev/Work/hackason
firebase deploy
```

### 個別デプロイ

#### Functions (コンテンツ生成) のみ
```bash
firebase deploy --only functions:content-generator
```

#### Functions (メディア処理) のみ
```bash
firebase deploy --only functions:media-processor
```

#### Hosting のみ
```bash
firebase deploy --only hosting
```

### 特定の関数のみデプロイ
```bash
# コンテンツ生成の特定関数
firebase deploy --only functions:content-generator:generate_notebook_on_create

# メディア処理の特定関数
firebase deploy --only functions:media-processor:process_media_for_cloud_function
```

## ロールバック方法

前の個別管理構成に戻す場合：

1. 統合設定を削除
```bash
rm firebase.json
rm .firebaserc
```

2. バックアップを復元
```bash
mv content_generator/firebase.json.backup content_generator/firebase.json
mv content_generator/.firebaserc.backup content_generator/.firebaserc
mv dairy_publisher/firebase.json.backup dairy_publisher/firebase.json
mv dairy_publisher/.firebaserc.backup dairy_publisher/.firebaserc
mv media_processing_agent/firebase.json.backup media_processing_agent/firebase.json
mv media_processing_agent/.firebaserc.backup media_processing_agent/.firebaserc
```

3. 各ディレクトリで個別にデプロイ
```bash
cd content_generator && firebase deploy --only functions
cd ../dairy_publisher && firebase deploy --only hosting
cd ../media_processing_agent && firebase deploy --only functions
```

## 注意事項

- `mobile/` ディレクトリのFlutterアプリは別管理のままです
- Functions は `codebase` で分離されているため、独立してデプロイ可能です
- Python Functionsのランタイムは `python311` を使用しています