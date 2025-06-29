import 'package:cloud_firestore/cloud_firestore.dart';

enum Gender { male, female, other }

class Child {
  final String id;
  final String familyId;
  final String name;
  final DateTime birthDate;
  final Gender gender;
  final String? nickname;
  final String? relationship;
  final DateTime createdAt;
  final DateTime updatedAt;

  Child({
    required this.id,
    required this.familyId,
    required this.name,
    required this.birthDate,
    required this.gender,
    required this.createdAt,
    required this.updatedAt,
    this.nickname,
    this.relationship,
  });

  factory Child.fromFirestore(DocumentSnapshot doc) {
    final data = doc.data()! as Map<String, dynamic>;
    return Child(
      id: doc.id,
      familyId: data['familyId'] as String? ?? '',
      name: data['name'] as String? ?? '',
      birthDate: (data['birthDate'] as Timestamp).toDate(),
      gender: _parseGender(data['gender'] as String?),
      nickname: data['nickname'] as String?,
      relationship: data['relationship'] as String?,
      createdAt: (data['createdAt'] as Timestamp).toDate(),
      updatedAt: (data['updatedAt'] as Timestamp).toDate(),
    );
  }

  Map<String, dynamic> toFirestore() {
    return {
      'familyId': familyId,
      'name': name,
      'birthDate': Timestamp.fromDate(birthDate),
      'gender': gender.name,
      'nickname': nickname,
      'relationship': relationship,
      'createdAt': Timestamp.fromDate(createdAt),
      'updatedAt': Timestamp.fromDate(updatedAt),
    };
  }

  Child copyWith({
    String? id,
    String? familyId,
    String? name,
    DateTime? birthDate,
    Gender? gender,
    String? nickname,
    String? relationship,
    DateTime? createdAt,
    DateTime? updatedAt,
  }) {
    return Child(
      id: id ?? this.id,
      familyId: familyId ?? this.familyId,
      name: name ?? this.name,
      birthDate: birthDate ?? this.birthDate,
      gender: gender ?? this.gender,
      nickname: nickname ?? this.nickname,
      relationship: relationship ?? this.relationship,
      createdAt: createdAt ?? this.createdAt,
      updatedAt: updatedAt ?? this.updatedAt,
    );
  }

  int get age {
    final now = DateTime.now();
    var age = now.year - birthDate.year;
    if (now.month < birthDate.month ||
        (now.month == birthDate.month && now.day < birthDate.day)) {
      age--;
    }
    return age;
  }

  static Gender _parseGender(String? genderStr) {
    switch (genderStr) {
      case 'male':
        return Gender.male;
      case 'female':
        return Gender.female;
      case 'other':
        return Gender.other;
      default:
        return Gender.other;
    }
  }
}
