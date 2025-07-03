import 'package:cloud_firestore/cloud_firestore.dart';

class Notebook {
  final String id;
  final String nickname;
  final DateTime date;
  final NotebookPeriod period;
  final List<NotebookTopic> topics;
  final DateTime createdAt;
  final NotebookStatus status;
  final NotebookGenerationStatus generationStatus;
  final List<String> missingTopics;

  Notebook({
    required this.id,
    required this.nickname,
    required this.date,
    required this.period,
    required this.topics,
    required this.createdAt,
    required this.status,
    required this.generationStatus,
    required this.missingTopics,
  });

  static DateTime _parseDate(dynamic value) {
    if (value == null) return DateTime.now();
    if (value is Timestamp) return value.toDate();
    if (value is String) return DateTime.parse(value);
    if (value is DateTime) return value;
    return DateTime.now();
  }

  factory Notebook.fromJson(Map<String, dynamic> json, String id) {
    return Notebook(
      id: id,
      nickname: json['nickname'] as String? ?? '',
      date: _parseDate(json['date']),
      period: NotebookPeriod.fromJson(
        json['period'] as Map<String, dynamic>? ?? {},
      ),
      topics:
          (json['topics'] as List<dynamic>?)
              ?.map(
                (topic) =>
                    NotebookTopic.fromJson(topic as Map<String, dynamic>),
              )
              .toList() ??
          [],
      createdAt: _parseDate(json['createdAt']),
      status: _parseStatus(json['status'] as String?),
      generationStatus: _parseGenerationStatus(
        json['generation_status'] as String?,
      ),
      missingTopics:
          (json['missing_topics'] as List<dynamic>?)?.cast<String>() ?? [],
    );
  }

  static NotebookStatus _parseStatus(String? status) {
    switch (status) {
      case 'published':
        return NotebookStatus.published;
      case 'draft':
        return NotebookStatus.draft;
      default:
        return NotebookStatus.draft;
    }
  }

  static NotebookGenerationStatus _parseGenerationStatus(String? status) {
    switch (status) {
      case 'success':
        return NotebookGenerationStatus.success;
      case 'partial_success':
        return NotebookGenerationStatus.partialSuccess;
      case 'failed':
        return NotebookGenerationStatus.failed;
      default:
        return NotebookGenerationStatus.success;
    }
  }

  Map<String, dynamic> toJson() {
    return {
      'nickname': nickname,
      'date': Timestamp.fromDate(date),
      'period': period.toJson(),
      'topics': topics.map((topic) => topic.toJson()).toList(),
      'createdAt': Timestamp.fromDate(createdAt),
      'status': status.toString().split('.').last,
      'generation_status': generationStatus.toString().split('.').last,
      'missing_topics': missingTopics,
    };
  }
}

class NotebookPeriod {
  final DateTime start;
  final DateTime end;
  final int days;

  NotebookPeriod({
    required this.start,
    required this.end,
    required this.days,
  });

  factory NotebookPeriod.fromJson(Map<String, dynamic> json) {
    // startとendはTimestampまたはISO文字列の可能性がある
    DateTime parseDate(dynamic value) {
      if (value == null) return DateTime.now();
      if (value is Timestamp) return value.toDate();
      if (value is String) return DateTime.parse(value);
      return DateTime.now();
    }

    return NotebookPeriod(
      start: parseDate(json['start']),
      end: parseDate(json['end']),
      days: json['days'] as int? ?? 7,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'start': Timestamp.fromDate(start),
      'end': Timestamp.fromDate(end),
      'days': days,
    };
  }
}

class NotebookTopic {
  final String title;
  final String? subtitle;
  final String content;
  final String? photo;
  final String? caption;

  NotebookTopic({
    required this.title,
    required this.content,
    this.subtitle,
    this.photo,
    this.caption,
  });

  factory NotebookTopic.fromJson(Map<String, dynamic> json) {
    return NotebookTopic(
      title: json['title'] as String? ?? '',
      subtitle: json['subtitle'] as String?,
      content: json['content'] as String? ?? '',
      photo: json['photo'] as String?,
      caption: json['caption'] as String?,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'title': title,
      if (subtitle != null) 'subtitle': subtitle,
      'content': content,
      if (photo != null) 'photo': photo,
      if (caption != null) 'caption': caption,
    };
  }
}

enum NotebookStatus {
  draft,
  published,
}

enum NotebookGenerationStatus {
  success,
  partialSuccess,
  failed,
}

class NotebookGenerationRequest {
  final String childId;
  final String startDate;
  final String endDate;
  final Map<String, dynamic>? childInfo;

  NotebookGenerationRequest({
    required this.childId,
    required this.startDate,
    required this.endDate,
    this.childInfo,
  });

  Map<String, dynamic> toJson() {
    return {
      'child_id': childId,
      'start_date': startDate,
      'end_date': endDate,
      if (childInfo != null) 'child_info': childInfo,
    };
  }
}

class NotebookGenerationResponse {
  final String status;
  final String? notebookId;
  final String? url;
  final int? validTopics;
  final List<String>? missingTopics;
  final String message;
  final String? error;

  NotebookGenerationResponse({
    required this.status,
    required this.message,
    this.notebookId,
    this.url,
    this.validTopics,
    this.missingTopics,
    this.error,
  });

  factory NotebookGenerationResponse.fromJson(Map<String, dynamic> json) {
    return NotebookGenerationResponse(
      status: json['status'] as String,
      notebookId: json['notebook_id'] as String?,
      url: json['url'] as String?,
      validTopics: json['valid_topics'] as int?,
      missingTopics: (json['missing_topics'] as List<dynamic>?)?.cast<String>(),
      message: json['message'] as String? ?? '',
      error: json['error'] as String?,
    );
  }

  bool get isSuccess => status == 'success' || status == 'partial_success';
  bool get isError => status == 'error';
}
