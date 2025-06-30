import 'dart:async';
import 'dart:typed_data';

import 'package:firebase_storage/firebase_storage.dart';
import 'package:flutter/material.dart';
import 'package:kids_diary/models/child.dart';
import 'package:kids_diary/models/media_upload.dart';
import 'package:kids_diary/models/notebook.dart';
import 'package:kids_diary/providers/children_provider.dart';
import 'package:kids_diary/providers/family_provider.dart';
import 'package:kids_diary/services/notebook_service.dart';
import 'package:kids_diary/services/video_thumbnail_service.dart';
import 'package:provider/provider.dart';
import 'package:share_plus/share_plus.dart';

class WeeklyNotebookScreen extends StatefulWidget {
  const WeeklyNotebookScreen({super.key});

  @override
  State<WeeklyNotebookScreen> createState() => _WeeklyNotebookScreenState();
}

class _WeeklyNotebookScreenState extends State<WeeklyNotebookScreen> {
  final NotebookService _notebookService = NotebookService();
  final VideoThumbnailService _videoThumbnailService = VideoThumbnailService();
  List<WeekInfo> _weeks = [];
  bool _isLoading = true;
  String? _selectedChildId;
  StreamSubscription<Set<String>>? _notebookIdSubscription;
  final Set<String> _generatingNotebooks = {};
  Set<String> _existingNotebookIds = {};

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _loadWeeks();
    });
  }

  @override
  void dispose() {
    _notebookIdSubscription?.cancel();
    super.dispose();
  }

  Future<void> _loadWeeks() async {
    try {
      debugPrint('=== _loadWeeks START ===');
      setState(() {
        _isLoading = true;
      });

      final childrenProvider = context.read<ChildrenProvider>();
      final children = childrenProvider.children;
      debugPrint('Found ${children.length} children');

      if (children.isEmpty) {
        debugPrint('No children found, showing empty state');
        setState(() {
          _weeks = [];
          _isLoading = false;
        });
        return;
      }

      // 最初の子供を選択（後で変更可能）
      final childId = _selectedChildId ?? children.first.id;
      debugPrint('Loading weeks for child: $childId');

      // ノートブックIDのリアルタイム監視を開始（軽量版）
      _notebookIdSubscription?.cancel();
      _notebookIdSubscription = _notebookService
          .watchChildNotebookIds(childId)
          .listen(
            (notebookIds) {
              debugPrint('Notebook IDs updated: ${notebookIds.length} notebooks');
              if (mounted) {
                final previousIds = _existingNotebookIds;
                _existingNotebookIds = notebookIds;
                
                // 新しく追加されたノートブックがある場合のみ再読み込み
                final newIds = notebookIds.difference(previousIds);
                if (newIds.isNotEmpty) {
                  debugPrint('New notebooks detected: $newIds');
                  
                  // 新しく作成されたノートブックの生成中フラグをクリア
                  for (final notebookId in newIds) {
                    if (_generatingNotebooks.contains(notebookId)) {
                      setState(() {
                        _generatingNotebooks.remove(notebookId);
                      });
                    }
                  }
                  
                  _loadWeeks(); // 新しいノートブックが追加されたら週リストを再読み込み
                }
              }
            },
          );

      final weeks = await _notebookService.getRecentWeeks(
        childId: childId,
      );
      debugPrint('Loaded ${weeks.length} weeks');

      if (mounted) {
        setState(() {
          _weeks = weeks;
          _selectedChildId = childId;
          _isLoading = false;
        });
        debugPrint('=== _loadWeeks SUCCESS ===');
      }
    } catch (e, stackTrace) {
      debugPrint('=== ERROR in _loadWeeks ===');
      debugPrint('Error type: ${e.runtimeType}');
      debugPrint('Error message: $e');
      debugPrint('Stack trace: $stackTrace');
      debugPrint('=== END ERROR ===');

      if (mounted) {
        setState(() {
          _isLoading = false;
        });

        // ユーザーには簡潔なメッセージを表示
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('データの読み込みに失敗しました'),
            backgroundColor: Colors.orange,
          ),
        );
      }
    }
  }

  Future<void> _generateNotebook(WeekInfo weekInfo) async {
    if (_selectedChildId == null) {
      debugPrint('ERROR: _selectedChildId is null in _generateNotebook');
      return;
    }

    // weekIdを外側で定義
    final weekId = _getWeekId(weekInfo.weekStart);

    try {
      debugPrint('=== _generateNotebook START ===');
      debugPrint('Child ID: $_selectedChildId');
      debugPrint('Week start: ${weekInfo.weekStart}');
      debugPrint('Week title: ${weekInfo.title}');

      // 生成中ダイアログを表示
      showDialog(
        context: context,
        barrierDismissible: false,
        builder: (context) => const AlertDialog(
          content: Row(
            children: [
              CircularProgressIndicator(),
              SizedBox(width: 16),
              Text('ノートブック生成中...'),
            ],
          ),
        ),
      );

      // 生成中フラグを設定
      setState(() {
        _generatingNotebooks.add(weekId);
      });

      debugPrint('Calling generateWeeklyNotebook API...');
      final response = await _notebookService.generateWeeklyNotebook(
        childId: _selectedChildId!,
        weekDate: weekInfo.weekStart,
      );

      debugPrint('API Response status: ${response.status}');
      debugPrint('API Response message: ${response.message}');
      if (response.error != null) {
        debugPrint('API Response error: ${response.error}');
      }

      if (mounted) {
        Navigator.of(context).pop(); // ダイアログを閉じる

        if (response.isSuccess) {
          debugPrint('Notebook generation SUCCESS');
          // 成功時のメッセージ
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(
              content: Text('ノートブックを作成しました'),
              backgroundColor: Colors.green,
            ),
          );

          // ノートブックは同期的に作成されるので、生成中フラグをクリアして再読み込み
          setState(() {
            _generatingNotebooks.remove(weekId);
          });
          _loadWeeks();
        } else {
          debugPrint('Notebook generation FAILED');
          // エラー時は生成中フラグをクリア
          setState(() {
            _generatingNotebooks.remove(weekId);
          });
          // エラー時のメッセージ
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(
              content: Text('ノートブックの作成に失敗しました'),
              backgroundColor: Colors.red,
            ),
          );
        }
      }
      debugPrint('=== _generateNotebook END ===');
    } catch (e, stackTrace) {
      debugPrint('=== ERROR in _generateNotebook ===');
      debugPrint('Error type: ${e.runtimeType}');
      debugPrint('Error message: $e');
      debugPrint('Stack trace: $stackTrace');
      debugPrint('=== END ERROR ===');

      if (mounted) {
        Navigator.of(context).pop(); // ダイアログを閉じる
        setState(() {
          _generatingNotebooks.remove(weekId);
        });
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('システムエラーが発生しました'),
            backgroundColor: Colors.red,
          ),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final familyProvider = context.watch<FamilyProvider>();
    final childrenProvider = context.watch<ChildrenProvider>();

    // ファミリーまたは子供が登録されていない場合
    if (!familyProvider.hasFamily || !childrenProvider.hasChildren) {
      return Scaffold(
        appBar: AppBar(
          title: const Text('週刊ノートブック'),
        ),
        body: const Center(
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(
                Icons.book_outlined,
                size: 80,
                color: Colors.grey,
              ),
              SizedBox(height: 24),
              Text(
                '週刊ノートブックを作成するには',
                style: TextStyle(
                  fontSize: 20,
                  fontWeight: FontWeight.bold,
                ),
              ),
              SizedBox(height: 16),
              Text(
                'ファミリーとお子様の情報を\n登録してください',
                textAlign: TextAlign.center,
                style: TextStyle(
                  fontSize: 16,
                  color: Colors.grey,
                ),
              ),
            ],
          ),
        ),
      );
    }

    return Scaffold(
      appBar: AppBar(
        title: const Text('週刊ノートブック'),
        actions: [
          if (childrenProvider.hasChildren &&
              childrenProvider.children.length > 1)
            PopupMenuButton<String>(
              icon: const Icon(Icons.person),
              onSelected: (childId) {
                setState(() {
                  _selectedChildId = childId;
                  _generatingNotebooks
                      .clear(); // Clear generation status when switching child
                });
                _loadWeeks();
              },
              itemBuilder: (context) => childrenProvider.children
                  .map(
                    (child) => PopupMenuItem<String>(
                      value: child.id,
                      child: Text(child.nickname ?? child.name),
                    ),
                  )
                  .toList(),
            ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: _loadWeeks,
        child: _buildContent(childrenProvider),
      ),
    );
  }

  Widget _buildContent(ChildrenProvider childrenProvider) {
    if (_isLoading) {
      return const Center(
        child: CircularProgressIndicator(),
      );
    }

    if (_weeks.isEmpty) {
      return const Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(
              Icons.book_outlined,
              size: 80,
              color: Colors.grey,
            ),
            SizedBox(height: 24),
            Text(
              'まだノートブックがありません',
              style: TextStyle(
                fontSize: 20,
                fontWeight: FontWeight.bold,
              ),
            ),
            SizedBox(height: 16),
            Text(
              '写真をアップロードして\nエピソードが蓄積されると\n週刊ノートブックが作成できます',
              textAlign: TextAlign.center,
              style: TextStyle(
                fontSize: 16,
                color: Colors.grey,
              ),
            ),
          ],
        ),
      );
    }

    // 選択中の子供の情報を取得
    final selectedChild = _selectedChildId != null
        ? childrenProvider.getChildById(_selectedChildId!)
        : null;

    return ListView.builder(
      padding: const EdgeInsets.all(16),
      itemCount: _weeks.length,
      itemBuilder: (context, index) {
        final week = _weeks[index];
        return _buildWeekCard(week, selectedChild);
      },
    );
  }

  Widget _buildWeekCard(WeekInfo week, Child? child) {
    return Card(
      margin: const EdgeInsets.only(bottom: 16),
      elevation: week.hasNotebook ? 3 : 1,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
      ),
      child: InkWell(
        onTap: week.hasNotebook ? () => _viewNotebook(week) : null,
        borderRadius: BorderRadius.circular(12),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // ヘッダー
              Row(
                children: [
                  Icon(
                    week.hasNotebook ? Icons.menu_book : Icons.book_outlined,
                    color: week.hasNotebook ? Colors.green : Colors.grey,
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      week.title,
                      style: const TextStyle(
                        fontSize: 18,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ),
                  if (week.isCurrentWeek)
                    Container(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 8,
                        vertical: 4,
                      ),
                      decoration: BoxDecoration(
                        color: Colors.blue[100],
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: Text(
                        '今週',
                        style: TextStyle(
                          fontSize: 12,
                          color: Colors.blue[700],
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                    ),
                ],
              ),
              const SizedBox(height: 12),

              // ステータス
              if (_generatingNotebooks.contains(
                _getWeekId(week.weekStart),
              )) ...[
                Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 12,
                    vertical: 6,
                  ),
                  decoration: BoxDecoration(
                    color: Colors.orange[50],
                    borderRadius: BorderRadius.circular(20),
                  ),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      SizedBox(
                        width: 16,
                        height: 16,
                        child: CircularProgressIndicator(
                          strokeWidth: 2,
                          valueColor: AlwaysStoppedAnimation<Color>(
                            Colors.orange[700]!,
                          ),
                        ),
                      ),
                      const SizedBox(width: 6),
                      Text(
                        'ノートブック生成中...',
                        style: TextStyle(
                          fontSize: 14,
                          color: Colors.orange[700],
                          fontWeight: FontWeight.w500,
                        ),
                      ),
                    ],
                  ),
                ),
              ] else if (week.hasNotebook) ...[
                Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 12,
                    vertical: 6,
                  ),
                  decoration: BoxDecoration(
                    color: Colors.green[50],
                    borderRadius: BorderRadius.circular(20),
                  ),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Icon(
                        Icons.check_circle,
                        size: 16,
                        color: Colors.green[700],
                      ),
                      const SizedBox(width: 6),
                      Text(
                        'ノートブック作成済み',
                        style: TextStyle(
                          fontSize: 14,
                          color: Colors.green[700],
                          fontWeight: FontWeight.w500,
                        ),
                      ),
                    ],
                  ),
                ),
                if (week.notebook!.topics.isNotEmpty) ...[
                  const SizedBox(height: 8),
                  Text(
                    '${week.notebook!.topics.length}個のトピック',
                    style: const TextStyle(
                      fontSize: 12,
                      color: Colors.grey,
                    ),
                  ),
                ],
                const SizedBox(height: 12),
                Row(
                  children: [
                    Expanded(
                      child: ElevatedButton.icon(
                        onPressed: () => _viewNotebook(week),
                        icon: const Icon(Icons.menu_book, size: 18),
                        label: const Text('ノートブックを見る'),
                        style: ElevatedButton.styleFrom(
                          padding: const EdgeInsets.symmetric(vertical: 12),
                          backgroundColor: Colors.indigo,
                          foregroundColor: Colors.white,
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(8),
                          ),
                        ),
                      ),
                    ),
                    const SizedBox(width: 8),
                    Container(
                      decoration: BoxDecoration(
                        border: Border.all(color: Colors.indigo.shade200),
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: IconButton(
                        onPressed: week.notebookId != null 
                            ? () => _shareNotebookById(week.notebookId!)
                            : null,
                        icon: const Icon(Icons.share),
                        color: Colors.indigo,
                        tooltip: 'ノートブックを共有',
                      ),
                    ),
                  ],
                ),
              ] else if (week.canGenerate && week.hasMedia) ...[
                Text(
                  'この週のノートブックを作成できます',
                  style: TextStyle(
                    fontSize: 14,
                    color: Colors.blue[700],
                  ),
                ),
                const SizedBox(height: 12),
                SizedBox(
                  width: double.infinity,
                  child: ElevatedButton.icon(
                    onPressed:
                        _generatingNotebooks.contains(
                          _getWeekId(week.weekStart),
                        )
                        ? null
                        : () => _generateNotebook(week),
                    icon: const Icon(Icons.auto_awesome),
                    label: const Text('ノートブック作成'),
                  ),
                ),
              ] else if (!week.hasMedia) ...[
                const Text(
                  'この週はまだ写真や動画がありません',
                  style: TextStyle(
                    fontSize: 14,
                    color: Colors.orange,
                  ),
                ),
              ] else ...[
                Text(
                  week.isCurrentWeek
                      ? '今週はまだ作成できません（週末まで待ってね）'
                      : 'この期間はノートブックを作成できません',
                  style: const TextStyle(
                    fontSize: 14,
                    color: Colors.grey,
                  ),
                ),
              ],

              // メディアサムネイル
              if (week.hasMedia) ...[
                const SizedBox(height: 12),
                _buildMediaThumbnails(week.weekMedia),
              ],
            ],
          ),
        ),
      ),
    );
  }

  Future<void> _viewNotebook(WeekInfo week) async {
    // ノートブックがまだ読み込まれていない場合は読み込む
    if (week.hasNotebook && !week.notebookLoaded && week.notebookId != null) {
      // ローディングを表示
      showDialog(
        context: context,
        barrierDismissible: false,
        builder: (context) => const Center(
          child: CircularProgressIndicator(),
        ),
      );
      
      try {
        // ノートブックの詳細を取得
        final childId = _selectedChildId!;
        final notebook = await _notebookService.getNotebook(childId, week.notebookId!);
        
        if (mounted) {
          Navigator.of(context).pop(); // ローディングを閉じる
          
          if (notebook != null) {
            week.notebook = notebook;
            Navigator.of(context).push(
              MaterialPageRoute(
                builder: (context) => NotebookDetailScreen(notebook: notebook),
              ),
            );
          } else {
            ScaffoldMessenger.of(context).showSnackBar(
              const SnackBar(
                content: Text('ノートブックが見つかりません'),
                backgroundColor: Colors.red,
              ),
            );
          }
        }
      } catch (e) {
        if (mounted) {
          Navigator.of(context).pop(); // ローディングを閉じる
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(
              content: Text('ノートブックの読み込みに失敗しました'),
              backgroundColor: Colors.red,
            ),
          );
        }
      }
    } else if (week.notebook != null) {
      Navigator.of(context).push(
        MaterialPageRoute(
          builder: (context) => NotebookDetailScreen(notebook: week.notebook!),
        ),
      );
    }
  }

  Future<void> _shareNotebook(Notebook notebook) async {
    try {
      // Create the web URL for the notebook
      const baseUrl = 'https://hackason-464007.web.app';
      final notebookUrl = '$baseUrl/notebooks/${notebook.id}';

      final shareText =
          '''
${notebook.nickname}のノートブック
${_formatDateRange(notebook.period.start, notebook.period.end)}

${notebook.topics.length}個のエピソードが記録されています。

ノートブックを見る：
$notebookUrl
''';

      await Share.share(shareText);
    } catch (e) {
      debugPrint('Error sharing notebook: $e');
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('共有に失敗しました'),
            backgroundColor: Colors.red,
          ),
        );
      }
    }
  }

  Future<void> _shareNotebookById(String notebookId) async {
    try {
      // Create the web URL for the notebook
      const baseUrl = 'https://hackason-464007.web.app';
      final notebookUrl = '$baseUrl/notebooks/$notebookId';

      final shareText = '''
ノートブック

ノートブックを見る：
$notebookUrl
''';

      await Share.share(shareText);
    } catch (e) {
      debugPrint('Error sharing notebook: $e');
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('共有に失敗しました'),
            backgroundColor: Colors.red,
          ),
        );
      }
    }
  }

  String _formatDateRange(DateTime start, DateTime end) {
    return '${start.year}年${start.month}月${start.day}日 〜 ${end.month}月${end.day}日';
  }

  String _getWeekId(DateTime weekStart) {
    // バックエンドの実装に合わせてIDを生成
    // 形式: {child_id}_{start_date}_notebook
    final startDateStr = '${weekStart.year}_${weekStart.month.toString().padLeft(2, '0')}_${weekStart.day.toString().padLeft(2, '0')}';
    return '${_selectedChildId}_${startDateStr}_notebook';
  }

  int _getWeekNumber(DateTime date) {
    final firstDayOfMonth = DateTime(date.year, date.month);
    final firstMonday = _getWeekStart(firstDayOfMonth);
    final targetMonday = _getWeekStart(date);

    final diffInDays = targetMonday.difference(firstMonday).inDays;
    return (diffInDays ~/ 7) + 1;
  }

  DateTime _getWeekStart(DateTime date) {
    final weekday = date.weekday;
    final daysFromMonday = weekday - 1;
    return DateTime(
      date.year,
      date.month,
      date.day,
    ).subtract(Duration(days: daysFromMonday));
  }


  Widget _buildMediaThumbnails(List<MediaUpload> mediaList) {
    if (mediaList.isEmpty) return const SizedBox.shrink();

    // 最大6個まで表示
    final displayMedia = mediaList.take(6).toList();

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            const Icon(Icons.photo_library, size: 16, color: Colors.grey),
            const SizedBox(width: 4),
            Text(
              '${mediaList.length}件の写真・動画',
              style: const TextStyle(
                fontSize: 12,
                color: Colors.grey,
                fontWeight: FontWeight.w500,
              ),
            ),
          ],
        ),
        const SizedBox(height: 8),
        SizedBox(
          height: 60,
          child: ListView.builder(
            scrollDirection: Axis.horizontal,
            itemCount: displayMedia.length,
            itemBuilder: (context, index) {
              final media = displayMedia[index];
              return Padding(
                padding: EdgeInsets.only(
                  right: index < displayMedia.length - 1 ? 8 : 0,
                ),
                child: _buildMediaThumbnail(media),
              );
            },
          ),
        ),
      ],
    );
  }

  Widget _buildMediaThumbnail(MediaUpload media) {
    return Container(
      width: 60,
      height: 60,
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(8),
        color: Colors.grey[200],
      ),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(8),
        child: FutureBuilder<String>(
          future: _getDownloadUrl(media),
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
                if (media.mediaType == MediaType.image)
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
                  )
                else if (media.mediaType == MediaType.video)
                  FutureBuilder<Uint8List?>(
                    future: _videoThumbnailService.getThumbnail(snapshot.data!),
                    builder: (context, thumbnailSnapshot) {
                      if (thumbnailSnapshot.hasData &&
                          thumbnailSnapshot.data != null) {
                        return Image.memory(
                          thumbnailSnapshot.data!,
                          fit: BoxFit.cover,
                        );
                      } else if (thumbnailSnapshot.hasError) {
                        return const Icon(Icons.error, color: Colors.red);
                      } else {
                        return Container(
                          color: Colors.grey[300],
                          child: const Icon(
                            Icons.video_library,
                            color: Colors.grey,
                          ),
                        );
                      }
                    },
                  )
                else
                  const Icon(Icons.insert_drive_file, color: Colors.grey),

                if (media.mediaType == MediaType.video)
                  const Positioned(
                    bottom: 4,
                    right: 4,
                    child: Icon(
                      Icons.play_circle_outline,
                      color: Colors.white,
                      size: 16,
                      shadows: [
                        Shadow(
                          offset: Offset(1, 1),
                          blurRadius: 2,
                          color: Colors.black54,
                        ),
                      ],
                    ),
                  ),
              ],
            );
          },
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
}

class NotebookDetailScreen extends StatelessWidget {
  final Notebook notebook;

  const NotebookDetailScreen({
    required this.notebook,
    super.key,
  });

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text('${notebook.nickname}のノート'),
        actions: [
          IconButton(
            onPressed: () async {
              try {
                const baseUrl = 'https://hackason-464007.web.app';
                final notebookUrl = '$baseUrl/notebooks/${notebook.id}';

                final shareText =
                    '''
${notebook.nickname}のノートブック

${notebook.topics.length}個のエピソードが記録されています。

ノートブックを見る：
$notebookUrl
''';

                await Share.share(shareText);
              } catch (e) {
                debugPrint('Error sharing notebook: $e');
              }
            },
            icon: const Icon(Icons.share),
            tooltip: 'ノートブックを共有',
          ),
        ],
      ),
      body: ListView.builder(
        padding: const EdgeInsets.all(16),
        itemCount: notebook.topics.length,
        itemBuilder: (context, index) {
          final topic = notebook.topics[index];
          return _buildTopicCard(topic);
        },
      ),
    );
  }

  Widget _buildTopicCard(NotebookTopic topic) {
    return Card(
      margin: const EdgeInsets.only(bottom: 16),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // タイトル
            Text(
              topic.title,
              style: const TextStyle(
                fontSize: 20,
                fontWeight: FontWeight.bold,
                color: Colors.indigo,
              ),
            ),
            if (topic.subtitle != null) ...[
              const SizedBox(height: 4),
              Text(
                topic.subtitle!,
                style: const TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.w500,
                  color: Colors.grey,
                ),
              ),
            ],
            const SizedBox(height: 12),

            // 画像（あれば）
            if (topic.photo != null) ...[
              ClipRRect(
                borderRadius: BorderRadius.circular(8),
                child: Image.network(
                  topic.photo!,
                  width: double.infinity,
                  height: 200,
                  fit: BoxFit.cover,
                  errorBuilder: (context, error, stackTrace) {
                    return Container(
                      height: 200,
                      color: Colors.grey[300],
                      child: const Center(
                        child: Icon(
                          Icons.broken_image,
                          size: 50,
                          color: Colors.grey,
                        ),
                      ),
                    );
                  },
                ),
              ),
              if (topic.caption != null) ...[
                const SizedBox(height: 8),
                Text(
                  topic.caption!,
                  style: const TextStyle(
                    fontSize: 12,
                    color: Colors.grey,
                    fontStyle: FontStyle.italic,
                  ),
                ),
              ],
              const SizedBox(height: 12),
            ],

            // 内容
            Text(
              topic.content,
              style: const TextStyle(
                fontSize: 16,
                height: 1.6,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

