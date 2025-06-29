#!/bin/bash

# 簡単なデプロイスクリプト

echo "Cloud Run Function をデプロイします..."

# 1. Cloud Functionsディレクトリに移動
cd cloud_functions

# 2. Cloud Run Functionをデプロイ（HTTPトリガーのみ）
gcloud run deploy media-processor \
  --source . \
  --function=process_media_upload \
  --region=us-central1 \
  --allow-unauthenticated

echo ""
echo "デプロイ完了！"
echo ""
echo "テスト方法："
echo "1. 上記のURLにアクセス"
echo "2. 以下のJSONをPOSTリクエストで送信："
echo '{'
echo '  "doc_id": "test123",'
echo '  "media_uri": "gs://your-bucket/test.mp4",'
echo '  "user_id": "test-user",'
echo '  "child_id": "test-child"'
echo '}'