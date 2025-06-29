import 'package:flutter/material.dart';
import 'package:mobile/models/child.dart';
import 'package:mobile/models/episode.dart';
import 'package:mobile/providers/children_provider.dart';
import 'package:mobile/providers/family_provider.dart';
import 'package:mobile/services/episode_service.dart';
import 'package:provider/provider.dart';

class TimelineScreen extends StatefulWidget {
  const TimelineScreen({super.key});

  @override
  State<TimelineScreen> createState() => _TimelineScreenState();
}

class _TimelineScreenState extends State<TimelineScreen> {
  final EpisodeService _episodeService = EpisodeService();
  List<Episode> _episodes = [];
  bool _isLoading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    debugPrint('TimelineScreen: initState called');
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _loadEpisodes();
    });
  }

  Future<void> _loadEpisodes() async {
    try {
      setState(() {
        _isLoading = true;
        _error = null;
      });

      final childrenProvider = context.read<ChildrenProvider>();
      final children = childrenProvider.children;
      debugPrint('TimelineScreen: ChildrenProvider has ${children.length} children');

      if (children.isEmpty) {
        debugPrint('TimelineScreen: No children found, showing empty state');
        if (mounted) {
          setState(() {
            _episodes = [];
            _isLoading = false;
          });
        }
        return;
      }

      // Get all child IDs
      final childIds = children.map((child) => child.id).toList();
      
      // Fetch episodes for all children in the family
      debugPrint('TimelineScreen: Loading episodes for child IDs: $childIds');
      final episodes = await _episodeService.getFamilyChildrenEpisodes(childIds);
      debugPrint('TimelineScreen: Loaded ${episodes.length} episodes');

      if (mounted) {
        setState(() {
          _episodes = episodes;
          _isLoading = false;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _error = 'エピソードの読み込みに失敗しました: $e';
          _isLoading = false;
        });
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
          title: const Text('タイムライン'),
        ),
        body: Center(
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              const Icon(
                Icons.timeline_outlined,
                size: 80,
                color: Colors.grey,
              ),
              const SizedBox(height: 24),
              const Text(
                'タイムラインを表示するには',
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
            ],
          ),
        ),
      );
    }

    return Scaffold(
      appBar: AppBar(
        title: const Text('タイムライン'),
      ),
      body: RefreshIndicator(
        onRefresh: _loadEpisodes,
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

    if (_error != null) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(
              Icons.error_outline,
              size: 60,
              color: Colors.red[300],
            ),
            const SizedBox(height: 16),
            Text(
              _error!,
              textAlign: TextAlign.center,
              style: const TextStyle(fontSize: 16),
            ),
            const SizedBox(height: 16),
            ElevatedButton(
              onPressed: _loadEpisodes,
              child: const Text('再読み込み'),
            ),
          ],
        ),
      );
    }

    if (_episodes.isEmpty) {
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
              'まだエピソードがありません',
              style: TextStyle(
                fontSize: 20,
                color: Colors.grey[600],
                fontWeight: FontWeight.bold,
              ),
            ),
            const SizedBox(height: 16),
            Text(
              '写真をアップロードすると\nエピソードが自動生成されます',
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

    return ListView.builder(
      padding: const EdgeInsets.all(16),
      itemCount: _episodes.length,
      itemBuilder: (context, index) {
        final episode = _episodes[index];
        final child = childrenProvider.children.firstWhere(
          (c) => c.id == episode.childId,
          orElse: () => Child(
            id: '',
            familyId: '',
            name: '不明',
            birthDate: DateTime.now(),
            gender: Gender.other,
            createdAt: DateTime.now(),
            updatedAt: DateTime.now(),
          ),
        );
        return _buildEpisodeCard(episode, child);
      },
    );
  }

  Widget _buildEpisodeCard(Episode episode, Child child) {
    return Card(
      margin: const EdgeInsets.only(bottom: 16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // ヘッダー
          Padding(
            padding: const EdgeInsets.all(16),
            child: Row(
              children: [
                // 子供の名前とアイコン
                Container(
                  width: 40,
                  height: 40,
                  decoration: BoxDecoration(
                    color: child.gender == Gender.male
                        ? Colors.blue[100]
                        : child.gender == Gender.female
                            ? Colors.pink[100]
                            : Colors.grey[100],
                    shape: BoxShape.circle,
                  ),
                  child: Icon(
                    child.gender == Gender.male
                        ? Icons.face
                        : child.gender == Gender.female
                            ? Icons.face_3
                            : Icons.face_6,
                    color: child.gender == Gender.male
                        ? Colors.blue
                        : child.gender == Gender.female
                            ? Colors.pink
                            : Colors.grey,
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        child.nickname ?? child.name,
                        style: const TextStyle(
                          fontWeight: FontWeight.bold,
                          fontSize: 16,
                        ),
                      ),
                      Text(
                        _formatDate(episode.createdAt),
                        style: TextStyle(
                          fontSize: 12,
                          color: Colors.grey[600],
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),

          // タイトル（あれば）
          if (episode.title != null && episode.title!.isNotEmpty)
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16),
              child: Text(
                episode.title!,
                style: const TextStyle(
                  fontSize: 18,
                  fontWeight: FontWeight.bold,
                ),
              ),
            ),

          // コンテンツ
          if (episode.content != null && episode.content!.isNotEmpty)
            Padding(
              padding: const EdgeInsets.all(16),
              child: Text(
                episode.content!,
                style: const TextStyle(fontSize: 14),
              ),
            ),

          // 画像（あれば）
          if (episode.mediaUrls.isNotEmpty)
            SizedBox(
              height: 200,
              child: ListView.builder(
                scrollDirection: Axis.horizontal,
                padding: const EdgeInsets.symmetric(horizontal: 16),
                itemCount: episode.mediaUrls.length,
                itemBuilder: (context, index) {
                  return Padding(
                    padding: const EdgeInsets.only(right: 8),
                    child: ClipRRect(
                      borderRadius: BorderRadius.circular(8),
                      child: Image.network(
                        episode.mediaUrls[index],
                        width: 200,
                        height: 200,
                        fit: BoxFit.cover,
                        errorBuilder: (context, error, stackTrace) {
                          return Container(
                            width: 200,
                            height: 200,
                            color: Colors.grey[300],
                            child: const Icon(
                              Icons.broken_image,
                              size: 50,
                              color: Colors.grey,
                            ),
                          );
                        },
                      ),
                    ),
                  );
                },
              ),
            ),

          const SizedBox(height: 16),
        ],
      ),
    );
  }

  String _formatDate(DateTime date) {
    final now = DateTime.now();
    final difference = now.difference(date);

    if (difference.inDays > 7) {
      return '${date.year}年${date.month}月${date.day}日';
    } else if (difference.inDays > 0) {
      return '${difference.inDays}日前';
    } else if (difference.inHours > 0) {
      return '${difference.inHours}時間前';
    } else if (difference.inMinutes > 0) {
      return '${difference.inMinutes}分前';
    } else {
      return 'たった今';
    }
  }
}
