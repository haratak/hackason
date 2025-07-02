import 'dart:io';

import 'package:crypto/crypto.dart';
import 'package:exif/exif.dart';
import 'package:firebase_auth/firebase_auth.dart';
import 'package:firebase_storage/firebase_storage.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import 'package:kids_diary/models/media_upload.dart';
import 'package:kids_diary/services/media_upload_service.dart';
import 'package:mime/mime.dart';

class PhotoItem {
  final String id;
  final String url;
  final String path;
  final DateTime uploadedAt;
  final String? contentHash;
  final String? mediaUploadId;
  final String? childId;

  PhotoItem({
    required this.id,
    required this.url,
    required this.path,
    required this.uploadedAt,
    this.contentHash,
    this.mediaUploadId,
    this.childId,
  });
}

class StorageProvider extends ChangeNotifier {
  final FirebaseStorage _storage = FirebaseStorage.instanceFor(
    bucket: 'gs://hackason-464007.firebasestorage.app',
  );
  final ImagePicker _picker = ImagePicker();
  final MediaUploadService _mediaUploadService = MediaUploadService();

  List<MediaUpload> _mediaUploads = [];
  bool _isLoading = false;
  int _uploadProgress = 0;
  int _totalFiles = 0;
  String? _selectedChildId;

  List<MediaUpload> get mediaUploads => _mediaUploads;
  List<PhotoItem> get photos => _mediaUploads
      .map(
        (upload) => PhotoItem(
          id: upload.id,
          url: '', // Will be loaded from Storage
          path: upload.filePath,
          uploadedAt: upload.uploadedAt,
          mediaUploadId: upload.id,
          childId: upload.childId,
        ),
      )
      .toList();
  bool get isLoading => _isLoading;
  int get uploadProgress => _uploadProgress;
  int get totalFiles => _totalFiles;
  String? get selectedChildId => _selectedChildId;

  String? _getUserId() {
    final user = FirebaseAuth.instance.currentUser;
    return user?.uid;
  }

  void setSelectedChildId(String? childId) {
    _selectedChildId = childId;
    notifyListeners();
  }

  Future<void> loadPhotos() async {
    try {
      _isLoading = true;
      notifyListeners();

      // Load media uploads from Firestore
      _mediaUploads = await _mediaUploadService.getDisplayMediaUploads(
        childId: _selectedChildId,
      );

      // Filter by media type (images and videos only)
      _mediaUploads = _mediaUploads
          .where(
            (upload) =>
                upload.mediaType == MediaType.image ||
                upload.mediaType == MediaType.video,
          )
          .toList();

      debugPrint('Loaded ${_mediaUploads.length} media uploads');

      _isLoading = false;
      notifyListeners();
    } catch (e) {
      _isLoading = false;
      notifyListeners();
      debugPrint('Failed to load media uploads: $e');
      rethrow;
    }
  }

  Future<String> _calculateFileHash(File file) async {
    final bytes = await file.readAsBytes();
    final digest = sha256.convert(bytes);
    return digest.toString();
  }

  Future<bool> _isDuplicatePhoto(String contentHash) async {
    // For now, skip duplicate check since MediaUpload doesn't store content hash
    // TODO: Add content hash to MediaUpload model if needed
    return false;
  }

  Future<DateTime?> _extractCapturedDate(File file) async {
    try {
      final bytes = await file.readAsBytes();
      final data = await readExifFromBytes(bytes);

      if (data.isEmpty) {
        debugPrint('No EXIF data found in image');
        return null;
      }

      // Try to get date from EXIF
      final dateTimeOriginal = data['EXIF DateTimeOriginal'];
      final dateTimeDigitized = data['EXIF DateTimeDigitized'];
      final dateTime = data['Image DateTime'];

      final dateStr =
          dateTimeOriginal?.toString() ??
          dateTimeDigitized?.toString() ??
          dateTime?.toString();

      if (dateStr != null) {
        // EXIF date format: "2023:12:25 10:30:45"
        try {
          final parts = dateStr.split(' ');
          if (parts.length == 2) {
            final dateParts = parts[0].split(':');
            final timeParts = parts[1].split(':');

            if (dateParts.length == 3 && timeParts.length == 3) {
              return DateTime(
                int.parse(dateParts[0]),
                int.parse(dateParts[1]),
                int.parse(dateParts[2]),
                int.parse(timeParts[0]),
                int.parse(timeParts[1]),
                int.parse(timeParts[2]),
              );
            }
          }
        } catch (e) {
          debugPrint('Error parsing EXIF date: $e');
        }
      }

      return null;
    } catch (e) {
      debugPrint('Error reading EXIF data: $e');
      return null;
    }
  }

  Future<DateTime?> _extractVideoDate(File file) async {
    try {
      // For videos, we'll use file modification date as a fallback
      // In a production app, you might want to use platform-specific APIs
      // or parse video metadata using a more sophisticated approach

      final stat = await file.stat();
      final dates = [
        stat.modified,
        stat.accessed,
        // stat.created is not available on all platforms
      ];

      // Use the earliest date as it's more likely to be closer to capture time
      DateTime? captureDate;
      for (final date in dates) {
        if (captureDate == null || date.isBefore(captureDate)) {
          captureDate = date;
        }
      }

      // Sanity check - if the date is in the future, don't use it
      if (captureDate != null && captureDate.isAfter(DateTime.now())) {
        debugPrint('Video date is in the future, ignoring: $captureDate');
        return null;
      }

      return captureDate;
    } catch (e) {
      debugPrint('Error extracting video date: $e');
      return null;
    }
  }

  Future<void> uploadPhotos() async {
    final userId = _getUserId();
    if (userId == null) {
      debugPrint('No user ID found - user must be logged in to upload photos');
      return;
    }

    try {
      final images = await _picker.pickMultipleMedia();
      if (images.isEmpty) {
        debugPrint('User cancelled media picker');
        return;
      }

      _isLoading = true;
      _uploadProgress = 0;
      _totalFiles = images.length;
      notifyListeners();

      debugPrint('Storage bucket: ${_storage.bucket}');
      debugPrint('Uploading ${images.length} files');

      var skippedDuplicates = 0;
      var actualUploaded = 0;

      for (var i = 0; i < images.length; i++) {
        final image = images[i];
        debugPrint('Processing file ${i + 1}/${images.length}: ${image.name}');
        try {
          final file = File(image.path);

          // Calculate file hash for duplicate detection
          final contentHash = await _calculateFileHash(file);
          debugPrint('File hash calculated: ${contentHash.substring(0, 8)}...');

          // Check for duplicates
          if (await _isDuplicatePhoto(contentHash)) {
            debugPrint('Skipping duplicate photo: ${image.name}');
            skippedDuplicates++;
            _uploadProgress++;
            notifyListeners();
            continue;
          }

          final fileName =
              '${DateTime.now().millisecondsSinceEpoch}_${image.name}';
          debugPrint(
            'Uploading file ${_uploadProgress + 1}/$_totalFiles: $fileName',
          );

          // Use recommended path convention if child is selected
          String uploadPath;
          if (_selectedChildId != null) {
            final now = DateTime.now();
            final yearMonth =
                '${now.year}-${now.month.toString().padLeft(2, '0')}';
            uploadPath = '$userId/$_selectedChildId/$yearMonth/$fileName';
          } else {
            uploadPath = 'users/$userId/$fileName';
          }

          final ref = _storage.ref(uploadPath);
          debugPrint('Reference path: ${ref.fullPath}');

          // Upload with metadata
          final metadata = SettableMetadata(
            customMetadata: {
              'contentHash': contentHash,
              'originalName': image.name,
            },
          );

          final uploadTask = ref.putFile(file, metadata);

          // Track upload progress
          uploadTask.snapshotEvents.listen((TaskSnapshot snapshot) {
            if (snapshot.state == TaskState.running) {
              if (snapshot.totalBytes > 0) {
                final progress =
                    snapshot.bytesTransferred / snapshot.totalBytes;
                debugPrint(
                  'Upload progress for file ${i + 1}: ${(progress * 100).toStringAsFixed(1)}%',
                );
              }
            } else if (snapshot.state == TaskState.success) {
              debugPrint('Upload successful for file ${i + 1}');
            } else if (snapshot.state == TaskState.error) {
              debugPrint('Upload error for file ${i + 1}');
            }
          });

          // Wait for upload to complete
          final finalSnapshot = await uploadTask;

          if (finalSnapshot.state != TaskState.success) {
            throw Exception('Upload failed with state: ${finalSnapshot.state}');
          }

          // Verify upload by getting download URL
          try {
            final downloadUrl = await ref.getDownloadURL();
            debugPrint(
              'File uploaded successfully, download URL: ${downloadUrl.substring(0, 50)}...',
            );
          } catch (e) {
            debugPrint('Warning: Could not get download URL: $e');
          }

          actualUploaded++;
          _uploadProgress++;
          debugPrint(
            'Upload completed: $_uploadProgress/$_totalFiles (actual uploads: $actualUploaded)',
          );
          notifyListeners();

          // Save media upload metadata to Firestore
          debugPrint('Starting Firestore metadata save...');
          try {
            if (_selectedChildId != null) {
              debugPrint('Selected child ID: $_selectedChildId');

              // Determine content type
              final contentType =
                  lookupMimeType(file.path) ?? 'application/octet-stream';
              debugPrint('Content type: $contentType');

              // Extract captured date
              DateTime? capturedAt;
              if (contentType.startsWith('image/')) {
                capturedAt = await _extractCapturedDate(file);
                debugPrint('Captured date from EXIF: $capturedAt');
              } else if (contentType.startsWith('video/')) {
                capturedAt = await _extractVideoDate(file);
                debugPrint('Video date from file: $capturedAt');
              }

              // Generate file path following the recommended convention
              final userId = _getUserId()!;
              debugPrint('User ID: $userId');

              final now = DateTime.now();
              final yearMonth =
                  '${now.year}-${now.month.toString().padLeft(2, '0')}';
              final fullPath = '$userId/$_selectedChildId/$yearMonth/$fileName';
              debugPrint('Full path: $fullPath');

              // Extract bucket name without gs:// prefix
              final bucketName = _storage.bucket.replaceFirst('gs://', '');
              debugPrint('Bucket name: $bucketName');

              debugPrint('Calling createMediaUpload...');
              final mediaUploadId = await _mediaUploadService.createMediaUpload(
                childId: _selectedChildId!,
                bucketName: bucketName,
                filePath: fullPath,
                contentType: contentType,
                fileSize: file.lengthSync(),
                originalFilename: image.name,
                customMetadata: {
                  'contentHash': contentHash,
                  'device': 'mobile',
                },
                capturedAt: capturedAt,
              );
              debugPrint(
                'Media upload metadata saved successfully. ID: $mediaUploadId',
              );
            } else {
              debugPrint('No child selected, skipping Firestore metadata save');
            }
          } catch (e, stackTrace) {
            debugPrint('ERROR saving media upload metadata:');
            debugPrint('Error type: ${e.runtimeType}');
            debugPrint('Error message: $e');
            debugPrint('Stack trace: $stackTrace');
            // Continue even if metadata save fails
          }
          debugPrint('Firestore metadata save completed');

          // Small delay between uploads
          debugPrint('Waiting 100ms before next file...');
          await Future<void>.delayed(const Duration(milliseconds: 100));

          debugPrint('=== File ${i + 1} processing completed ===');
        } on Exception catch (e) {
          debugPrint('Failed to upload file ${i + 1}: $e');
          _uploadProgress++;
          notifyListeners();
          // Continue with next file even if one fails
        }

        debugPrint('Moving to next file in loop...');
      }

      debugPrint('All files processed. Exiting upload loop.');

      debugPrint('=== Upload Summary ===');
      debugPrint('Total files selected: ${images.length}');
      debugPrint('Files uploaded: $actualUploaded');
      debugPrint('Duplicates skipped: $skippedDuplicates');
      debugPrint('Upload progress counter: $_uploadProgress');
      debugPrint('====================');

      // Small delay to ensure Firebase has processed all uploads
      await Future<void>.delayed(const Duration(milliseconds: 500));

      // Reset progress
      _uploadProgress = 0;
      _totalFiles = 0;
      _isLoading = false;
      notifyListeners();

      // Reload photos
      await loadPhotos();
    } catch (e) {
      _isLoading = false;
      _uploadProgress = 0;
      _totalFiles = 0;
      notifyListeners();
      debugPrint('Failed to upload photo: $e');
      throw Exception('Failed to upload photo: $e');
    }
  }

  Future<void> deletePhoto(PhotoItem photo) async {
    try {
      _isLoading = true;
      notifyListeners();

      final ref = _storage.ref(photo.path);
      await ref.delete();

      // Delete media upload metadata if exists
      if (photo.mediaUploadId != null) {
        try {
          await _mediaUploadService.deleteMediaUpload(photo.mediaUploadId!);
          debugPrint('Media upload metadata deleted for photo: ${photo.id}');
        } on Exception catch (e) {
          debugPrint('Failed to delete media upload metadata: $e');
          // Continue even if metadata deletion fails
        }
      }

      // Reload photos to reflect the deletion
      await loadPhotos();

      _isLoading = false;
      notifyListeners();
    } catch (e) {
      _isLoading = false;
      notifyListeners();
      debugPrint('Failed to delete photo: $e');
      throw Exception('Failed to delete photo: $e');
    }
  }
}
