import 'dart:typed_data';

import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:firebase_storage/firebase_storage.dart';
import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:kids_diary/models/analysis_result.dart';
import 'package:kids_diary/models/media_upload.dart';
import 'package:kids_diary/providers/auth_provider.dart';
import 'package:kids_diary/providers/children_provider.dart';
import 'package:kids_diary/services/analysis_result_service.dart';
import 'package:kids_diary/services/video_thumbnail_service.dart';
import 'package:provider/provider.dart';

class NotebookCreationScreen extends StatefulWidget {
  final String childId;

  const NotebookCreationScreen({
    required this.childId,
    super.key,
  });

  @override
  State<NotebookCreationScreen> createState() => _NotebookCreationScreenState();
}

class _NotebookCreationScreenState extends State<NotebookCreationScreen> {
  final FirebaseFirestore _firestore = FirebaseFirestore.instance;
  final AnalysisResultService _analysisService = AnalysisResultService();
  
  // 期間選択
  DateTime _startDate = DateTime.now().subtract(const Duration(days: 7));
  DateTime _endDate = DateTime.now();
  String _periodType = 'week'; // week, month, custom
  
  // カスタムプロンプト
  final TextEditingController _toneController = TextEditingController();
  final TextEditingController _focusController = TextEditingController();
  
  // 分析結果とメディア情報
  List<AnalysisResult> _analysisResults = [];
  Map<String, MediaUpload> _mediaUploads = {};
  final Set<String> _selectedAnalysisIds = {};
  bool _isLoading = true;
  bool _isContentLoading = false;
  
  @override
  void initState() {
    super.initState();
    _setWeekPeriod();
    _loadAnalysisResults();
  }
  
  @override
  void dispose() {
    _toneController.dispose();
    _focusController.dispose();
    super.dispose();
  }
  
  void _setWeekPeriod() {
    final now = DateTime.now();
    final weekday = now.weekday;
    final daysFromMonday = weekday - 1;
    _startDate = DateTime(now.year, now.month, now.day).subtract(Duration(days: daysFromMonday + 7));
    _endDate = _startDate.add(const Duration(days: 6));
  }
  
  void _setMonthPeriod() {
    final now = DateTime.now();
    _startDate = DateTime(now.year, now.month - 1, 1);
    _endDate = DateTime(now.year, now.month, 1).subtract(const Duration(days: 1));
  }
  
  Future<void> _loadAnalysisResults() async {
    try {
      setState(() {
        _isContentLoading = true;
        _mediaUploads.clear();
      });
      
      // 1. 分析結果を取得
      final results = await _analysisService.getChildAnalysisResults(widget.childId);
      
      // 2. 各分析結果に対応するMediaUploadを取得
      final List<AnalysisResult> filteredResults = [];
      
      for (final result in results) {
        try {
          // MediaUploadを取得（mediaUriでmedia_uploadsを検索）
          final mediaUploadQuery = await _firestore
              .collection('media_uploads')
              .where('media_uri', isEqualTo: result.mediaUri)
              .limit(1)
              .get();
          
          if (mediaUploadQuery.docs.isNotEmpty) {
            final mediaUpload = MediaUpload.fromJson(
              mediaUploadQuery.docs.first.data(),
              mediaUploadQuery.docs.first.id,
            );
            
            // capturedAtまたはuploadedAtで期間フィルター
            final photoDate = mediaUpload.capturedAt ?? mediaUpload.uploadedAt;
            if (photoDate.isAfter(_startDate.subtract(const Duration(days: 1))) &&
                photoDate.isBefore(_endDate.add(const Duration(days: 1)))) {
              filteredResults.add(result);
              _mediaUploads[result.id] = mediaUpload;
            }
          }
        } catch (e) {
          debugPrint('Error loading media upload for result ${result.id}: $e');
          // エラーが発生しても、createdAtでフォールバック
          if (result.createdAt.isAfter(_startDate.subtract(const Duration(days: 1))) &&
              result.createdAt.isBefore(_endDate.add(const Duration(days: 1)))) {
            filteredResults.add(result);
          }
        }
      }
      
      setState(() {
        _analysisResults = filteredResults;
        // デフォルトで全て選択
        _selectedAnalysisIds
          ..clear()
          ..addAll(filteredResults.map((r) => r.id));
        _isLoading = false;
        _isContentLoading = false;
      });
    } catch (e) {
      debugPrint('Error loading analysis results: $e');
      setState(() {
        _isLoading = false;
        _isContentLoading = false;
      });
      
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('分析結果の読み込みに失敗しました'),
            backgroundColor: Colors.red,
          ),
        );
      }
    }
  }
  
  Future<void> _selectDateRange() async {
    final picked = await showDateRangePicker(
      context: context,
      firstDate: DateTime(2020),
      lastDate: DateTime.now(),
      initialDateRange: DateTimeRange(start: _startDate, end: _endDate),
    );
    
    if (picked != null) {
      setState(() {
        _startDate = picked.start;
        _endDate = picked.end;
        _periodType = 'custom';
      });
      _loadAnalysisResults();
    }
  }
  
  Future<void> _createNotebook() async {
    if (_selectedAnalysisIds.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('少なくとも1つのコンテンツを選択してください'),
          backgroundColor: Colors.orange,
        ),
      );
      return;
    }
    
    try {
      final authProvider = context.read<AuthProvider>();
      final user = authProvider.user;
      if (user == null) return;
      
      // ノートブックリクエストを作成
      final notebookData = {
        'childId': widget.childId,
        'userId': user.uid,
        'createdAt': FieldValue.serverTimestamp(),
        'status': 'requested',
        'period': {
          'start': Timestamp.fromDate(_startDate),
          'end': Timestamp.fromDate(_endDate),
          'type': _periodType,
        },
        'customization': {
          'tone': _toneController.text.trim(),
          'focus': _focusController.text.trim(),
        },
        'sources': _analysisResults
            .where((result) => _selectedAnalysisIds.contains(result.id))
            .map((result) => {
                  'analysisId': result.id,
                  'mediaId': result.mediaUri,
                  'included': true,
                })
            .toList(),
      };
      
      // Firestoreに保存
      await _firestore
          .collection('children')
          .doc(widget.childId)
          .collection('notebooks')
          .add(notebookData);
      
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('ノートブックの作成を開始しました'),
            backgroundColor: Colors.green,
          ),
        );
        Navigator.of(context).pop(true);
      }
    } catch (e) {
      debugPrint('Error creating notebook: $e');
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('ノートブックの作成に失敗しました'),
            backgroundColor: Colors.red,
          ),
        );
      }
    }
  }
  
  @override
  Widget build(BuildContext context) {
    final childrenProvider = context.watch<ChildrenProvider>();
    final child = childrenProvider.getChildById(widget.childId);
    
    return Scaffold(
      appBar: AppBar(
        title: Text('${child?.nickname ?? ''}のノートブック作成'),
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : Column(
              children: [
                Expanded(
                  child: SingleChildScrollView(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        // 期間選択セクション
                        _buildPeriodSection(),
                        const Divider(height: 1),
                        
                        // コンテンツ選択セクション
                        _buildContentSection(),
                        const Divider(height: 1),
                        
                        // カスタマイズセクション
                        _buildCustomizationSection(),
                      ],
                    ),
                  ),
                ),
                // 作成ボタン
                Container(
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(
                    color: Theme.of(context).scaffoldBackgroundColor,
                    boxShadow: [
                      BoxShadow(
                        color: Colors.black.withOpacity(0.1),
                        blurRadius: 4,
                        offset: const Offset(0, -2),
                      ),
                    ],
                  ),
                  child: SafeArea(
                    child: SizedBox(
                      width: double.infinity,
                      height: 48,
                      child: ElevatedButton.icon(
                        onPressed: _createNotebook,
                        icon: const Icon(Icons.auto_awesome),
                        label: const Text('ノートブックを作成'),
                        style: ElevatedButton.styleFrom(
                          backgroundColor: Colors.indigo,
                          foregroundColor: Colors.white,
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(8),
                          ),
                        ),
                      ),
                    ),
                  ),
                ),
              ],
            ),
    );
  }
  
  Widget _buildPeriodSection() {
    return Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
            const Text(
              '期間選択',
              style: TextStyle(
                fontSize: 18,
                fontWeight: FontWeight.bold,
              ),
            ),
            const SizedBox(height: 16),
            
            // テンプレートボタン
            Wrap(
              spacing: 8,
              children: [
                ChoiceChip(
                  label: const Text('先週'),
                  selected: _periodType == 'week',
                  onSelected: (selected) {
                    if (selected) {
                      setState(() {
                        _periodType = 'week';
                        _setWeekPeriod();
                      });
                      _loadAnalysisResults();
                    }
                  },
                ),
                ChoiceChip(
                  label: const Text('先月'),
                  selected: _periodType == 'month',
                  onSelected: (selected) {
                    if (selected) {
                      setState(() {
                        _periodType = 'month';
                        _setMonthPeriod();
                      });
                      _loadAnalysisResults();
                    }
                  },
                ),
                ChoiceChip(
                  label: const Text('カスタム'),
                  selected: _periodType == 'custom',
                  onSelected: (selected) {
                    if (selected) {
                      _selectDateRange();
                    }
                  },
                ),
              ],
            ),
            const SizedBox(height: 16),
            
            // 選択された期間の表示
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: Colors.grey[100],
                borderRadius: BorderRadius.circular(8),
              ),
              child: Row(
                children: [
                  const Icon(Icons.date_range, size: 20),
                  const SizedBox(width: 8),
                  Text(
                    '${DateFormat('yyyy/MM/dd').format(_startDate)} 〜 ${DateFormat('yyyy/MM/dd').format(_endDate)}',
                    style: const TextStyle(fontWeight: FontWeight.w500),
                  ),
                ],
              ),
            ),
          ],
      ),
    );
  }
  
  Widget _buildContentSection() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Padding(
          padding: const EdgeInsets.all(16),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              const Text(
                'コンテンツ選択',
                style: TextStyle(
                  fontSize: 18,
                  fontWeight: FontWeight.bold,
                ),
              ),
              Text(
                '${_selectedAnalysisIds.length}/${_analysisResults.length}件選択',
                style: TextStyle(
                  color: Colors.grey[600],
                  fontSize: 14,
                ),
              ),
            ],
          ),
        ),
        
        if (_isContentLoading)
          Container(
            height: 200,
            alignment: Alignment.center,
            child: const CircularProgressIndicator(),
          )
        else if (_analysisResults.isEmpty)
          Container(
            height: 200,
            alignment: Alignment.center,
            child: const Text(
              'この期間に分析済みのコンテンツがありません',
              style: TextStyle(color: Colors.grey),
            ),
          )
        else
          SizedBox(
            height: 200,
            child: ListView.builder(
              scrollDirection: Axis.horizontal,
              padding: const EdgeInsets.symmetric(horizontal: 16),
              itemCount: _analysisResults.length,
              itemBuilder: (context, index) {
                final result = _analysisResults[index];
                return _buildContentThumbnail(result);
              },
            ),
          ),
        const SizedBox(height: 16),
      ],
    );
  }
  
  Widget _buildContentThumbnail(AnalysisResult result) {
    final isSelected = _selectedAnalysisIds.contains(result.id);
    final mediaUpload = _mediaUploads[result.id];
    
    return GestureDetector(
      onTap: () {
        setState(() {
          if (isSelected) {
            _selectedAnalysisIds.remove(result.id);
          } else {
            _selectedAnalysisIds.add(result.id);
          }
        });
      },
      child: Container(
        width: 150,
        margin: const EdgeInsets.only(right: 12),
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(12),
          border: Border.all(
            color: isSelected ? Colors.indigo : Colors.grey[300]!,
            width: isSelected ? 3 : 1,
          ),
        ),
        child: Stack(
          children: [
            // サムネイル画像
            ClipRRect(
              borderRadius: BorderRadius.circular(11),
              child: FutureBuilder<String?>(
                future: _getMediaUrl(result.mediaUri),
                builder: (context, snapshot) {
                  if (snapshot.connectionState == ConnectionState.waiting) {
                    return Container(
                      width: double.infinity,
                      height: double.infinity,
                      color: Colors.grey[200],
                      child: const Center(
                        child: CircularProgressIndicator(strokeWidth: 2),
                      ),
                    );
                  }
                  
                  // URLが取得できなかった場合はプレースホルダー画像を表示
                  if (!snapshot.hasData || snapshot.data == null) {
                    return Container(
                      width: double.infinity,
                      height: double.infinity,
                      color: Colors.grey[300],
                      child: Column(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          Icon(
                            Icons.image_outlined,
                            color: Colors.grey[600],
                            size: 40,
                          ),
                          const SizedBox(height: 4),
                          Text(
                            '画像',
                            style: TextStyle(
                              color: Colors.grey[600],
                              fontSize: 12,
                            ),
                          ),
                        ],
                      ),
                    );
                  }
                  
                  // 動画の場合はサムネイルを表示
                  if (mediaUpload != null && mediaUpload.mediaType == MediaType.video) {
                    return FutureBuilder<Uint8List?>(
                      future: VideoThumbnailService().getThumbnail(snapshot.data!),
                      builder: (context, thumbnailSnapshot) {
                        return Stack(
                          fit: StackFit.expand,
                          children: [
                            if (thumbnailSnapshot.hasData && thumbnailSnapshot.data != null)
                              Image.memory(
                                thumbnailSnapshot.data!,
                                fit: BoxFit.cover,
                              )
                            else
                              const ColoredBox(
                                color: Colors.black,
                                child: Icon(
                                  Icons.video_library,
                                  color: Colors.white,
                                  size: 32,
                                ),
                              ),
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
                    );
                  } else {
                    // 画像の場合はそのまま表示
                    return Image.network(
                      snapshot.data!,
                      width: double.infinity,
                      height: double.infinity,
                      fit: BoxFit.cover,
                      errorBuilder: (context, error, stackTrace) {
                        return Container(
                          width: double.infinity,
                          height: double.infinity,
                          color: Colors.grey[300],
                          child: Icon(
                            Icons.broken_image,
                            color: Colors.grey[600],
                            size: 40,
                          ),
                        );
                      },
                    );
                  }
                },
              ),
            ),
            
            // 選択チェックマーク
            if (isSelected)
              Positioned(
                top: 8,
                right: 8,
                child: Container(
                  width: 28,
                  height: 28,
                  decoration: BoxDecoration(
                    color: Colors.indigo,
                    shape: BoxShape.circle,
                    boxShadow: [
                      BoxShadow(
                        color: Colors.black.withOpacity(0.3),
                        blurRadius: 4,
                        offset: const Offset(0, 2),
                      ),
                    ],
                  ),
                  child: const Icon(
                    Icons.check,
                    color: Colors.white,
                    size: 18,
                  ),
                ),
              ),
            
            // 情報オーバーレイ
            Positioned(
              bottom: 0,
              left: 0,
              right: 0,
              child: Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  borderRadius: const BorderRadius.only(
                    bottomLeft: Radius.circular(11),
                    bottomRight: Radius.circular(11),
                  ),
                  gradient: LinearGradient(
                    begin: Alignment.topCenter,
                    end: Alignment.bottomCenter,
                    colors: [
                      Colors.transparent,
                      Colors.black.withOpacity(0.7),
                    ],
                  ),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(
                      result.emotionalTitle.isNotEmpty ? result.emotionalTitle : '分析中...',
                      style: const TextStyle(
                        color: Colors.white,
                        fontSize: 12,
                        fontWeight: FontWeight.bold,
                      ),
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                    ),
                    const SizedBox(height: 2),
                    Text(
                      _getPhotoDateText(result),
                      style: const TextStyle(
                        color: Colors.white70,
                        fontSize: 10,
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
  
  Future<String?> _getMediaUrl(String mediaUri) async {
    try {
      // mediaUriがすでにURLの場合はそのまま返す
      if (mediaUri.startsWith('http')) {
        return mediaUri;
      }
      
      // gsスキームの場合は処理
      if (mediaUri.startsWith('gs://')) {
        final ref = FirebaseStorage.instance.refFromURL(mediaUri);
        return await ref.getDownloadURL();
      }
      
      // それ以外は通常のパスとして処理
      final ref = FirebaseStorage.instance.ref(mediaUri);
      return await ref.getDownloadURL();
    } catch (e) {
      debugPrint('Error getting media URL for $mediaUri: $e');
      // エラー時はnullを返す
      return null;
    }
  }
  
  String _getPhotoDateText(AnalysisResult result) {
    final mediaUpload = _mediaUploads[result.id];
    if (mediaUpload != null) {
      final photoDate = mediaUpload.capturedAt ?? mediaUpload.uploadedAt;
      return DateFormat('MM/dd').format(photoDate);
    }
    // フォールバック
    return DateFormat('MM/dd').format(result.createdAt);
  }
  
  Widget _buildCustomizationSection() {
    return Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'AIへのリクエスト（任意）',
            style: TextStyle(
              fontSize: 18,
              fontWeight: FontWeight.bold,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            'ノートブックをどのように仕上げたいか、AIに伝えることができます',
            style: TextStyle(
              fontSize: 14,
              color: Colors.grey[600],
            ),
          ),
          const SizedBox(height: 16),
          
          // 文章のスタイル
          TextField(
            controller: _toneController,
            decoration: const InputDecoration(
              labelText: 'どんな文章にしたいですか？',
              hintText: '例：温かくて優しい文章で、将来子どもと一緒に読み返せるように',
              border: OutlineInputBorder(),
              helperText: '文章の雰囲気や読む人を意識した表現をAIに伝えます',
            ),
            maxLines: 2,
          ),
          const SizedBox(height: 16),
          
          // 注目してほしいこと
          TextField(
            controller: _focusController,
            decoration: const InputDecoration(
              labelText: '特に注目してほしいことは？',
              hintText: '例：運動会での頑張りや、お友達との関わり方について',
              border: OutlineInputBorder(),
              helperText: 'この期間の特別な出来事や成長をAIに伝えます',
            ),
            maxLines: 2,
          ),
        ],
      ),
    );
  }
}
