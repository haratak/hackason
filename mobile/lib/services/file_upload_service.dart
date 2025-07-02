import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:firebase_auth/firebase_auth.dart';
import 'package:flutter/foundation.dart';
import 'package:kids_diary/models/file_upload.dart';
import 'package:kids_diary/services/children_service.dart';

class FileUploadService {
  final FirebaseFirestore _firestore = FirebaseFirestore.instance;
  final FirebaseAuth _auth = FirebaseAuth.instance;
  final ChildrenService _childrenService = ChildrenService();

  CollectionReference get _fileUploadsCollection =>
      _firestore.collection('file_uploads');

  Future<String?> saveFileUploadMetadata({
    required String bucketUrl,
    required String filePath,
    String? childId,
    Map<String, dynamic>? additionalMetadata,
  }) async {
    try {
      final user = _auth.currentUser;
      if (user == null) {
        debugPrint('User not authenticated');
        return null;
      }

      // If childId is provided, verify access
      if (childId != null) {
        final child = await _childrenService.getChild(childId);
        if (child == null) {
          debugPrint('Invalid child ID or no access');
          return null;
        }
      }

      final fileUploadData = {
        'bucketUrl': bucketUrl,
        'filePath': filePath,
        'uploadedAt': Timestamp.fromDate(DateTime.now()),
        'userId': user.uid,
        'childId': childId,
        'metadata': additionalMetadata,
      };

      final docRef = await _fileUploadsCollection.add(fileUploadData);
      return docRef.id;
    } on Exception catch (e) {
      debugPrint('Error saving file upload metadata: $e');
      return null;
    }
  }

  Future<FileUpload?> getFileUploadMetadata(String fileUploadId) async {
    try {
      final doc = await _fileUploadsCollection.doc(fileUploadId).get();
      if (!doc.exists) return null;
      return FileUpload.fromFirestore(doc);
    } on Exception catch (e) {
      debugPrint('Error getting file upload metadata: $e');
      return null;
    }
  }

  Future<FileUpload?> getFileUploadByPath(String filePath) async {
    try {
      final querySnapshot = await _fileUploadsCollection
          .where('filePath', isEqualTo: filePath)
          .limit(1)
          .get();

      if (querySnapshot.docs.isEmpty) return null;
      return FileUpload.fromFirestore(querySnapshot.docs.first);
    } on Exception catch (e) {
      debugPrint('Error getting file upload by path: $e');
      return null;
    }
  }

  Future<List<FileUpload>> getUserFileUploads() async {
    try {
      final user = _auth.currentUser;
      if (user == null) return [];

      final querySnapshot = await _fileUploadsCollection
          .where('userId', isEqualTo: user.uid)
          .orderBy('uploadedAt', descending: true)
          .get();

      return querySnapshot.docs.map(FileUpload.fromFirestore).toList();
    } on Exception catch (e) {
      debugPrint('Error getting user file uploads: $e');
      return [];
    }
  }

  Future<List<FileUpload>> getChildFileUploads(String childId) async {
    try {
      // Verify access to child
      final child = await _childrenService.getChild(childId);
      if (child == null) return [];

      final querySnapshot = await _fileUploadsCollection
          .where('childId', isEqualTo: childId)
          .orderBy('uploadedAt', descending: true)
          .get();

      return querySnapshot.docs.map(FileUpload.fromFirestore).toList();
    } on Exception catch (e) {
      debugPrint('Error getting child file uploads: $e');
      return [];
    }
  }

  Future<bool> updateFileUploadMetadata(
    String fileUploadId,
    Map<String, dynamic> metadata,
  ) async {
    try {
      await _fileUploadsCollection.doc(fileUploadId).update({
        'metadata': metadata,
      });
      return true;
    } on Exception catch (e) {
      debugPrint('Error updating file upload metadata: $e');
      return false;
    }
  }

  Future<bool> deleteFileUploadMetadata(String fileUploadId) async {
    try {
      // Get the file upload to verify ownership
      final fileUpload = await getFileUploadMetadata(fileUploadId);
      if (fileUpload == null) return false;

      final user = _auth.currentUser;
      if (user == null || fileUpload.userId != user.uid) {
        debugPrint('User does not have permission to delete this file upload');
        return false;
      }

      await _fileUploadsCollection.doc(fileUploadId).delete();
      return true;
    } on Exception catch (e) {
      debugPrint('Error deleting file upload metadata: $e');
      return false;
    }
  }

  Stream<List<FileUpload>> watchUserFileUploads() {
    final user = _auth.currentUser;
    if (user == null) return Stream.value([]);

    return _fileUploadsCollection
        .where('userId', isEqualTo: user.uid)
        .orderBy('uploadedAt', descending: true)
        .snapshots()
        .map(
          (snapshot) => snapshot.docs.map(FileUpload.fromFirestore).toList(),
        );
  }

  Stream<List<FileUpload>> watchChildFileUploads(String childId) {
    return _childrenService.watchChild(childId).asyncMap((child) async {
      if (child == null) return [];

      final querySnapshot = await _fileUploadsCollection
          .where('childId', isEqualTo: childId)
          .orderBy('uploadedAt', descending: true)
          .get();

      return querySnapshot.docs.map(FileUpload.fromFirestore).toList();
    });
  }
}
