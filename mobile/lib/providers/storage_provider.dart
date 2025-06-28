import 'dart:io';

import 'package:firebase_auth/firebase_auth.dart';
import 'package:firebase_storage/firebase_storage.dart';
import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';

class PhotoItem {
  final String id;
  final String url;
  final String path;
  final DateTime uploadedAt;
  
  PhotoItem({
    required this.id,
    required this.url,
    required this.path,
    required this.uploadedAt,
  });
}

class StorageProvider extends ChangeNotifier {
  final FirebaseStorage _storage = FirebaseStorage.instance;
  final ImagePicker _picker = ImagePicker();
  
  List<PhotoItem> _photos = [];
  bool _isLoading = false;
  
  List<PhotoItem> get photos => _photos;
  bool get isLoading => _isLoading;
  
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
        ));
      }
      
      _photos.sort((a, b) => b.uploadedAt.compareTo(a.uploadedAt));
      
      _isLoading = false;
      notifyListeners();
    } catch (e) {
      _isLoading = false;
      notifyListeners();
      throw Exception('Failed to load photos: $e');
    }
  }
  
  Future<void> uploadPhoto() async {
    final userId = _getUserId();
    if (userId == null) return;
    
    try {
      final image = await _picker.pickImage(source: ImageSource.gallery);
      if (image == null) return;
      
      _isLoading = true;
      notifyListeners();
      
      final file = File(image.path);
      final fileName = '${DateTime.now().millisecondsSinceEpoch}_${image.name}';
      final ref = _storage.ref('users/$userId/$fileName');
      
      await ref.putFile(file);
      
      await loadPhotos();
    } catch (e) {
      _isLoading = false;
      notifyListeners();
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
      throw Exception('Failed to delete photo: $e');
    }
  }
}
