#!/bin/bash

PROJECT_ID="hackason-464007"
REGION="us-central1"
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format="value(projectNumber)")

echo "Creating Eventarc trigger for Firestore..."

gcloud eventarc triggers create firestore-media-upload-trigger \
    --location=$REGION \
    --destination-run-service=process-media-upload-firestore \
    --destination-run-region=$REGION \
    --event-filters="type=google.cloud.firestore.document.v1.written" \
    --event-filters="database=database" \
    --event-data-content-type="application/protobuf" \
    --event-filters-path-pattern="document=media_uploads/{docId}" \
    --service-account="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

echo "Trigger created successfully!"