import 'dart:convert';

import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:firebase_auth/firebase_auth.dart';
import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;
import 'package:mobile/models/media_upload.dart';
import 'package:mobile/models/notebook.dart';

class NotebookService {
  final FirebaseFirestore _firestore = FirebaseFirestore.instance;
  final FirebaseAuth _auth = FirebaseAuth.instance;

  // Cloud Function URL
  static const String _baseUrl =
      'https://us-central1-hackason-464007.cloudfunctions.net';
  static const String _generateNotebookUrl = '$_baseUrl/generate_notebook_http';

  /// ノートブック生成APIを呼び出す
  Future<NotebookGenerationResponse> generateNotebook({
    required String childId,
    required String startDate,
    required String endDate,
    Map<String, dynamic>? childInfo,
  }) async {
    try {
      debugPrint('=== generateNotebook API CALL START ===');
      debugPrint('URL: $_generateNotebookUrl');
      debugPrint('Child ID: $childId');
      debugPrint('Start Date: $startDate');
      debugPrint('End Date: $endDate');
      debugPrint('Child Info: $childInfo');

      final request = NotebookGenerationRequest(
        childId: childId,
        startDate: startDate,
        endDate: endDate,
        childInfo: childInfo,
      );

      final requestBody = jsonEncode(request.toJson());
      debugPrint('Request body: $requestBody');

      // 一時的に認証を無効化してテスト
      final headers = <String, String>{
        'Content-Type': 'application/json',
      };

      debugPrint('Sending request without authentication for testing');

      debugPrint('Making HTTP POST request...');
      final response = await http.post(
        Uri.parse(_generateNotebookUrl),
        headers: headers,
        body: requestBody,
      );

      debugPrint('HTTP Response Status: ${response.statusCode}');
      debugPrint('HTTP Response Headers: ${response.headers}');
      debugPrint('HTTP Response Body: ${response.body}');

      if (response.statusCode == 200 || response.statusCode == 202) {
        try {
          final responseData =
              jsonDecode(response.body) as Map<String, dynamic>;
          debugPrint('Successfully parsed JSON response');
          final result = NotebookGenerationResponse.fromJson(responseData);
          debugPrint('=== generateNotebook API CALL SUCCESS ===');
          return result;
        } catch (jsonError, jsonStackTrace) {
          debugPrint('=== JSON PARSE ERROR ===');
          debugPrint('JSON Parse Error: $jsonError');
          debugPrint('JSON Parse Stack Trace: $jsonStackTrace');
          debugPrint('Raw response body: ${response.body}');
          debugPrint('=== END JSON PARSE ERROR ===');
          return NotebookGenerationResponse(
            status: 'error',
            message: 'レスポンスの解析に失敗しました',
            error: 'JSON Parse Error: $jsonError',
          );
        }
      } else {
        debugPrint('HTTP Error - Status: ${response.statusCode}');
        return NotebookGenerationResponse(
          status: 'error',
          message: 'サーバーエラーが発生しました',
          error: 'HTTP ${response.statusCode}: ${response.body}',
        );
      }
    } catch (e, stackTrace) {
      debugPrint('=== NETWORK ERROR in generateNotebook ===');
      debugPrint('Error type: ${e.runtimeType}');
      debugPrint('Error message: $e');
      debugPrint('Stack trace: $stackTrace');
      debugPrint('=== END NETWORK ERROR ===');
      return NotebookGenerationResponse(
        status: 'error',
        message: 'ネットワークエラーが発生しました',
        error: e.toString(),
      );
    }
  }

  /// 子供のノートブック一覧を取得
  Future<List<Notebook>> getChildNotebooks(String childId) async {
    try {
      debugPrint('=== getChildNotebooks START ===');
      debugPrint('Child ID: $childId');
      debugPrint('Firestore path: children/$childId/notebooks');

      final querySnapshot = await _firestore
          .collection('children')
          .doc(childId)
          .collection('notebooks')
          .orderBy('created_at', descending: true)
          .get();

      debugPrint('Found ${querySnapshot.docs.length} notebook documents');

      final notebooks = <Notebook>[];
      for (final doc in querySnapshot.docs) {
        try {
          debugPrint('Processing notebook document: ${doc.id}');
          final notebook = Notebook.fromJson(doc.data(), doc.id);
          notebooks.add(notebook);
          debugPrint('Successfully parsed notebook: ${notebook.id}');
        } catch (parseError, parseStackTrace) {
          debugPrint('=== NOTEBOOK PARSE ERROR ===');
          debugPrint('Document ID: ${doc.id}');
          debugPrint('Document data: ${doc.data()}');
          debugPrint('Parse error: $parseError');
          debugPrint('Parse stack trace: $parseStackTrace');
          debugPrint('=== END NOTEBOOK PARSE ERROR ===');
        }
      }

      debugPrint('Successfully loaded ${notebooks.length} notebooks');
      debugPrint('=== getChildNotebooks SUCCESS ===');
      return notebooks;
    } catch (e, stackTrace) {
      debugPrint('=== ERROR in getChildNotebooks ===');
      debugPrint('Child ID: $childId');
      debugPrint('Error type: ${e.runtimeType}');
      debugPrint('Error message: $e');
      debugPrint('Stack trace: $stackTrace');
      debugPrint('=== END ERROR ===');
      return [];
    }
  }

  /// 特定のノートブックを取得
  Future<Notebook?> getNotebook(String childId, String notebookId) async {
    try {
      debugPrint('Getting notebook: $notebookId for child: $childId');

      final doc = await _firestore
          .collection('children')
          .doc(childId)
          .collection('notebooks')
          .doc(notebookId)
          .get();

      if (!doc.exists) {
        debugPrint('Notebook not found: $notebookId');
        return null;
      }

      return Notebook.fromJson(doc.data()!, doc.id);
    } catch (e) {
      debugPrint('Error getting notebook: $e');
      return null;
    }
  }

  /// ノートブックをリアルタイムで監視
  Stream<List<Notebook>> watchChildNotebooks(String childId) {
    return _firestore
        .collection('children')
        .doc(childId)
        .collection('notebooks')
        .orderBy('created_at', descending: true)
        .snapshots()
        .map(
          (snapshot) => snapshot.docs
              .map((doc) => Notebook.fromJson(doc.data(), doc.id))
              .toList(),
        );
  }

  /// 週の開始日を取得（月曜日始まり）
  DateTime getWeekStart(DateTime date) {
    final weekday = date.weekday;
    // Dartの weekday: 1=Monday, 7=Sunday
    // 月曜日始まりにするため、月曜日の場合は0、火曜日は1...日曜日は6
    final daysFromMonday = weekday - 1;
    return DateTime(
      date.year,
      date.month,
      date.day,
    ).subtract(Duration(days: daysFromMonday));
  }

  /// 週の終了日を取得（日曜日終わり）
  DateTime getWeekEnd(DateTime date) {
    final weekStart = getWeekStart(date);
    return weekStart.add(
      const Duration(days: 6, hours: 23, minutes: 59, seconds: 59),
    );
  }

  /// 特定の週のノートブック生成
  Future<NotebookGenerationResponse> generateWeeklyNotebook({
    required String childId,
    required DateTime weekDate,
    Map<String, dynamic>? childInfo,
  }) async {
    final weekStart = getWeekStart(weekDate);
    final weekEnd = getWeekEnd(weekDate);

    final startDate =
        '${weekStart.year.toString().padLeft(4, '0')}-'
        '${weekStart.month.toString().padLeft(2, '0')}-'
        '${weekStart.day.toString().padLeft(2, '0')}';

    final endDate =
        '${weekEnd.year.toString().padLeft(4, '0')}-'
        '${weekEnd.month.toString().padLeft(2, '0')}-'
        '${weekEnd.day.toString().padLeft(2, '0')}';

    return generateNotebook(
      childId: childId,
      startDate: startDate,
      endDate: endDate,
      childInfo: childInfo,
    );
  }

  /// 週のタイトルを生成
  String getWeekTitle(DateTime weekDate) {
    final weekStart = getWeekStart(weekDate);
    final weekEnd = getWeekEnd(weekDate);

    if (weekStart.month == weekEnd.month) {
      return '${weekStart.month}月第${_getWeekNumber(weekStart)}週'
          ' (${weekStart.day}日-${weekEnd.day}日)';
    } else {
      return '${weekStart.month}月${weekStart.day}日-${weekEnd.month}月${weekEnd.day}日';
    }
  }

  /// 月の第何週かを計算
  int _getWeekNumber(DateTime date) {
    final firstDayOfMonth = DateTime(date.year, date.month);
    final firstMonday = getWeekStart(firstDayOfMonth);
    final targetMonday = getWeekStart(date);

    final diffInDays = targetMonday.difference(firstMonday).inDays;
    return (diffInDays ~/ 7) + 1;
  }

  /// 週のメディアを取得
  Future<List<MediaUpload>> getWeekMedia({
    required String childId,
    required DateTime weekStart,
    required DateTime weekEnd,
  }) async {
    try {
      debugPrint('=== getWeekMedia START ===');
      debugPrint('childId: $childId');
      debugPrint('weekStart: $weekStart');
      debugPrint('weekEnd: $weekEnd');

      // captured_atがある場合とない場合（uploaded_atのみ）の両方を取得する必要があるため、
      // まず全体を取得してから、アプリ側でフィルタリングする
      final user = _auth.currentUser;
      if (user == null) {
        debugPrint('No authenticated user');
        return [];
      }
      debugPrint('user.uid: ${user.uid}');

      // タイムラインと同じ条件で取得（child_idでフィルタリングしない）
      final mediaQuery = await _firestore
          .collection('media_uploads')
          .where('user_id', isEqualTo: user.uid)
          .where('is_deleted', isEqualTo: false)
          .orderBy('uploaded_at', descending: false)
          .get();

      debugPrint('Found ${mediaQuery.docs.length} media uploads for child');

      final allMedia = mediaQuery.docs
          .map((doc) => MediaUpload.fromJson(doc.data(), doc.id))
          .toList();

      debugPrint('Parsed ${allMedia.length} media uploads');
      for (final media in allMedia) {
        final targetDate = media.capturedAt ?? media.uploadedAt;
        debugPrint(
          'Media ${media.id}: targetDate=$targetDate, childId=${media.childId}',
        );
      }

      // アプリ側で週の範囲とchild_idでフィルタリング
      final weekEndPlusOne = weekEnd.add(const Duration(days: 1));
      final filteredMedia = allMedia.where((media) {
        // child_idでフィルタリング
        if (media.childId != childId) return false;

        // capturedAtがある場合はそれを使用、ない場合はuploadedAtを使用
        final targetDate = media.capturedAt ?? media.uploadedAt;
        final inRange =
            targetDate.isAfter(
              weekStart.subtract(const Duration(microseconds: 1)),
            ) &&
            targetDate.isBefore(weekEndPlusOne);
        debugPrint(
          'Media ${media.id}: targetDate=$targetDate, childId=${media.childId}, inRange=$inRange',
        );
        return inRange;
      }).toList();

      debugPrint(
        'Filtered to ${filteredMedia.length} media uploads in week range',
      );
      debugPrint('=== getWeekMedia END ===');
      return filteredMedia;
    } catch (e) {
      debugPrint('Error getting week media: $e');
      return [];
    }
  }

  /// 現在の週を含む過去数週間のノートブック情報を取得
  Future<List<WeekInfo>> getRecentWeeks({
    required String childId,
    int weeksCount = 8,
  }) async {
    final now = DateTime.now();
    final weeks = <WeekInfo>[];

    // 既存のノートブックを取得
    final existingNotebooks = await getChildNotebooks(childId);
    final notebookMap = <String, Notebook>{};

    for (final notebook in existingNotebooks) {
      // ノートブックIDから週を特定（例: 2024_06_week4）
      notebookMap[notebook.id] = notebook;
    }

    // 過去数週間の情報を生成
    for (var i = 0; i < weeksCount; i++) {
      final weekDate = now.subtract(Duration(days: i * 7));
      final weekStart = getWeekStart(weekDate);
      final weekEnd = getWeekEnd(weekDate);

      // ノートブックIDを生成（推測）
      final year = weekStart.year;
      final month = weekStart.month.toString().padLeft(2, '0');
      final weekNumber = _getWeekNumber(weekStart);
      final expectedNotebookId = '${year}_${month}_week$weekNumber';

      final existingNotebook = notebookMap[expectedNotebookId];

      // その週のメディアを取得
      final weekMedia = await getWeekMedia(
        childId: childId,
        weekStart: weekStart,
        weekEnd: weekEnd,
      );

      weeks.add(
        WeekInfo(
          weekStart: weekStart,
          weekEnd: weekEnd,
          title: getWeekTitle(weekDate),
          canGenerate:
              weekEnd.isBefore(now) &&
              weekMedia.isNotEmpty, // 過去の週でメディアがある場合のみ生成可能
          notebook: existingNotebook,
          weekMedia: weekMedia,
        ),
      );
    }

    return weeks;
  }
}

class WeekInfo {
  final DateTime weekStart;
  final DateTime weekEnd;
  final String title;
  final Notebook? notebook;
  final bool canGenerate;
  final List<MediaUpload> weekMedia;

  WeekInfo({
    required this.weekStart,
    required this.weekEnd,
    required this.title,
    required this.canGenerate,
    this.notebook,
    this.weekMedia = const [],
  });

  bool get hasNotebook => notebook != null;
  bool get isCurrentWeek {
    final now = DateTime.now();
    return weekStart.isBefore(now) && weekEnd.isAfter(now);
  }

  bool get hasMedia => weekMedia.isNotEmpty;
}
