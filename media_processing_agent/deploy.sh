#!/bin/bash

# デプロイスクリプト for Media Processing Agent Cloud Function

set -e  # エラーが発生したら即座に終了

# デフォルト値
PROJECT_ID=${PROJECT_ID:-"hackason-464007"}
REGION=${REGION:-"us-central1"}
SERVICE_ACCOUNT=${SERVICE_ACCOUNT:-"${PROJECT_ID}@appspot.gserviceaccount.com"}
VERTEX_AI_INDEX_ID=${VERTEX_AI_INDEX_ID:-"5650858647094296576"}
VERTEX_AI_INDEX_ENDPOINT_ID=${VERTEX_AI_INDEX_ENDPOINT_ID:-"5893998287041658880"}

# 色付きの出力用
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Media Processing Agent - Cloud Function デプロイスクリプト${NC}"
echo "================================================"

echo "デプロイ設定:"
echo "  Project ID: $PROJECT_ID"
echo "  Region: $REGION"
echo "  Service Account: $SERVICE_ACCOUNT"
echo "  Vertex AI Index ID: $VERTEX_AI_INDEX_ID"
echo "  Vertex AI Index Endpoint ID: $VERTEX_AI_INDEX_ENDPOINT_ID"
echo ""

# 確認プロンプト
read -p "このままデプロイを続けますか? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "デプロイをキャンセルしました"
    exit 1
fi

# プロジェクトの設定
echo -e "${YELLOW}プロジェクトを設定しています...${NC}"
gcloud config set project $PROJECT_ID

# 必要なAPIの有効化
echo -e "${YELLOW}必要なAPIを有効化しています...${NC}"
gcloud services enable cloudfunctions.googleapis.com \
    cloudbuild.googleapis.com \
    firestore.googleapis.com \
    aiplatform.googleapis.com \
    eventarc.googleapis.com

# Firestore Trigger Function のデプロイ
echo -e "${YELLOW}Firestore Trigger Function をデプロイしています...${NC}"
gcloud functions deploy process-media-upload-firestore \
    --gen2 \
    --runtime=python312 \
    --region=$REGION \
    --source=./cloud_functions \
    --entry-point=process_media_upload_firestore \
    --trigger-event-filters="type=google.cloud.firestore.document.v1.written" \
    --trigger-event-filters="database=database" \
    --trigger-event-filters-path-pattern="document=media_uploads/{docId}" \
    --trigger-location=$REGION \
    --memory=1GB \
    --timeout=540s \
    --max-instances=5 \
    --set-env-vars="GOOGLE_CLOUD_PROJECT=$PROJECT_ID,GOOGLE_CLOUD_LOCATION=$REGION,VERTEX_AI_INDEX_ID=$VERTEX_AI_INDEX_ID,VERTEX_AI_INDEX_ENDPOINT_ID=$VERTEX_AI_INDEX_ENDPOINT_ID" \
    --service-account=$SERVICE_ACCOUNT

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Cloud Function のデプロイが成功しました！${NC}"
    echo ""
    echo "デプロイ完了！"
    echo ""
    echo "次のステップ:"
    echo ""
    echo "1. Firestoreの media_uploads コレクションにドキュメントを作成:"
    echo "   必須フィールド:"
    echo "   - media_uri: メディアファイルのURI (gs:// または https://)"
    echo "   - user_id: ユーザーID"
    echo "   - child_id: 子供のID"
    echo "   - processing_status: 'pending' (デフォルト)"
    echo ""
    echo "2. 自動的にCloud Functionがトリガーされ:"
    echo "   - processing_status が 'processing' に更新"
    echo "   - メディア分析を実行"
    echo "   - episodes コレクションにエピソードを作成"
    echo "   - processing_status が 'completed' に更新"
    echo "   - episode_id フィールドが追加"
    echo ""
    echo "3. ログを確認:"
    echo "   gcloud functions logs read process-media-upload-firestore --region=$REGION"
    echo ""
    echo "4. 結果の確認:"
    echo "   - media_uploadsコレクション: 処理状態とepisode_id"
    echo "   - episodesコレクション: 生成されたエピソード"
    echo "   - processing_logsコレクション: 処理ログ"
else
    echo -e "${RED}✗ デプロイに失敗しました${NC}"
    exit 1
fi