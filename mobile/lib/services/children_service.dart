import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:flutter/foundation.dart';
import 'package:kids_diary/models/child.dart';
import 'package:kids_diary/services/family_service.dart';

class ChildrenService {
  final FirebaseFirestore _firestore = FirebaseFirestore.instance;
  final FamilyService _familyService = FamilyService();

  CollectionReference get _childrenCollection =>
      _firestore.collection('children');

  Future<Child?> createChild({
    required String name,
    required DateTime birthDate,
    required Gender gender,
    String? nickname,
    String? relationship,
  }) async {
    try {
      // Get user's family
      final family = await _familyService.getUserFamily();
      if (family == null) {
        debugPrint('User does not belong to a family');
        return null;
      }

      final now = DateTime.now();
      final childData = {
        'familyId': family.id,
        'name': name,
        'birthDate': Timestamp.fromDate(birthDate),
        'gender': gender.name,
        'nickname': nickname,
        'relationship': relationship,
        'createdAt': Timestamp.fromDate(now),
        'updatedAt': Timestamp.fromDate(now),
      };

      final docRef = await _childrenCollection.add(childData);
      final doc = await docRef.get();
      return Child.fromFirestore(doc);
    } on Exception catch (e) {
      debugPrint('Error creating child: $e');
      return null;
    }
  }

  Future<List<Child>> getFamilyChildren() async {
    try {
      final family = await _familyService.getUserFamily();
      if (family == null) {
        return [];
      }

      final querySnapshot = await _childrenCollection
          .where('familyId', isEqualTo: family.id)
          .orderBy('createdAt', descending: false)
          .get();

      return querySnapshot.docs.map(Child.fromFirestore).toList();
    } on Exception catch (e) {
      debugPrint('Error getting family children: $e');
      return [];
    }
  }

  Future<Child?> getChild(String childId) async {
    try {
      final doc = await _childrenCollection.doc(childId).get();
      if (!doc.exists) return null;

      final child = Child.fromFirestore(doc);

      // Verify user has access to this child
      final family = await _familyService.getUserFamily();
      if (family == null || child.familyId != family.id) {
        debugPrint('User does not have access to this child');
        return null;
      }

      return child;
    } on Exception catch (e) {
      debugPrint('Error getting child: $e');
      return null;
    }
  }

  Future<bool> updateChild(
    String childId, {
    String? name,
    DateTime? birthDate,
    Gender? gender,
    String? nickname,
    String? relationship,
  }) async {
    try {
      // Verify user has access
      final child = await getChild(childId);
      if (child == null) return false;

      final updates = <String, dynamic>{
        'updatedAt': Timestamp.fromDate(DateTime.now()),
      };

      if (name != null) updates['name'] = name;
      if (birthDate != null)
        updates['birthDate'] = Timestamp.fromDate(birthDate);
      if (gender != null) updates['gender'] = gender.name;
      if (nickname != null) updates['nickname'] = nickname;
      if (relationship != null) updates['relationship'] = relationship;

      await _childrenCollection.doc(childId).update(updates);
      return true;
    } on Exception catch (e) {
      debugPrint('Error updating child: $e');
      return false;
    }
  }

  Future<bool> deleteChild(String childId) async {
    try {
      // Verify user has access
      final child = await getChild(childId);
      if (child == null) return false;

      await _childrenCollection.doc(childId).delete();
      return true;
    } on Exception catch (e) {
      debugPrint('Error deleting child: $e');
      return false;
    }
  }

  Stream<List<Child>> watchFamilyChildren() {
    return _familyService.watchUserFamily().asyncMap((family) async {
      if (family == null) return [];

      final querySnapshot = await _childrenCollection
          .where('familyId', isEqualTo: family.id)
          .orderBy('createdAt', descending: false)
          .get();

      return querySnapshot.docs.map(Child.fromFirestore).toList();
    });
  }

  Stream<Child?> watchChild(String childId) {
    return _childrenCollection.doc(childId).snapshots().asyncMap((doc) async {
      if (!doc.exists) return null;

      final child = Child.fromFirestore(doc);

      // Verify user has access
      final family = await _familyService.getUserFamily();
      if (family == null || child.familyId != family.id) {
        return null;
      }

      return child;
    });
  }
}
