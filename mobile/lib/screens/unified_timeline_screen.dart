import 'dart:async';

import 'package:firebase_storage/firebase_storage.dart';
import 'package:flutter/material.dart';
import 'package:mobile/models/child.dart';
import 'package:mobile/models/episode.dart';
import 'package:mobile/models/media_upload.dart';
import 'package:mobile/providers/children_provider.dart';
import 'package:mobile/providers/family_provider.dart';
import 'package:mobile/providers/storage_provider.dart';
import 'package:mobile/screens/home_screen.dart';
import 'package:mobile/services/episode_service.dart';
import 'package:mobile/services/media_upload_service.dart';
import 'package:provider/provider.dart';

class UnifiedTimelineScreen extends StatefulWidget {
  const UnifiedTimelineScreen({super.key});

  @override
  State<UnifiedTimelineScreen> createState() => _UnifiedTimelineScreenState();
}

class _UnifiedTimelineScreenState extends State<UnifiedTimelineScreen> {
  final MediaUploadService _mediaUploadService = MediaUploadService();
  final EpisodeService _episodeService = EpisodeService();
  List<MediaUpload> _mediaUploads = [];
  Map<String, Episode> _episodesMap = {};
  bool _isLoading = true;
  
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _loadData();
    });
  }
  
  Future<void> _loadData() async {
    try {
      setState(() {
        _isLoading = true;
      });
      
      // Load media uploads
      final mediaUploads = await _mediaUploadService.getUserMediaUploads();
      
      // Sort by captured date (newest first)
      mediaUploads.sort((a, b) {
        final dateA = a.capturedAt ?? a.uploadedAt ?? DateTime.now();
        final dateB = b.capturedAt ?? b.uploadedAt ?? DateTime.now();
        return dateB.compareTo(dateA);
      });
      
      // Load episodes for completed media uploads
      final episodesMap = <String, Episode>{};
      for (final upload in mediaUploads) {
        if (upload.episodeId != null) {
          final episode = await _episodeService.getEpisode(upload.episodeId!);
          if (episode != null) {
            episodesMap[upload.episodeId!] = episode;
          }
        }
      }
      
      if (mounted) {
        setState(() {
          _mediaUploads = mediaUploads;
          _episodesMap = episodesMap;
          _isLoading = false;
        });
      }
    } catch (e) {
      debugPrint('Error loading timeline data: $e');
      if (mounted) {
        setState(() {
          _isLoading = false;
        });
      }
    }
  }
  
  @override
  Widget build(BuildContext context) {
    final familyProvider = context.watch<FamilyProvider>();
    final childrenProvider = context.watch<ChildrenProvider>();
    final storageProvider = context.watch<StorageProvider>();
    
    // Check if family and children are registered
    if (!familyProvider.hasFamily || !childrenProvider.hasChildren) {
      return Scaffold(
        appBar: AppBar(
          title: const Text('タイムライン'),
        ),
        body: Center(
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              const Icon(
                Icons.photo_library_outlined,
                size: 80,
                color: Colors.grey,
              ),
              const SizedBox(height: 24),
              const Text(
                'タイムラインを始めるには',
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
        title: const Text('タイムライン'),
        actions: [
          if (childrenProvider.hasChildren)
            PopupMenuButton<String?>(
              icon: Icon(
                storageProvider.selectedChildId != null
                    ? Icons.child_care
                    : Icons.child_care_outlined,
              ),
              onSelected: (childId) {
                storageProvider.setSelectedChildId(childId);
                _loadData();
              },
              itemBuilder: (context) => [
                const PopupMenuItem<String?>(
                  value: null,
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
      body: RefreshIndicator(
        onRefresh: _loadData,
        child: _buildContent(childrenProvider),
      ),
      floatingActionButton: FloatingActionButton(
        onPressed: () => _uploadPhotos(context, storageProvider, childrenProvider),
        child: const Icon(Icons.add_photo_alternate),
      ),
    );
  }
  
  Widget _buildContent(ChildrenProvider childrenProvider) {
    if (_isLoading) {
      return const Center(
        child: CircularProgressIndicator(),
      );
    }
    
    if (_mediaUploads.isEmpty) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(
              Icons.photo_library_outlined,
              size: 80,
              color: Colors.grey[400],
            ),
            const SizedBox(height: 24),
            Text(
              'まだ写真がありません',
              style: TextStyle(
                fontSize: 20,
                color: Colors.grey[600],
                fontWeight: FontWeight.bold,
              ),
            ),
            const SizedBox(height: 16),
            Text(
              '写真をアップロードして\nタイムラインを作成しましょう',
              textAlign: TextAlign.center,
              style: TextStyle(
                fontSize: 16,
                color: Colors.grey[500],
              ),
            ),
          ],
        ),
      );
    }
    
    // Group media uploads by date
    final groupedUploads = <String, List<MediaUpload>>{};
    final dateKeys = <String, DateTime>{};
    
    for (final upload in _mediaUploads) {
      final date = upload.capturedAt ?? upload.uploadedAt ?? DateTime.now();
      final dateKey = _getDateKey(date);
      
      if (!groupedUploads.containsKey(dateKey)) {
        groupedUploads[dateKey] = [];
        dateKeys[dateKey] = date;
      }
      groupedUploads[dateKey]!.add(upload);
    }
    
    // Sort date keys (newest first)
    final sortedDateKeys = groupedUploads.keys.toList()
      ..sort((a, b) {
        final dateA = dateKeys[a]!;
        final dateB = dateKeys[b]!;
        return dateB.compareTo(dateA);
      });
    
    return CustomScrollView(
      slivers: [
        for (final dateKey in sortedDateKeys) ...[
          // Date section header
          SliverToBoxAdapter(
            child: Container(
              width: double.infinity,
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
              decoration: BoxDecoration(
                color: Colors.grey[50],
                border: Border(
                  bottom: BorderSide(
                    color: Colors.grey[300]!,
                    width: 0.5,
                  ),
                ),
              ),
              child: Text(
                dateKey,
                style: TextStyle(
                  fontSize: 15,
                  fontWeight: FontWeight.w600,
                  color: Colors.grey[800],
                ),
              ),
            ),
          ),
          // Items in this section
          SliverList(
            delegate: SliverChildBuilderDelegate(
              (context, index) {
                final mediaUpload = groupedUploads[dateKey]![index];
                final episode = mediaUpload.episodeId != null 
                    ? _episodesMap[mediaUpload.episodeId!] 
                    : null;
                final child = childrenProvider.getChildById(mediaUpload.childId);
                
                return _buildTimelineItem(mediaUpload, episode, child);
              },
              childCount: groupedUploads[dateKey]!.length,
            ),
          ),
        ],
      ],
    );
  }
  
  Widget _buildTimelineItem(
    MediaUpload mediaUpload,
    Episode? episode,
    Child? child,
  ) {
    final displayDate = mediaUpload.capturedAt ?? mediaUpload.uploadedAt ?? DateTime.now();
    
    return Container(
      decoration: BoxDecoration(
        color: Colors.white,
        border: Border(
          bottom: BorderSide(
            color: Colors.grey[200]!,
            width: 1,
          ),
        ),
      ),
      child: InkWell(
        onTap: () {
          // TODO: Navigate to detail view
        },
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Thumbnail
              ClipRRect(
                borderRadius: BorderRadius.circular(8),
                child: SizedBox(
                  width: 80,
                  height: 80,
                  child: FutureBuilder<String>(
                    future: _getDownloadUrl(mediaUpload),
                    builder: (context, snapshot) {
                      if (!snapshot.hasData) {
                        return Container(
                          color: Colors.grey[200],
                          child: const Center(
                            child: CircularProgressIndicator(strokeWidth: 2),
                          ),
                        );
                      }
                      
                      return Stack(
                        fit: StackFit.expand,
                        children: [
                          if (mediaUpload.mediaType == MediaType.video)
                            Container(
                              color: Colors.black,
                              child: const Icon(
                                Icons.video_library,
                                color: Colors.white,
                                size: 32,
                              ),
                            )
                          else
                            Image.network(
                              snapshot.data!,
                              fit: BoxFit.cover,
                              errorBuilder: (context, error, stackTrace) {
                                return Container(
                                  color: Colors.grey[300],
                                  child: const Icon(
                                    Icons.broken_image,
                                    color: Colors.grey,
                                  ),
                                );
                              },
                            ),
                          if (mediaUpload.mediaType == MediaType.video)
                            const Positioned.fill(
                              child: Icon(
                                Icons.play_circle_outline,
                                color: Colors.white,
                                size: 40,
                              ),
                            ),
                        ],
                      );
                    },
                  ),
                ),
              ),
              const SizedBox(width: 12),
              // Content
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    // Time and child info
                    Row(
                      children: [
                        Text(
                          '${displayDate.hour.toString().padLeft(2, '0')}:${displayDate.minute.toString().padLeft(2, '0')}',
                          style: TextStyle(
                            fontSize: 12,
                            color: Colors.grey[600],
                          ),
                        ),
                        if (child != null) ...[
                          const SizedBox(width: 8),
                          Container(
                            padding: const EdgeInsets.symmetric(
                              horizontal: 8,
                              vertical: 2,
                            ),
                            decoration: BoxDecoration(
                              color: child.gender == Gender.male
                                  ? Colors.blue[100]
                                  : Colors.pink[100],
                              borderRadius: BorderRadius.circular(12),
                            ),
                            child: Text(
                              child.nickname ?? child.name,
                              style: TextStyle(
                                fontSize: 12,
                                color: child.gender == Gender.male
                                    ? Colors.blue[700]
                                    : Colors.pink[700],
                              ),
                            ),
                          ),
                        ],
                      ],
                    ),
                    const SizedBox(height: 8),
                    // Title or status
                    if (mediaUpload.processingStatus == ProcessingStatus.pending ||
                        mediaUpload.processingStatus == ProcessingStatus.processing)
                      Row(
                        children: [
                          SizedBox(
                            width: 16,
                            height: 16,
                            child: CircularProgressIndicator(
                              strokeWidth: 2,
                              valueColor: AlwaysStoppedAnimation<Color>(
                                Colors.orange[600]!,
                              ),
                            ),
                          ),
                          const SizedBox(width: 8),
                          Text(
                            'タイムライン作成中...',
                            style: TextStyle(
                              fontSize: 14,
                              color: Colors.orange[600],
                              fontWeight: FontWeight.w500,
                            ),
                          ),
                        ],
                      )
                    else if (episode != null)
                      Text(
                        episode.title ?? '無題のエピソード',
                        style: const TextStyle(
                          fontSize: 16,
                          fontWeight: FontWeight.bold,
                        ),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      )
                    else
                      const Text(
                        'エピソード',
                        style: TextStyle(
                          fontSize: 16,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                    // Content preview
                    if (episode != null && episode.content != null)
                      Padding(
                        padding: const EdgeInsets.only(top: 4),
                        child: Text(
                          episode.content!,
                          style: TextStyle(
                            fontSize: 14,
                            color: Colors.grey[700],
                          ),
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                  ],
                ),
              ),
            ],
          ),
        ),
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
  
  String _formatDate(DateTime date) {
    final now = DateTime.now();
    final difference = now.difference(date);
    
    if (difference.inDays == 0) {
      return '今日';
    } else if (difference.inDays == 1) {
      return '昨日';
    } else if (difference.inDays < 7) {
      return '${difference.inDays}日前';
    } else {
      return '${date.year}年${date.month}月${date.day}日';
    }
  }
  
  String _getDateKey(DateTime date) {
    final now = DateTime.now();
    final today = DateTime(now.year, now.month, now.day);
    final targetDate = DateTime(date.year, date.month, date.day);
    final difference = today.difference(targetDate).inDays;
    
    if (difference == 0) {
      return '今日';
    } else if (difference == 1) {
      return '昨日';
    } else if (difference == 2) {
      return '一昨日';
    } else if (difference < 7) {
      const weekdays = ['日', '月', '火', '水', '木', '金', '土'];
      return '${weekdays[date.weekday % 7]}曜日';
    } else if (difference < 30) {
      return '${date.month}月${date.day}日 (${_getWeekdayName(date)})';
    } else if (date.year == now.year) {
      return '${date.month}月${date.day}日';
    } else {
      return '${date.year}年${date.month}月${date.day}日';
    }
  }
  
  String _getWeekdayName(DateTime date) {
    const weekdays = ['日', '月', '火', '水', '木', '金', '土'];
    return '${weekdays[date.weekday % 7]}曜';
  }
  
  Future<void> _uploadPhotos(
    BuildContext context,
    StorageProvider storageProvider,
    ChildrenProvider childrenProvider,
  ) async {
    // Show child selection dialog if needed
    if (childrenProvider.hasChildren && storageProvider.selectedChildId == null) {
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
    
    // Show upload progress dialog
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
                            ? provider.uploadProgress / provider.totalFiles
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
        _loadData(); // Reload timeline after upload
      }
    } catch (e) {
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
}
