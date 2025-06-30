import 'dart:async';

import 'package:firebase_storage/firebase_storage.dart';
import 'package:flutter/material.dart';
import 'package:kids_diary/models/child.dart';
import 'package:kids_diary/models/media_upload.dart';
import 'package:kids_diary/providers/children_provider.dart';
import 'package:kids_diary/providers/family_provider.dart';
import 'package:kids_diary/providers/storage_provider.dart';
import 'package:kids_diary/screens/home_screen.dart';
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

      Provider.of<ChildrenProvider>(
        context,
        listen: false,
      ).loadChildren().catchError((Object e) {
        debugPrint('Error loading children on init: $e');
        // Error is already handled in the provider
      });
    });
  }

  @override
  Widget build(BuildContext context) {
    final storageProvider = Provider.of<StorageProvider>(context);
    final childrenProvider = Provider.of<ChildrenProvider>(context);
    final familyProvider = Provider.of<FamilyProvider>(context);

    // Check if family and children are registered
    if (!familyProvider.hasFamily || !childrenProvider.hasChildren) {
      return Scaffold(
        appBar: AppBar(
          title: const Text('写真管理'),
        ),
        body: Center(
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              const Icon(
                Icons.warning_amber_rounded,
                size: 80,
                color: Colors.orange,
              ),
              const SizedBox(height: 24),
              const Text(
                '写真をアップロードする前に',
                style: TextStyle(
                  fontSize: 20,
                  fontWeight: FontWeight.bold,
                ),
              ),
              const SizedBox(height: 16),
              const Text(
                'ファミリーとお子様の情報を\n登録してください',
                textAlign: TextAlign.center,
                style: TextStyle(
                  fontSize: 16,
                  color: Colors.grey,
                ),
              ),
              const SizedBox(height: 32),
              ElevatedButton.icon(
                onPressed: () {
                  // Navigate to family tab (index 2)
                  HomeScreen.of(context)?.navigateToTab(2);
                },
                icon: const Icon(Icons.family_restroom),
                label: const Text('ファミリー設定へ'),
              ),
            ],
          ),
        ),
      );
    }

    return Scaffold(
      appBar: AppBar(
        title: const Text('写真管理'),
        actions: [
          if (childrenProvider.hasChildren)
            PopupMenuButton<String?>(
              icon: Icon(
                storageProvider.selectedChildId != null
                    ? Icons.child_care
                    : Icons.child_care_outlined,
              ),
              onSelected: storageProvider.setSelectedChildId,
              itemBuilder: (context) => [
                const PopupMenuItem<String?>(
                  child: Text('全員'),
                ),
                ...childrenProvider.children.map<PopupMenuItem<String?>>(
                  (child) => PopupMenuItem<String?>(
                    value: child.id,
                    child: Text(child.nickname ?? child.name),
                  ),
                ),
              ],
            ),
        ],
      ),
      body: storageProvider.isLoading
          ? const Center(child: CircularProgressIndicator())
          : storageProvider.mediaUploads.isEmpty
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
              child: _buildGroupedPhotoList(storageProvider, childrenProvider),
            ),
      floatingActionButton: FloatingActionButton(
        onPressed: () async {
          // Show child selection dialog if children exist
          if (childrenProvider.hasChildren &&
              storageProvider.selectedChildId == null) {
            final selectedChildId = await _showChildSelectionDialog(
              context,
              childrenProvider,
            );
            if (selectedChildId != null) {
              storageProvider.setSelectedChildId(
                selectedChildId == '' ? null : selectedChildId,
              );
            }
          }
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

  void _showDeleteDialog(BuildContext context, MediaUpload mediaUpload) {
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
                  // TODO: Implement delete for media uploads
                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(
                      content: Text('削除機能は準備中です'),
                    ),
                  );
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

  String _getChildName(ChildrenProvider provider, String childId) {
    final child = provider.getChildById(childId);
    return child?.nickname ?? child?.name ?? '不明';
  }

  Widget _buildGroupedPhotoList(
    StorageProvider storageProvider,
    ChildrenProvider childrenProvider,
  ) {
    // Group media uploads by month
    final groupedUploads = <String, List<MediaUpload>>{};
    
    for (final upload in storageProvider.mediaUploads) {
      // Use captured date if available, otherwise use upload date
      final date = upload.capturedAt ?? upload.uploadedAt ?? DateTime.now();
      final monthKey = '${date.year}年${date.month}月';
      
      if (!groupedUploads.containsKey(monthKey)) {
        groupedUploads[monthKey] = [];
      }
      groupedUploads[monthKey]!.add(upload);
    }
    
    // Sort months in descending order
    final sortedMonths = groupedUploads.keys.toList()
      ..sort((a, b) => b.compareTo(a));
    
    return CustomScrollView(
      slivers: [
        for (final month in sortedMonths) ...[
          SliverPadding(
            padding: const EdgeInsets.fromLTRB(16, 16, 16, 8),
            sliver: SliverToBoxAdapter(
              child: Text(
                month,
                style: const TextStyle(
                  fontSize: 20,
                  fontWeight: FontWeight.bold,
                ),
              ),
            ),
          ),
          SliverPadding(
            padding: const EdgeInsets.symmetric(horizontal: 8),
            sliver: SliverGrid(
              gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                crossAxisCount: 3,
                crossAxisSpacing: 8,
                mainAxisSpacing: 8,
              ),
              delegate: SliverChildBuilderDelegate(
                (context, index) {
                  final mediaUpload = groupedUploads[month]![index];
                  return _buildPhotoItem(mediaUpload, childrenProvider);
                },
                childCount: groupedUploads[month]!.length,
              ),
            ),
          ),
        ],
      ],
    );
  }

  Widget _buildPhotoItem(
    MediaUpload mediaUpload,
    ChildrenProvider childrenProvider,
  ) {
    return FutureBuilder<String>(
      future: _getDownloadUrl(mediaUpload),
      builder: (context, snapshot) {
        if (!snapshot.hasData) {
          return Container(
            decoration: BoxDecoration(
              color: Colors.grey[200],
              borderRadius: BorderRadius.circular(8),
            ),
            child: const Center(
              child: CircularProgressIndicator(),
            ),
          );
        }
        
        // Use captured date if available, otherwise use upload date
        final displayDate = mediaUpload.capturedAt ?? mediaUpload.uploadedAt;
        
        return GestureDetector(
          onLongPress: () => _showDeleteDialog(context, mediaUpload),
          child: Stack(
            fit: StackFit.expand,
            children: [
              ClipRRect(
                borderRadius: BorderRadius.circular(8),
                child: mediaUpload.mediaType == MediaType.video
                    ? _buildVideoThumbnail(snapshot.data!)
                    : Image.network(
                        snapshot.data!,
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
              // Date label
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
                    displayDate != null 
                      ? '${displayDate.month}/${displayDate.day}'
                      : '',
                    style: const TextStyle(
                      color: Colors.white,
                      fontSize: 10,
                    ),
                  ),
                ),
              ),
              // Child name label
              if (mediaUpload.childId.isNotEmpty)
                Positioned(
                  left: 4,
                  bottom: 4,
                  child: Container(
                    decoration: BoxDecoration(
                      color: Colors.blue.withValues(alpha: 0.8),
                      borderRadius: BorderRadius.circular(4),
                    ),
                    padding: const EdgeInsets.symmetric(
                      horizontal: 6,
                      vertical: 2,
                    ),
                    child: Text(
                      _getChildName(childrenProvider, mediaUpload.childId),
                      style: const TextStyle(
                        color: Colors.white,
                        fontSize: 10,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ),
                ),
              // Video indicator
              if (mediaUpload.mediaType == MediaType.video)
                const Positioned(
                  left: 0,
                  right: 0,
                  bottom: 0,
                  top: 0,
                  child: Icon(
                    Icons.play_circle_outline,
                    color: Colors.white,
                    size: 48,
                  ),
                ),
            ],
          ),
        );
      },
    );
  }

  Future<String?> _showChildSelectionDialog(
    BuildContext context,
    ChildrenProvider childrenProvider,
  ) {
    return showDialog<String?>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('子供を選択'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Text('写真をアップロードする子供を選択してください'),
            const SizedBox(height: 16),
            ...childrenProvider.children.map<Widget>(
              (child) => ListTile(
                leading: CircleAvatar(
                  backgroundColor: child.gender == Gender.male
                      ? Colors.blue
                      : Colors.pink,
                  child: Text(
                    child.name.isNotEmpty ? child.name[0] : '?',
                    style: const TextStyle(color: Colors.white),
                  ),
                ),
                title: Text(child.nickname ?? child.name),
                subtitle: Text('${child.age}歳'),
                onTap: () => Navigator.of(context).pop(child.id),
              ),
            ),
            const Divider(),
            ListTile(
              leading: const CircleAvatar(
                child: Icon(Icons.people),
              ),
              title: const Text('全員'),
              subtitle: const Text('特定の子供を選択しない'),
              onTap: () => Navigator.of(context).pop(''),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(),
            child: const Text('キャンセル'),
          ),
        ],
      ),
    );
  }

  Future<String> _getDownloadUrl(MediaUpload mediaUpload) async {
    try {
      final storage = FirebaseStorage.instance;
      final ref = storage.ref(mediaUpload.filePath);
      return await ref.getDownloadURL();
    } catch (e) {
      debugPrint('Error getting download URL: $e');
      rethrow;
    }
  }

  Widget _buildVideoThumbnail(String url) {
    return Stack(
      fit: StackFit.expand,
      children: [
        Container(
          color: Colors.black,
          child: const Center(
            child: Icon(
              Icons.video_library,
              color: Colors.white,
              size: 48,
            ),
          ),
        ),
      ],
    );
  }
}
