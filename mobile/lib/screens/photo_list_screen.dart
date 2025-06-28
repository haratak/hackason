import 'dart:async';

import 'package:flutter/material.dart';
import 'package:mobile/providers/storage_provider.dart';
import 'package:provider/provider.dart';

class PhotoListScreen extends StatefulWidget {
  const PhotoListScreen({super.key});

  @override
  State<PhotoListScreen> createState() => _PhotoListScreenState();
}

class _PhotoListScreenState extends State<PhotoListScreen> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      Provider.of<StorageProvider>(
        context,
        listen: false,
      ).loadPhotos().catchError((Object e) {
        debugPrint('Error loading photos on init: $e');
        // Error is already handled in the provider
      });
    });
  }

  @override
  Widget build(BuildContext context) {
    final storageProvider = Provider.of<StorageProvider>(context);

    return Scaffold(
      appBar: AppBar(
        title: const Text('写真管理'),
      ),
      body: storageProvider.isLoading
          ? const Center(child: CircularProgressIndicator())
          : storageProvider.photos.isEmpty
          ? const Center(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Icon(
                    Icons.photo_library_outlined,
                    size: 64,
                    color: Colors.grey,
                  ),
                  SizedBox(height: 16),
                  Text(
                    '写真がありません',
                    style: TextStyle(
                      fontSize: 16,
                      color: Colors.grey,
                    ),
                  ),
                  SizedBox(height: 8),
                  Text(
                    '右下のボタンから写真を追加してください',
                    style: TextStyle(
                      fontSize: 14,
                      color: Colors.grey,
                    ),
                  ),
                ],
              ),
            )
          : RefreshIndicator(
              onRefresh: storageProvider.loadPhotos,
              child: GridView.builder(
                padding: const EdgeInsets.all(8),
                gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                  crossAxisCount: 3,
                  crossAxisSpacing: 8,
                  mainAxisSpacing: 8,
                ),
                itemCount: storageProvider.photos.length,
                itemBuilder: (context, index) {
                  final photo = storageProvider.photos[index];
                  return GestureDetector(
                    onLongPress: () => _showDeleteDialog(context, photo),
                    child: Stack(
                      fit: StackFit.expand,
                      children: [
                        ClipRRect(
                          borderRadius: BorderRadius.circular(8),
                          child: Image.network(
                            photo.url,
                            fit: BoxFit.cover,
                            loadingBuilder: (context, child, loadingProgress) {
                              if (loadingProgress == null) return child;
                              return Container(
                                color: Colors.grey[200],
                                child: const Center(
                                  child: CircularProgressIndicator(),
                                ),
                              );
                            },
                            errorBuilder: (context, error, stackTrace) {
                              return Container(
                                color: Colors.grey[300],
                                child: const Icon(
                                  Icons.error_outline,
                                  color: Colors.grey,
                                ),
                              );
                            },
                          ),
                        ),
                        Positioned(
                          right: 4,
                          top: 4,
                          child: Container(
                            decoration: BoxDecoration(
                              color: Colors.black54,
                              borderRadius: BorderRadius.circular(4),
                            ),
                            padding: const EdgeInsets.all(4),
                            child: Text(
                              '${photo.uploadedAt.month}/${photo.uploadedAt.day}',
                              style: const TextStyle(
                                color: Colors.white,
                                fontSize: 10,
                              ),
                            ),
                          ),
                        ),
                      ],
                    ),
                  );
                },
              ),
            ),
      floatingActionButton: FloatingActionButton(
        onPressed: () async {
          unawaited(
            showDialog<void>(
              context: context,
              barrierDismissible: false,
              builder: (BuildContext dialogContext) {
                return AlertDialog(
                  content: Consumer<StorageProvider>(
                    builder: (context, provider, child) {
                      return Column(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          const CircularProgressIndicator(),
                          const SizedBox(height: 16),
                          if (provider.totalFiles > 0) ...[
                            Text(
                              'アップロード中... ${provider.uploadProgress}/${provider.totalFiles}',
                            ),
                            const SizedBox(height: 8),
                            LinearProgressIndicator(
                              value: provider.totalFiles > 0
                                  ? provider.uploadProgress /
                                        provider.totalFiles
                                  : null,
                            ),
                            const SizedBox(height: 4),
                            Text(
                              '${((provider.uploadProgress / provider.totalFiles) * 100).toStringAsFixed(0)}%',
                              style: const TextStyle(fontSize: 12),
                            ),
                          ] else
                            const Text('写真を選択中...'),
                        ],
                      );
                    },
                  ),
                );
              },
            ),
          );

          try {
            await storageProvider.uploadPhotos();
            if (mounted) {
              Navigator.of(context).pop();
            }
          } on Exception catch (e) {
            debugPrint('Failed to upload photo: $e');
            if (mounted) {
              Navigator.of(context).pop();
              ScaffoldMessenger.of(context).showSnackBar(
                SnackBar(
                  content: Text('写真のアップロードに失敗しました: $e'),
                  backgroundColor: Colors.red,
                ),
              );
            }
          }
        },
        child: const Icon(Icons.add_photo_alternate),
      ),
    );
  }

  void _showDeleteDialog(BuildContext context, PhotoItem photo) {
    showDialog<void>(
      context: context,
      builder: (BuildContext context) {
        return AlertDialog(
          title: const Text('写真を削除'),
          content: const Text('この写真を削除しますか？'),
          actions: [
            TextButton(
              onPressed: () => Navigator.of(context).pop(),
              child: const Text('キャンセル'),
            ),
            TextButton(
              onPressed: () async {
                Navigator.of(context).pop();
                try {
                  await Provider.of<StorageProvider>(
                    context,
                    listen: false,
                  ).deletePhoto(photo);
                } on Exception catch (e) {
                  debugPrint('Failed to delete photo: $e');
                  if (mounted) {
                    ScaffoldMessenger.of(context).showSnackBar(
                      SnackBar(
                        content: Text('写真の削除に失敗しました: $e'),
                        backgroundColor: Colors.red,
                      ),
                    );
                  }
                }
              },
              child: const Text(
                '削除',
                style: TextStyle(color: Colors.red),
              ),
            ),
          ],
        );
      },
    );
  }
}
