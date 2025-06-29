import 'package:cloud_firestore/cloud_firestore.dart';

class Family {
  final String id;
  final String name;
  final List<String> members;
  final String createdBy;
  final DateTime createdAt;
  final DateTime updatedAt;

  Family({
    required this.id,
    required this.name,
    required this.members,
    required this.createdBy,
    required this.createdAt,
    required this.updatedAt,
  });

  factory Family.fromFirestore(DocumentSnapshot doc) {
    final data = doc.data()! as Map<String, dynamic>;
    return Family(
      id: doc.id,
      name: data['name'] as String? ?? '',
      members: List<String>.from(data['members'] as List<dynamic>? ?? []),
      createdBy: data['createdBy'] as String? ?? '',
      createdAt: (data['createdAt'] as Timestamp).toDate(),
      updatedAt: (data['updatedAt'] as Timestamp).toDate(),
    );
  }

  Map<String, dynamic> toFirestore() {
    return {
      'name': name,
      'members': members,
      'createdBy': createdBy,
      'createdAt': Timestamp.fromDate(createdAt),
      'updatedAt': Timestamp.fromDate(updatedAt),
    };
  }

  Family copyWith({
    String? id,
    String? name,
    List<String>? members,
    String? createdBy,
    DateTime? createdAt,
    DateTime? updatedAt,
  }) {
    return Family(
      id: id ?? this.id,
      name: name ?? this.name,
      members: members ?? this.members,
      createdBy: createdBy ?? this.createdBy,
      createdAt: createdAt ?? this.createdAt,
      updatedAt: updatedAt ?? this.updatedAt,
    );
  }
}
