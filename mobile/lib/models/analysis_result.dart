import 'package:cloud_firestore/cloud_firestore.dart';

class AnalysisResult {
  final String id;
  final String mediaUri;
  final String childId;
  final int childAgeMonths;
  final String userId;
  final String emotionalTitle;
  final List<AnalysisEpisode> episodes;
  final int episodeCount;
  final DateTime createdAt;
  final DateTime updatedAt;

  AnalysisResult({
    required this.id,
    required this.mediaUri,
    required this.childId,
    required this.childAgeMonths,
    required this.userId,
    required this.emotionalTitle,
    required this.episodes,
    required this.episodeCount,
    required this.createdAt,
    required this.updatedAt,
  });

  factory AnalysisResult.fromJson(Map<String, dynamic> json, String id) {
    return AnalysisResult(
      id: id,
      mediaUri: json['media_uri'] as String? ?? '',
      childId: json['child_id'] as String? ?? '',
      childAgeMonths: json['child_age_months'] as int? ?? 0,
      userId: json['user_id'] as String? ?? '',
      emotionalTitle: json['emotional_title'] as String? ?? '',
      episodes: (json['episodes'] as List<dynamic>?)
              ?.map((e) => AnalysisEpisode.fromJson(e as Map<String, dynamic>))
              .toList() ??
          [],
      episodeCount: json['episode_count'] as int? ?? 0,
      createdAt: json['created_at'] != null
          ? (json['created_at'] as Timestamp).toDate()
          : DateTime.now(),
      updatedAt: json['updated_at'] != null
          ? (json['updated_at'] as Timestamp).toDate()
          : DateTime.now(),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'media_uri': mediaUri,
      'child_id': childId,
      'child_age_months': childAgeMonths,
      'user_id': userId,
      'emotional_title': emotionalTitle,
      'episodes': episodes.map((e) => e.toJson()).toList(),
      'episode_count': episodeCount,
      'created_at': Timestamp.fromDate(createdAt),
      'updated_at': Timestamp.fromDate(updatedAt),
    };
  }
}

class AnalysisEpisode {
  final String id;
  final String type;
  final String title;
  final String summary;
  final String content;
  final List<String> tags;
  final Map<String, dynamic> metadata;
  final DateTime createdAt;

  AnalysisEpisode({
    required this.id,
    required this.type,
    required this.title,
    required this.summary,
    required this.content,
    required this.tags,
    required this.metadata,
    required this.createdAt,
  });

  factory AnalysisEpisode.fromJson(Map<String, dynamic> json) {
    return AnalysisEpisode(
      id: json['id'] as String? ?? '',
      type: json['type'] as String? ?? '',
      title: json['title'] as String? ?? '',
      summary: json['summary'] as String? ?? '',
      content: json['content'] as String? ?? '',
      tags: (json['tags'] as List<dynamic>?)?.cast<String>() ?? [],
      metadata: json['metadata'] as Map<String, dynamic>? ?? {},
      createdAt: json['created_at'] != null
          ? (json['created_at'] as Timestamp).toDate()
          : DateTime.now(),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'type': type,
      'title': title,
      'summary': summary,
      'content': content,
      'tags': tags,
      'metadata': metadata,
      'created_at': Timestamp.fromDate(createdAt),
    };
  }
}
