import 'package:cloud_firestore/cloud_firestore.dart';

class FileUpload {
  final String id;
  final String bucketUrl;
  final String filePath;
  final DateTime uploadedAt;
  final String userId;
  final String? childId;
  final Map<String, dynamic>? metadata;

  FileUpload({
    required this.id,
    required this.bucketUrl,
    required this.filePath,
    required this.uploadedAt,
    required this.userId,
    this.childId,
    this.metadata,
  });

  factory FileUpload.fromFirestore(DocumentSnapshot doc) {
    final data = doc.data()! as Map<String, dynamic>;
    return FileUpload(
      id: doc.id,
      bucketUrl: data['bucketUrl'] as String? ?? '',
      filePath: data['filePath'] as String? ?? '',
      uploadedAt: (data['uploadedAt'] as Timestamp).toDate(),
      userId: data['userId'] as String? ?? '',
      childId: data['childId'] as String?,
      metadata: data['metadata'] as Map<String, dynamic>?,
    );
  }

  Map<String, dynamic> toFirestore() {
    return {
      'bucketUrl': bucketUrl,
      'filePath': filePath,
      'uploadedAt': Timestamp.fromDate(uploadedAt),
      'userId': userId,
      'childId': childId,
      'metadata': metadata,
    };
  }
}
