from google.cloud import firestore
import os

project_id = os.environ.get('GOOGLE_CLOUD_PROJECT', 'hackason-464007')
db = firestore.Client(project=project_id)

# media_uploadsのprocessing_statusをリセット
print("Resetting processing_status in media_uploads...")
docs = db.collection('media_uploads').stream()
reset_count = 0

for doc in docs:
    try:
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
    except Exception as e:
        print(f"Error resetting document {doc.id}: {e}")

print(f"Total reset: {reset_count} documents in media_uploads")
print("\nMedia uploads reset completed!")
print("\nNext steps:")
print("1. Deploy the updated Cloud Functions: cd functions && firebase deploy --only functions")
print("2. The media will be automatically reprocessed with captured_at field")