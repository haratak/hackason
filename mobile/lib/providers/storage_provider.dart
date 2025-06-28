import 'dart:io';

import 'package:crypto/crypto.dart';
import 'package:firebase_auth/firebase_auth.dart';
import 'package:firebase_storage/firebase_storage.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';

class PhotoItem {
  final String id;
  final String url;
  final String path;
  final DateTime uploadedAt;
  final int? fileSize;
  final String? contentHash;
  
  PhotoItem({
    required this.id,
    required this.url,
    required this.path,
    required this.uploadedAt,
    this.fileSize,
    this.contentHash,
  });
}

class StorageProvider extends ChangeNotifier {
  final FirebaseStorage _storage = FirebaseStorage.instanceFor(
    bucket: 'gs://hackason-464007.firebasestorage.app',
  );
  final ImagePicker _picker = ImagePicker();
  
  List<PhotoItem> _photos = [];
  bool _isLoading = false;
  int _uploadProgress = 0;
  int _totalFiles = 0;
  
  List<PhotoItem> get photos => _photos;
  bool get isLoading => _isLoading;
  int get uploadProgress => _uploadProgress;
  int get totalFiles => _totalFiles;
  
  String? _getUserId() {
    final user = FirebaseAuth.instance.currentUser;
    return user?.uid;
  }
  
  Future<void> loadPhotos() async {
    final userId = _getUserId();
    if (userId == null) return;
    
    try {
      _isLoading = true;
      notifyListeners();
      
      final ref = _storage.ref('users/$userId');
      
      try {
        final result = await ref.listAll();
        
        _photos = [];
        for (final item in result.items) {
          final url = await item.getDownloadURL();
          final metadata = await item.getMetadata();
          
          _photos.add(PhotoItem(
            id: item.name,
            url: url,
            path: item.fullPath,
            uploadedAt: metadata.timeCreated ?? DateTime.now(),
            fileSize: metadata.size,
            contentHash: metadata.customMetadata?['contentHash'],
          ));
        }
        
        _photos.sort((a, b) => b.uploadedAt.compareTo(a.uploadedAt));
      } on FirebaseException catch (e) {
        if (e.code == 'object-not-found') {
          // This is expected when no photos exist yet
          debugPrint('No photos found for user - this is normal for new users');
          _photos = [];
        } else {
          debugPrint('Firebase error while loading photos: $e');
          rethrow;
        }
      }
      
      _isLoading = false;
      notifyListeners();
    } catch (e) {
      _isLoading = false;
      notifyListeners();
      debugPrint('Failed to load photos: $e');
      rethrow;
    }
  }
  
  Future<String> _calculateFileHash(File file) async {
    final bytes = await file.readAsBytes();
    final digest = sha256.convert(bytes);
    return digest.toString();
  }
  
  Future<bool> _isDuplicatePhoto(String contentHash) async {
    // Check if any existing photo has the same hash
    return _photos.any((photo) => photo.contentHash == contentHash);
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
      
      for (var i = 0; i < images.length; i++) {
        final image = images[i];
        try {
          final file = File(image.path);
          
          // Calculate file hash for duplicate detection
          final contentHash = await _calculateFileHash(file);
          
          // Check for duplicates
          if (await _isDuplicatePhoto(contentHash)) {
            debugPrint('Skipping duplicate photo: ${image.name}');
            skippedDuplicates++;
            _uploadProgress++;
            notifyListeners();
            continue;
          }
          
          final fileName = '${DateTime.now().millisecondsSinceEpoch}_${image.name}';
          debugPrint('Uploading file ${_uploadProgress + 1}/$_totalFiles: $fileName');
          
          final ref = _storage.ref('users/$userId/$fileName');
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
              final progress = snapshot.bytesTransferred / snapshot.totalBytes;
              debugPrint('Upload progress for file ${i + 1}: ${(progress * 100).toStringAsFixed(1)}%');
            }
          });
          
          await uploadTask.whenComplete(() {
            _uploadProgress++;
            debugPrint('Upload completed: $_uploadProgress/$_totalFiles');
            notifyListeners();
          });
          
          // Small delay between uploads
          await Future<void>.delayed(const Duration(milliseconds: 100));
        } on Exception catch (e) {
          debugPrint('Failed to upload file: $e');
          _uploadProgress++;
          notifyListeners();
          // Continue with next file even if one fails
        }
      }
      
      if (skippedDuplicates > 0) {
        debugPrint('Skipped $skippedDuplicates duplicate photos');
      }
      
      debugPrint('All uploads completed: ${_uploadProgress - skippedDuplicates}/$_totalFiles files uploaded successfully');
      
      // Small delay to ensure Firebase has processed all uploads
      await Future<void>.delayed(const Duration(milliseconds: 500));
      
      // Reset progress
      _uploadProgress = 0;
      _totalFiles = 0;
      
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
      
      _photos.removeWhere((p) => p.id == photo.id);
      
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
