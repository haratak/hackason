import 'package:cloud_firestore/cloud_firestore.dart';

enum MediaType { image, video, unknown }

enum ProcessingStatus { pending, processing, completed, failed }

class MediaUpload {
  final String id;
  final String userId;
  final String childId;
  final String mediaUri;
  final String bucketName;
  final String filePath;
  final MediaType mediaType;
  final ProcessingStatus processingStatus;
  final DateTime createdAt;
  final DateTime uploadedAt;

  // Optional fields
  final String? processingError;
  final DateTime? processedAt;
  final String? episodeId;
  final DateTime? updatedAt;
  final DateTime? capturedAt; // 撮影日時

  MediaUpload({
    required this.id,
    required this.userId,
    required this.childId,
    required this.mediaUri,
    required this.bucketName,
    required this.filePath,
    required this.mediaType,
    required this.processingStatus,
    required this.createdAt,
    required this.uploadedAt,
    this.processingError,
    this.processedAt,
    this.episodeId,
    this.updatedAt,
    this.capturedAt,
  });

  factory MediaUpload.fromJson(Map<String, dynamic> json, String id) {
    return MediaUpload(
      id: id,
      userId: json['user_id'] as String,
      childId: json['child_id'] as String,
      mediaUri: json['media_uri'] as String,
      bucketName: json['bucket_name'] as String,
      filePath: json['file_path'] as String,
      mediaType: _parseMediaType(json['media_type'] as String),
      processingStatus: _parseProcessingStatus(
        json['processing_status'] as String,
      ),
      createdAt: (json['created_at'] as Timestamp).toDate(),
      uploadedAt: (json['uploaded_at'] as Timestamp).toDate(),
      processingError: json['processing_error'] as String?,
      processedAt: json['processed_at'] != null
          ? (json['processed_at'] as Timestamp).toDate()
          : null,
      episodeId: json['episode_id'] as String?,
      updatedAt: json['updated_at'] != null
          ? (json['updated_at'] as Timestamp).toDate()
          : null,
      capturedAt: json['captured_at'] != null
          ? (json['captured_at'] as Timestamp).toDate()
          : null,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'user_id': userId,
      'child_id': childId,
      'media_uri': mediaUri,
      'bucket_name': bucketName,
      'file_path': filePath,
      'media_type': mediaType.toString().split('.').last,
      'processing_status': processingStatus.toString().split('.').last,
      'created_at': FieldValue.serverTimestamp(),
      'uploaded_at': Timestamp.fromDate(uploadedAt),
      if (processingError != null) 'processing_error': processingError,
      if (processedAt != null) 'processed_at': Timestamp.fromDate(processedAt!),
      if (episodeId != null) 'episode_id': episodeId,
      if (updatedAt != null) 'updated_at': Timestamp.fromDate(updatedAt!),
      if (capturedAt != null) 'captured_at': Timestamp.fromDate(capturedAt!),
    };
  }

  static MediaType _parseMediaType(String type) {
    switch (type) {
      case 'image':
        return MediaType.image;
      case 'video':
        return MediaType.video;
      default:
        return MediaType.unknown;
    }
  }

  static ProcessingStatus _parseProcessingStatus(String status) {
    switch (status) {
      case 'pending':
        return ProcessingStatus.pending;
      case 'processing':
        return ProcessingStatus.processing;
      case 'completed':
        return ProcessingStatus.completed;
      case 'failed':
        return ProcessingStatus.failed;
      default:
        return ProcessingStatus.pending;
    }
  }

  MediaUpload copyWith({
    String? id,
    String? userId,
    String? childId,
    String? mediaUri,
    String? bucketName,
    String? filePath,
    MediaType? mediaType,
    ProcessingStatus? processingStatus,
    DateTime? createdAt,
    DateTime? uploadedAt,
    String? processingError,
    DateTime? processedAt,
    String? episodeId,
    DateTime? updatedAt,
    DateTime? capturedAt,
  }) {
    return MediaUpload(
      id: id ?? this.id,
      userId: userId ?? this.userId,
      childId: childId ?? this.childId,
      mediaUri: mediaUri ?? this.mediaUri,
      bucketName: bucketName ?? this.bucketName,
      filePath: filePath ?? this.filePath,
      mediaType: mediaType ?? this.mediaType,
      processingStatus: processingStatus ?? this.processingStatus,
      createdAt: createdAt ?? this.createdAt,
      uploadedAt: uploadedAt ?? this.uploadedAt,
      processingError: processingError ?? this.processingError,
      processedAt: processedAt ?? this.processedAt,
      episodeId: episodeId ?? this.episodeId,
      updatedAt: updatedAt ?? this.updatedAt,
      capturedAt: capturedAt ?? this.capturedAt,
    );
  }
}
