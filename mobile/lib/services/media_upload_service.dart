import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:firebase_auth/firebase_auth.dart';
import 'package:flutter/foundation.dart';
import 'package:mobile/models/media_upload.dart';

class MediaUploadService {
  final FirebaseFirestore _firestore = FirebaseFirestore.instance;
  final FirebaseAuth _auth = FirebaseAuth.instance;

  CollectionReference get _mediaUploadsCollection =>
      _firestore.collection('media_uploads');

  Future<String?> createMediaUpload({
    required String childId,
    required String bucketName,
    required String filePath,
    required String contentType,
    int? fileSize,
    String? originalFilename,
    Map<String, dynamic>? customMetadata,
    DateTime? capturedAt,
  }) async {
    debugPrint('MediaUploadService.createMediaUpload called');
    debugPrint('Parameters:');
    debugPrint('  childId: $childId');
    debugPrint('  bucketName: $bucketName');
    debugPrint('  filePath: $filePath');
    debugPrint('  contentType: $contentType');
    debugPrint('  fileSize: $fileSize');
    debugPrint('  originalFilename: $originalFilename');

    try {
      final user = _auth.currentUser;
      debugPrint('Current user: ${user?.uid}');
      if (user == null) {
        debugPrint('User not authenticated');
        return null;
      }

      // Determine media type from content type
      final mediaType = _determineMediaType(contentType);
      debugPrint('Determined media type: $mediaType');

      // Construct media URI
      final mediaUri = 'gs://$bucketName/$filePath';
      debugPrint('Media URI: $mediaUri');

      // Create media upload document
      debugPrint('Building media upload document...');
      final mediaUploadData = {
        // Required fields
        'user_id': user.uid,
        'child_id': childId,
        'media_uri': mediaUri,
        'bucket_name': bucketName,
        'file_path': filePath,
        'media_type': mediaType.toString().split('.').last,
        'content_type': contentType,
        'processing_status': 'pending',
        'created_at': FieldValue.serverTimestamp(),
        'uploaded_at': FieldValue.serverTimestamp(),

        // Optional fields
        if (fileSize != null) 'file_size': fileSize,
        if (originalFilename != null) 'original_filename': originalFilename,
        if (customMetadata != null) 'custom_metadata': customMetadata,
        if (capturedAt != null) 'captured_at': Timestamp.fromDate(capturedAt),

        // Default values for optional fields
        'visibility': 'private',
        'shared_with': <String>[],
        'is_deleted': false,
        'is_archived': false,
        'is_favorite': false,
      };

      debugPrint('Media upload data prepared. Adding to Firestore...');
      debugPrint('Collection path: media_uploads');

      final docRef = await _mediaUploadsCollection.add(mediaUploadData);
      debugPrint('Successfully created media upload document: ${docRef.id}');
      return docRef.id;
    } catch (e, stackTrace) {
      debugPrint('ERROR in createMediaUpload:');
      debugPrint('Error type: ${e.runtimeType}');
      debugPrint('Error message: $e');
      debugPrint('Stack trace: $stackTrace');
      return null;
    }
  }

  MediaType _determineMediaType(String contentType) {
    if (contentType.startsWith('image/')) {
      return MediaType.image;
    } else if (contentType.startsWith('video/')) {
      return MediaType.video;
    } else {
      return MediaType.unknown;
    }
  }

  Future<MediaUpload?> getMediaUpload(String mediaUploadId) async {
    try {
      final doc = await _mediaUploadsCollection.doc(mediaUploadId).get();
      if (!doc.exists) return null;
      return MediaUpload.fromJson(doc.data()! as Map<String, dynamic>, doc.id);
    } catch (e) {
      debugPrint('Error getting media upload: $e');
      return null;
    }
  }

  Future<List<MediaUpload>> getUserMediaUploads() async {
    try {
      final user = _auth.currentUser;
      if (user == null) return [];

      final querySnapshot = await _mediaUploadsCollection
          .where('user_id', isEqualTo: user.uid)
          .orderBy('uploaded_at', descending: true)
          .get();

      return querySnapshot.docs
          .map(
            (doc) => MediaUpload.fromJson(
              doc.data()! as Map<String, dynamic>,
              doc.id,
            ),
          )
          .toList();
    } catch (e) {
      debugPrint('Error getting user media uploads: $e');
      return [];
    }
  }

  Future<List<MediaUpload>> getChildMediaUploads(String childId) async {
    try {
      final querySnapshot = await _mediaUploadsCollection
          .where('child_id', isEqualTo: childId)
          .orderBy('uploaded_at', descending: true)
          .get();

      return querySnapshot.docs
          .map(
            (doc) => MediaUpload.fromJson(
              doc.data()! as Map<String, dynamic>,
              doc.id,
            ),
          )
          .toList();
    } catch (e) {
      debugPrint('Error getting child media uploads: $e');
      return [];
    }
  }

  Future<List<MediaUpload>> getPendingMediaUploads() async {
    try {
      final user = _auth.currentUser;
      if (user == null) return [];

      final querySnapshot = await _mediaUploadsCollection
          .where('user_id', isEqualTo: user.uid)
          .where('processing_status', isEqualTo: 'pending')
          .orderBy('uploaded_at', descending: true)
          .get();

      return querySnapshot.docs
          .map(
            (doc) => MediaUpload.fromJson(
              doc.data()! as Map<String, dynamic>,
              doc.id,
            ),
          )
          .toList();
    } catch (e) {
      debugPrint('Error getting pending media uploads: $e');
      return [];
    }
  }

  Future<bool> updateMediaUploadStatus(
    String mediaUploadId,
    ProcessingStatus status, {
    String? episodeId,
    String? processingError,
  }) async {
    try {
      final updateData = <String, dynamic>{
        'processing_status': status.toString().split('.').last,
        'updated_at': FieldValue.serverTimestamp(),
      };

      if (status == ProcessingStatus.completed) {
        updateData['processed_at'] = FieldValue.serverTimestamp();
        if (episodeId != null) {
          updateData['episode_id'] = episodeId;
        }
      } else if (status == ProcessingStatus.failed && processingError != null) {
        updateData['processing_error'] = processingError;
      }

      await _mediaUploadsCollection.doc(mediaUploadId).update(updateData);
      return true;
    } catch (e) {
      debugPrint('Error updating media upload status: $e');
      return false;
    }
  }

  Future<bool> toggleFavorite(String mediaUploadId) async {
    try {
      final doc = await _mediaUploadsCollection.doc(mediaUploadId).get();
      if (!doc.exists) return false;

      final currentData = doc.data() as Map<String, dynamic>?;
      final isFavorite = currentData?['is_favorite'] as bool? ?? false;

      await _mediaUploadsCollection.doc(mediaUploadId).update({
        'is_favorite': !isFavorite,
        'updated_at': FieldValue.serverTimestamp(),
      });
      return true;
    } catch (e) {
      debugPrint('Error toggling favorite: $e');
      return false;
    }
  }

  Future<bool> archiveMediaUpload(String mediaUploadId) async {
    try {
      await _mediaUploadsCollection.doc(mediaUploadId).update({
        'is_archived': true,
        'updated_at': FieldValue.serverTimestamp(),
      });
      return true;
    } catch (e) {
      debugPrint('Error archiving media upload: $e');
      return false;
    }
  }

  Future<bool> deleteMediaUpload(String mediaUploadId) async {
    try {
      await _mediaUploadsCollection.doc(mediaUploadId).update({
        'is_deleted': true,
        'updated_at': FieldValue.serverTimestamp(),
      });
      return true;
    } catch (e) {
      debugPrint('Error deleting media upload: $e');
      return false;
    }
  }

  Stream<List<MediaUpload>> watchUserMediaUploads() {
    final user = _auth.currentUser;
    if (user == null) return Stream.value([]);

    return _mediaUploadsCollection
        .where('user_id', isEqualTo: user.uid)
        .where('is_deleted', isEqualTo: false)
        .orderBy('uploaded_at', descending: true)
        .snapshots()
        .map(
          (snapshot) => snapshot.docs
              .map(
                (doc) => MediaUpload.fromJson(
                  doc.data()! as Map<String, dynamic>,
                  doc.id,
                ),
              )
              .toList(),
        );
  }

  Stream<MediaUpload?> watchMediaUploadStatus(String mediaUploadId) {
    return _mediaUploadsCollection.doc(mediaUploadId).snapshots().map((
      snapshot,
    ) {
      if (!snapshot.exists) return null;
      return MediaUpload.fromJson(
        snapshot.data()! as Map<String, dynamic>,
        snapshot.id,
      );
    });
  }

  // Helper method to generate the recommended file path
  String generateFilePath({
    required String userId,
    required String childId,
    required String filename,
    DateTime? uploadDate,
  }) {
    final date = uploadDate ?? DateTime.now();
    final yearMonth = '${date.year}-${date.month.toString().padLeft(2, '0')}';
    return '$userId/$childId/$yearMonth/$filename';
  }

  // Get media uploads for display with optional child filter
  Future<List<MediaUpload>> getDisplayMediaUploads({String? childId}) async {
    try {
      final user = _auth.currentUser;
      if (user == null) return [];

      var query = _mediaUploadsCollection
          .where('user_id', isEqualTo: user.uid)
          .where('is_deleted', isEqualTo: false)
          .where('is_archived', isEqualTo: false);

      if (childId != null) {
        query = query.where('child_id', isEqualTo: childId);
      }

      final querySnapshot = await query
          .orderBy('captured_at', descending: true)
          .orderBy('uploaded_at', descending: true)
          .get();

      return querySnapshot.docs
          .map((doc) => MediaUpload.fromJson(
                doc.data() as Map<String, dynamic>,
                doc.id,
              ))
          .toList();
    } catch (e) {
      debugPrint('Error getting display media uploads: $e');
      return [];
    }
  }
}
