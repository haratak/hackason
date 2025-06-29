import 'package:cloud_firestore/cloud_firestore.dart';

class Episode {
  final String id;
  final String userId;
  final String childId;
  final String? title;
  final String? content;
  final List<String> mediaUrls;
  final DateTime createdAt;
  final DateTime? updatedAt;
  final Map<String, dynamic>? metadata;

  Episode({
    required this.id,
    required this.userId,
    required this.childId,
    this.title,
    this.content,
    required this.mediaUrls,
    required this.createdAt,
    this.updatedAt,
    this.metadata,
  });

  factory Episode.fromJson(Map<String, dynamic> json, String id) {
    try {
      return Episode(
        id: id,
        userId: json['user_id'] as String? ?? json['userId'] as String? ?? '',
        childId: json['child_id'] as String? ?? json['childId'] as String? ?? '',
        title: json['title'] as String?,
        content: json['content'] as String?,
        mediaUrls: (json['media_urls'] as List<dynamic>?)?.cast<String>() ?? 
                   (json['mediaUrls'] as List<dynamic>?)?.cast<String>() ?? [],
        createdAt: json['created_at'] != null 
            ? (json['created_at'] as Timestamp).toDate()
            : json['createdAt'] != null 
                ? (json['createdAt'] as Timestamp).toDate()
                : DateTime.now(),
        updatedAt: json['updated_at'] != null 
            ? (json['updated_at'] as Timestamp).toDate()
            : json['updatedAt'] != null 
                ? (json['updatedAt'] as Timestamp).toDate()
                : null,
        metadata: json['metadata'] as Map<String, dynamic>?,
      );
    } catch (e) {
      print('Error parsing Episode from JSON: $e');
      print('JSON data: $json');
      rethrow;
    }
  }

  Map<String, dynamic> toJson() {
    return {
      'user_id': userId,
      'child_id': childId,
      if (title != null) 'title': title,
      if (content != null) 'content': content,
      'media_urls': mediaUrls,
      'created_at': Timestamp.fromDate(createdAt),
      if (updatedAt != null) 'updated_at': Timestamp.fromDate(updatedAt!),
      if (metadata != null) 'metadata': metadata,
    };
  }
}
