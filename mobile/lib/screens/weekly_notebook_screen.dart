import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:kids_diary/models/child.dart';
import 'package:kids_diary/models/notebook.dart';
import 'package:kids_diary/providers/children_provider.dart';
import 'package:kids_diary/providers/family_provider.dart';
import 'package:kids_diary/screens/notebook_creation_screen.dart';
import 'package:kids_diary/screens/notebook_webview_screen.dart';
import 'package:kids_diary/services/notebook_service.dart';
import 'package:provider/provider.dart';
import 'package:share_plus/share_plus.dart';

class WeeklyNotebookScreen extends StatefulWidget {
  const WeeklyNotebookScreen({super.key});

  @override
  State<WeeklyNotebookScreen> createState() => _WeeklyNotebookScreenState();
}

class _WeeklyNotebookScreenState extends State<WeeklyNotebookScreen> {
  final FirebaseFirestore _firestore = FirebaseFirestore.instance;
  final NotebookService _notebookService = NotebookService();
  List<QueryDocumentSnapshot> _notebooks = [];
  bool _isLoading = true;
  String? _selectedChildId;

  @override
  void initState() {
    super.initState();
    _loadNotebooks();
  }

  @override
  void dispose() {
    super.dispose();
  }

  Future<void> _loadNotebooks() async {
    try {
      debugPrint('=== _loadNotebooks START ===');
      setState(() {
        _isLoading = true;
      });

      final childrenProvider = context.read<ChildrenProvider>();
      final children = childrenProvider.children;
      debugPrint('Found ${children.length} children');

      if (children.isEmpty) {
        debugPrint('No children found, showing empty state');
        setState(() {
          _notebooks = [];
          _isLoading = false;
        });
        return;
      }

      // 最初の子供を選択（後で変更可能）
      final childId = _selectedChildId ?? children.first.id;
      debugPrint('Loading notebooks for child: $childId');

      // ノートブックを新しい順に取得
      final notebooksSnapshot = await _firestore
          .collection('children')
          .doc(childId)
          .collection('notebooks')
          .orderBy('createdAt', descending: true)
          .get();

      debugPrint('Loaded ${notebooksSnapshot.docs.length} notebooks');

      if (mounted) {
        setState(() {
          _notebooks = notebooksSnapshot.docs;
          _selectedChildId = childId;
          _isLoading = false;
        });
        debugPrint('=== _loadNotebooks SUCCESS ===');
      }
    } catch (e, stackTrace) {
      debugPrint('=== ERROR in _loadNotebooks ===');
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

  Future<void> _navigateToCreationScreen() async {
    if (_selectedChildId == null) return;

    final result = await Navigator.of(context).push<bool>(
      MaterialPageRoute(
        builder: (context) => NotebookCreationScreen(
          childId: _selectedChildId!,
        ),
      ),
    );

    if (result == true && mounted) {
      _loadNotebooks();
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
        title: const Text('ノートブック'),
        actions: [
          if (childrenProvider.hasChildren &&
              childrenProvider.children.length > 1)
            PopupMenuButton<String>(
              icon: const Icon(Icons.person),
              onSelected: (childId) {
                setState(() {
                  _selectedChildId = childId;
                });
                _loadNotebooks();
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
        onRefresh: _loadNotebooks,
        child: _buildContent(childrenProvider),
      ),
      floatingActionButton: childrenProvider.hasChildren
          ? FloatingActionButton(
              onPressed: _navigateToCreationScreen,
              child: const Icon(Icons.auto_awesome),
            )
          : null,
    );
  }

  Widget _buildContent(ChildrenProvider childrenProvider) {
    if (_isLoading) {
      return const Center(
        child: CircularProgressIndicator(),
      );
    }

    if (_notebooks.isEmpty) {
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
              '右下のボタンから\nノートブックを作成してください',
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

    // ノートブックを月ごとにグループ化
    final groupedNotebooks = <String, List<QueryDocumentSnapshot>>{};
    final monthKeys = <String, DateTime>{};

    for (final notebook in _notebooks) {
      final data = notebook.data()! as Map<String, dynamic>;
      final period = data['period'] as Map<String, dynamic>?;

      DateTime periodStart;
      if (period != null && period['start'] != null) {
        final startValue = period['start'];
        if (startValue is Timestamp) {
          periodStart = startValue.toDate();
        } else if (startValue is String) {
          periodStart = DateTime.parse(startValue);
        } else {
          periodStart = DateTime.now();
        }
      } else {
        periodStart = DateTime.now();
      }

      final monthKey = _getMonthKey(periodStart);

      if (!groupedNotebooks.containsKey(monthKey)) {
        groupedNotebooks[monthKey] = [];
        monthKeys[monthKey] = periodStart;
      }
      groupedNotebooks[monthKey]!.add(notebook);
    }

    // 月キーをソート（新しい順）
    final sortedMonthKeys = groupedNotebooks.keys.toList()
      ..sort((a, b) {
        final dateA = monthKeys[a]!;
        final dateB = monthKeys[b]!;
        return dateB.compareTo(dateA);
      });

    return CustomScrollView(
      slivers: [
        for (final monthKey in sortedMonthKeys) ...[
          // 月のセクションヘッダー
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
                monthKey,
                style: TextStyle(
                  fontSize: 15,
                  fontWeight: FontWeight.w600,
                  color: Colors.grey[800],
                ),
              ),
            ),
          ),
          // その月のノートブック
          SliverList(
            delegate: SliverChildBuilderDelegate(
              (context, index) {
                final notebook = groupedNotebooks[monthKey]![index];
                return _buildNotebookItem(notebook, selectedChild);
              },
              childCount: groupedNotebooks[monthKey]!.length,
            ),
          ),
        ],
      ],
    );
  }

  String _getMonthKey(DateTime date) {
    final year = date.year;
    final month = date.month;
    return '$year年$month月';
  }

  bool _isVideoFile(String url) {
    if (url.isEmpty) return false;
    const videoExtensions = ['.mov', '.mp4', '.avi', '.wmv', '.flv', '.webm', '.m4v'];
    final urlLower = url.toLowerCase();
    return videoExtensions.any((ext) => urlLower.contains(ext));
  }

  Widget _buildStackedThumbnails(List<String> photoUrls) {
    if (photoUrls.isEmpty) return const SizedBox.shrink();
    
    return Stack(
      children: [
        // 背景の写真達（最大3枚）
        ...photoUrls.take(3).toList().asMap().entries.map((entry) {
          final index = entry.key;
          final url = entry.value;
          final offset = index * 4.0;
          
          return Positioned(
            left: offset,
            top: offset,
            child: Container(
              width: 80 - offset,
              height: 80 - offset,
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(8),
                boxShadow: [
                  BoxShadow(
                    color: Colors.black.withOpacity(0.1),
                    blurRadius: 4,
                    offset: const Offset(0, 2),
                  ),
                ],
              ),
              child: ClipRRect(
                borderRadius: BorderRadius.circular(8),
                child: Image.network(
                  url,
                  fit: BoxFit.cover,
                  errorBuilder: (context, error, stackTrace) {
                    return Container(
                      color: Colors.grey[300],
                      child: Icon(
                        Icons.broken_image,
                        color: Colors.grey[600],
                        size: 20,
                      ),
                    );
                  },
                ),
              ),
            ),
          );
        }).toList(),
        
        // 枚数表示バッジ（3枚以上の場合）
        if (photoUrls.length > 3)
          Positioned(
            right: 0,
            top: 0,
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
              decoration: BoxDecoration(
                color: Colors.indigo,
                borderRadius: BorderRadius.circular(12),
                boxShadow: [
                  BoxShadow(
                    color: Colors.black.withOpacity(0.2),
                    blurRadius: 4,
                    offset: const Offset(0, 2),
                  ),
                ],
              ),
              child: Text(
                '+${photoUrls.length - 3}',
                style: const TextStyle(
                  color: Colors.white,
                  fontSize: 10,
                  fontWeight: FontWeight.bold,
                ),
              ),
            ),
          ),
      ],
    );
  }

  Widget _buildNotebookItem(QueryDocumentSnapshot notebook, Child? child) {
    try {
      final data = notebook.data()! as Map<String, dynamic>;
      final status = data['status'] as String? ?? 'requested';
      
      // created_atまたはcreatedAtフィールドを柔軟に処理
      DateTime createdAt;
      try {
        final createdAtValue = data['createdAt'];
        if (createdAtValue is Timestamp) {
          createdAt = createdAtValue.toDate();
        } else {
          createdAt = DateTime.now();
        }
      } catch (e) {
        createdAt = DateTime.now();
      }
      
      final period = data['period'] as Map<String, dynamic>?;
      
      // ノートブックから写真を取得（動画ファイルは除外）
      final photoUrls = <String>[];
      if (status == 'completed' && data['topics'] != null) {
        final topics = data['topics'] as List<dynamic>? ?? [];
        for (final topic in topics) {
          if (topic is Map<String, dynamic> && topic['photo'] != null) {
            final photoUrl = topic['photo'] as String;
            // gs://スキームのURLは変換が必要なのでスキップ
            // Firebase Storageの直接URLのみを使用し、動画ファイルは除外
            if (photoUrl.startsWith('https://') && !_isVideoFile(photoUrl)) {
              photoUrls.add(photoUrl);
              if (photoUrls.length >= 3) break; // 最大３枚まで
            }
          }
        }
      }

      return Container(
        decoration: BoxDecoration(
          color: Colors.white,
          border: Border(
            bottom: BorderSide(
              color: Colors.grey[200]!,
            ),
          ),
        ),
        child: InkWell(
          onTap: status == 'completed' ? () => _viewNotebook(notebook) : null,
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // モダンなサムネイル（重なり表示）
                if (photoUrls.isNotEmpty)
                  Container(
                    width: 80,
                    height: 80,
                    margin: const EdgeInsets.only(right: 12),
                    child: _buildStackedThumbnails(photoUrls),
                  ),
                
                // コンテンツ
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      // 期間とステータス
                      Row(
                        children: [
                          Expanded(
                            child: Text(
                              _getPeriodTitle(period),
                              style: const TextStyle(
                                fontSize: 16,
                                fontWeight: FontWeight.bold,
                              ),
                            ),
                          ),
                          _buildStatusChip(status),
                        ],
                      ),
                      const SizedBox(height: 4),
                      // 日時
                      Text(
                        DateFormat('yyyy/MM/dd HH:mm').format(createdAt),
                        style: TextStyle(
                          fontSize: 12,
                          color: Colors.grey[600],
                        ),
                      ),
                      // カスタマイズ情報
                      if (data['customization'] != null) ...[
                        const SizedBox(height: 8),
                        _buildCustomizationInfo(
                          data['customization'] as Map<String, dynamic>,
                        ),
                      ],
                      
                      // アクションボタン
                      if (status == 'completed') ...[
                        const SizedBox(height: 12),
                        ElevatedButton(
                          onPressed: () => _viewNotebook(notebook),
                          style: ElevatedButton.styleFrom(
                            backgroundColor: Colors.indigo,
                            foregroundColor: Colors.white,
                            padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 10),
                            shape: RoundedRectangleBorder(
                              borderRadius: BorderRadius.circular(20),
                            ),
                            elevation: 2,
                          ),
                          child: const Text(
                            '見る',
                            style: TextStyle(fontWeight: FontWeight.w600),
                          ),
                        ),
                      ] else if (status == 'failed') ...[
                        const SizedBox(height: 8),
                        Text(
                          'ノートブックの作成に失敗しました',
                          style: TextStyle(
                            fontSize: 14,
                            color: Colors.red[700],
                          ),
                        ),
                      ],
                    ],
                  ),
                ),
              ],
            ),
          ),
        ),
      );
    } catch (e) {
      debugPrint('Error building notebook item: $e');
      return Container(
        padding: const EdgeInsets.all(16),
        child: const Text('エラー: ノートブックの表示に失敗しました'),
      );
    }
  }

  Widget _buildNotebookCard(QueryDocumentSnapshot notebook, Child? child) {
    try {
      final data = notebook.data()! as Map<String, dynamic>;

      // デバッグ: データ構造を確認
      debugPrint('Notebook ID: ${notebook.id}');
      debugPrint('Notebook data keys: ${data.keys.toList()}');

      final status = data['status'] as String? ?? 'requested';

      DateTime createdAt;
      try {
        final createdAtValue = data['createdAt'];
        if (createdAtValue is Timestamp) {
          createdAt = createdAtValue.toDate();
        } else {
          debugPrint(
            'createdAt is not Timestamp: ${createdAtValue.runtimeType}',
          );
          createdAt = DateTime.now();
        }
      } catch (e) {
        debugPrint('Error parsing createdAt: $e');
        createdAt = DateTime.now();
      }
      final period = data['period'] as Map<String, dynamic>?;

      // ノートブックから写真を取得
      final photoUrls = <String>[];
      if (status == 'completed' && data['topics'] != null) {
        final topics = data['topics'] as List<dynamic>? ?? [];
        for (final topic in topics) {
          if (topic is Map<String, dynamic> && topic['photo'] != null) {
            photoUrls.add(topic['photo'] as String);
            if (photoUrls.length >= 3) break; // 最大３枚まで
          }
        }
      }

      return Card(
        margin: const EdgeInsets.only(bottom: 16),
        elevation: status == 'completed' ? 3 : 1,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(12),
        ),
        child: InkWell(
          onTap: status == 'completed' ? () => _viewNotebook(notebook) : null,
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
                      _getStatusIcon(status),
                      color: _getStatusColor(status),
                    ),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            _getPeriodTitle(period),
                            style: const TextStyle(
                              fontSize: 18,
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                          const SizedBox(height: 4),
                          Text(
                            DateFormat('yyyy/MM/dd HH:mm').format(createdAt),
                            style: TextStyle(
                              fontSize: 12,
                              color: Colors.grey[600],
                            ),
                          ),
                        ],
                      ),
                    ),
                    _buildStatusChip(status),
                  ],
                ),

                // フォトプレビュー
                if (photoUrls.isNotEmpty) ...[
                  const SizedBox(height: 12),
                  SizedBox(
                    height: 80,
                    child: ListView.builder(
                      scrollDirection: Axis.horizontal,
                      itemCount: photoUrls.length,
                      itemBuilder: (context, index) {
                        return Container(
                          width: 80,
                          height: 80,
                          margin: EdgeInsets.only(
                            right: index < photoUrls.length - 1 ? 8 : 0,
                          ),
                          decoration: BoxDecoration(
                            borderRadius: BorderRadius.circular(8),
                            image: DecorationImage(
                              image: NetworkImage(photoUrls[index]),
                              fit: BoxFit.cover,
                            ),
                          ),
                        );
                      },
                    ),
                  ),
                ],

                // カスタマイズ情報
                if (data['customization'] != null) ...[
                  const SizedBox(height: 12),
                  _buildCustomizationInfo(
                    data['customization'] as Map<String, dynamic>,
                  ),
                ],

                // アクションボタン
                if (status == 'completed') ...[
                  const SizedBox(height: 12),
                  _buildActionButtons(notebook),
                ] else if (status == 'failed') ...[
                  const SizedBox(height: 12),
                  Text(
                    'ノートブックの作成に失敗しました',
                    style: TextStyle(
                      fontSize: 14,
                      color: Colors.red[700],
                    ),
                  ),
                ],
              ],
            ),
          ),
        ),
      );
    } catch (e, stackTrace) {
      debugPrint('Error building notebook card: $e');
      debugPrint('Stack trace: $stackTrace');
      // エラー時は簡単なカードを表示
      return const Card(
        margin: EdgeInsets.only(bottom: 16),
        child: Padding(
          padding: EdgeInsets.all(16),
          child: Text('エラー: ノートブックの表示に失敗しました'),
        ),
      );
    }
  }

  IconData _getStatusIcon(String status) {
    switch (status) {
      case 'completed':
        return Icons.menu_book;
      case 'generating':
        return Icons.auto_awesome;
      case 'failed':
        return Icons.error_outline;
      default:
        return Icons.pending;
    }
  }

  Color _getStatusColor(String status) {
    switch (status) {
      case 'completed':
        return Colors.green;
      case 'generating':
        return Colors.orange;
      case 'failed':
        return Colors.red;
      default:
        return Colors.blue;
    }
  }

  String _getPeriodTitle(Map<String, dynamic>? period) {
    if (period == null) return 'ノートブック';

    // startとendは文字列（ISO形式）またはTimestampの可能性がある
    DateTime? start;
    DateTime? end;

    try {
      final startValue = period['start'];
      if (startValue is Timestamp) {
        start = startValue.toDate();
      } else if (startValue is String) {
        start = DateTime.parse(startValue);
      }

      final endValue = period['end'];
      if (endValue is Timestamp) {
        end = endValue.toDate();
      } else if (endValue is String) {
        end = DateTime.parse(endValue);
      }
    } catch (e) {
      debugPrint('Error parsing period dates: $e');
    }

    final type = period['type'] as String?;

    if (start == null || end == null) return 'ノートブック';

    if (type == 'week') {
      return '${DateFormat('M月d日').format(start)}の週';
    } else if (type == 'month') {
      return DateFormat('yyyy年M月').format(start);
    } else {
      return '${DateFormat('M/d').format(start)} 〜 ${DateFormat('M/d').format(end)}';
    }
  }

  Widget _buildStatusChip(String status) {
    String label;
    Color bgColor;
    Color textColor;

    switch (status) {
      case 'completed':
        label = '作成済み';
        bgColor = Colors.green[50]!;
        textColor = Colors.green[700]!;
      case 'generating':
        label = '生成中';
        bgColor = Colors.orange[50]!;
        textColor = Colors.orange[700]!;
      case 'failed':
        label = '失敗';
        bgColor = Colors.red[50]!;
        textColor = Colors.red[700]!;
      default:
        label = '処理待ち';
        bgColor = Colors.blue[50]!;
        textColor = Colors.blue[700]!;
    }

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      decoration: BoxDecoration(
        color: bgColor,
        borderRadius: BorderRadius.circular(20),
      ),
      child: Text(
        label,
        style: TextStyle(
          fontSize: 12,
          color: textColor,
          fontWeight: FontWeight.w500,
        ),
      ),
    );
  }

  Widget _buildCustomizationInfo(Map<String, dynamic> customization) {
    final tone = customization['tone'] as String?;
    final focus = customization['focus'] as String?;

    if ((tone?.isEmpty ?? true) && (focus?.isEmpty ?? true)) {
      return const SizedBox.shrink();
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        if (tone?.isNotEmpty ?? false) ...[
          Row(
            children: [
              Icon(Icons.palette, size: 16, color: Colors.grey[600]),
              const SizedBox(width: 4),
              Expanded(
                child: Text(
                  tone!,
                  style: TextStyle(
                    fontSize: 12,
                    color: Colors.grey[600],
                  ),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
              ),
            ],
          ),
        ],
        if (focus?.isNotEmpty ?? false) ...[
          const SizedBox(height: 4),
          Row(
            children: [
              Icon(
                Icons.center_focus_strong,
                size: 16,
                color: Colors.grey[600],
              ),
              const SizedBox(width: 4),
              Expanded(
                child: Text(
                  focus!,
                  style: TextStyle(
                    fontSize: 12,
                    color: Colors.grey[600],
                  ),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
              ),
            ],
          ),
        ],
      ],
    );
  }

  Widget _buildActionButtons(QueryDocumentSnapshot notebook) {
    return Row(
      children: [
        Expanded(
          child: ElevatedButton.icon(
            onPressed: () => _viewNotebook(notebook),
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
            onPressed: () => _shareNotebookById(notebook.id),
            icon: const Icon(Icons.share),
            color: Colors.indigo,
            tooltip: 'ノートブックを共有',
          ),
        ),
      ],
    );
  }

  Future<void> _viewNotebook(QueryDocumentSnapshot notebookDoc) async {
    final data = notebookDoc.data()! as Map<String, dynamic>;

    // WebViewで表示
    const baseUrl = 'https://hackason-464007.web.app';
    final notebookUrl =
        '$baseUrl/children/$_selectedChildId/notebooks/${notebookDoc.id}';

    Navigator.of(context).push(
      MaterialPageRoute(
        builder: (context) => NotebookWebViewScreen(
          notebookUrl: notebookUrl,
          title: data['nickname'] != null
              ? '${data['nickname']}のノートブック'
              : 'ノートブック',
          childId: _selectedChildId,
          notebookId: notebookDoc.id,
        ),
      ),
    );
  }

  Future<void> _shareNotebookById(String notebookId) async {
    try {
      // Create the web URL for the notebook
      const baseUrl = 'https://hackason-464007.web.app';
      final notebookUrl =
          '$baseUrl/children/$_selectedChildId/notebooks/$notebookId';

      final shareText =
          '''
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
}

class NotebookDetailScreen extends StatelessWidget {
  final Notebook notebook;
  final String childId;

  const NotebookDetailScreen({
    required this.notebook,
    required this.childId,
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
                final notebookUrl =
                    '$baseUrl/children/$childId/notebooks/${notebook.id}';

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
