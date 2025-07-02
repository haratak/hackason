import 'dart:convert';
import 'dart:io';

import 'package:crypto/crypto.dart';
import 'package:flutter/foundation.dart';
import 'package:path_provider/path_provider.dart';
import 'package:video_thumbnail/video_thumbnail.dart';

class VideoThumbnailService {
  static final VideoThumbnailService _instance = VideoThumbnailService._internal();
  factory VideoThumbnailService() => _instance;
  VideoThumbnailService._internal();

  // メモリキャッシュ
  final Map<String, Uint8List> _memoryCache = {};
  
  // ディスクキャッシュのディレクトリ
  Future<Directory> get _cacheDirectory async {
    final appDir = await getApplicationDocumentsDirectory();
    final cacheDir = Directory('${appDir.path}/video_thumbnails');
    if (!await cacheDir.exists()) {
      await cacheDir.create(recursive: true);
    }
    return cacheDir;
  }
  
  // URLからキャッシュキーを生成
  String _getCacheKey(String videoUrl) {
    final bytes = utf8.encode(videoUrl);
    final digest = sha256.convert(bytes);
    return digest.toString();
  }
  
  // キャッシュファイルのパスを取得
  Future<File> _getCacheFile(String cacheKey) async {
    final dir = await _cacheDirectory;
    return File('${dir.path}/$cacheKey.jpg');
  }
  
  // サムネイルを取得（キャッシュ対応）
  Future<Uint8List?> getThumbnail(String videoUrl) async {
    try {
      final cacheKey = _getCacheKey(videoUrl);
      
      // 1. メモリキャッシュをチェック
      if (_memoryCache.containsKey(cacheKey)) {
        debugPrint('Thumbnail found in memory cache');
        return _memoryCache[cacheKey];
      }
      
      // 2. ディスクキャッシュをチェック
      final cacheFile = await _getCacheFile(cacheKey);
      if (await cacheFile.exists()) {
        debugPrint('Thumbnail found in disk cache');
        final bytes = await cacheFile.readAsBytes();
        _memoryCache[cacheKey] = bytes;
        return bytes;
      }
      
      // 3. 新規生成
      debugPrint('Generating new thumbnail for: $videoUrl');
      final thumbnail = await VideoThumbnail.thumbnailData(
        video: videoUrl,
        imageFormat: ImageFormat.JPEG,
        maxWidth: 400,
        quality: 85,
      );
      
      if (thumbnail != null) {
        // キャッシュに保存
        _memoryCache[cacheKey] = thumbnail;
        await cacheFile.writeAsBytes(thumbnail);
        debugPrint('Thumbnail generated and cached');
        return thumbnail;
      }
      
      return null;
    } catch (e) {
      debugPrint('Error generating thumbnail: $e');
      return null;
    }
  }
  
  // キャッシュクリア
  Future<void> clearCache() async {
    _memoryCache.clear();
    try {
      final dir = await _cacheDirectory;
      if (await dir.exists()) {
        await dir.delete(recursive: true);
      }
    } catch (e) {
      debugPrint('Error clearing cache: $e');
    }
  }
  
  // 古いキャッシュを削除（30日以上前のファイル）
  Future<void> cleanOldCache() async {
    try {
      final dir = await _cacheDirectory;
      if (!await dir.exists()) return;
      
      final now = DateTime.now();
      final files = await dir.list().toList();
      
      for (final file in files) {
        if (file is File) {
          final stat = await file.stat();
          final age = now.difference(stat.modified);
          if (age.inDays > 30) {
            await file.delete();
            debugPrint('Deleted old thumbnail cache: ${file.path}');
          }
        }
      }
    } catch (e) {
      debugPrint('Error cleaning old cache: $e');
    }
  }
}
