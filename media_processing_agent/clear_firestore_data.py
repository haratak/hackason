from google.cloud import firestore
import os

project_id = os.environ.get('GOOGLE_CLOUD_PROJECT', 'hackason-464007')
db = firestore.Client(project=project_id)

# analysis_resultsコレクションのすべてのドキュメントを削除
print("Deleting all documents in analysis_results collection...")
docs = db.collection('analysis_results').stream()
deleted_count = 0

for doc in docs:
    doc.reference.delete()
    deleted_count += 1
    if deleted_count % 10 == 0:
        print(f"Deleted {deleted_count} documents...")

print(f"Total deleted: {deleted_count} documents from analysis_results")

# episodesコレクションも削除（旧形式のデータ）
print("\nDeleting all documents in episodes collection...")
docs = db.collection('episodes').stream()
deleted_count = 0

for doc in docs:
    doc.reference.delete()
    deleted_count += 1
    if deleted_count % 10 == 0:
        print(f"Deleted {deleted_count} documents...")

print(f"Total deleted: {deleted_count} documents from episodes")

# media_uploadsのprocessing_statusをリセット
print("\nResetting processing_status in media_uploads...")
docs = db.collection('media_uploads').stream()
reset_count = 0

for doc in docs:
    doc.reference.update({
        'processing_status': 'pending',
        'media_id': firestore.DELETE_FIELD,
        'emotional_title': firestore.DELETE_FIELD,
        'episode_count': firestore.DELETE_FIELD,
        'processing_error': firestore.DELETE_FIELD
    })
    reset_count += 1
    if reset_count % 10 == 0:
        print(f"Reset {reset_count} documents...")

print(f"Total reset: {reset_count} documents in media_uploads")
print("\nFirestore cleanup completed!")
print("\nIMPORTANT: Make sure to deploy the updated Cloud Functions before the documents are reprocessed!")
print("Run: firebase deploy --only functions")