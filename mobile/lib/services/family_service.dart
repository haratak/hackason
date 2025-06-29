import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:firebase_auth/firebase_auth.dart';
import 'package:flutter/foundation.dart';
import 'package:mobile/models/family.dart';

class FamilyService {
  final FirebaseFirestore _firestore = FirebaseFirestore.instance;
  final FirebaseAuth _auth = FirebaseAuth.instance;

  CollectionReference get _familiesCollection =>
      _firestore.collection('families');

  Future<Family?> createFamily(String name) async {
    try {
      final user = _auth.currentUser;
      if (user == null) throw Exception('User not authenticated');

      final now = DateTime.now();
      final familyData = {
        'name': name,
        'members': [user.uid],
        'createdBy': user.uid,
        'createdAt': Timestamp.fromDate(now),
        'updatedAt': Timestamp.fromDate(now),
      };

      final docRef = await _familiesCollection.add(familyData);

      // Update or create user document with familyId
      await _firestore.collection('users').doc(user.uid).set({
        'familyId': docRef.id,
        'uid': user.uid,
        'email': user.email,
        'updatedAt': Timestamp.fromDate(now),
      }, SetOptions(merge: true));

      final doc = await docRef.get();
      return Family.fromFirestore(doc);
    } on Exception catch (e) {
      debugPrint('Error creating family: $e');
      return null;
    }
  }

  Future<Family?> getFamily(String familyId) async {
    try {
      final doc = await _familiesCollection.doc(familyId).get();
      if (!doc.exists) return null;
      return Family.fromFirestore(doc);
    } on Exception catch (e) {
      debugPrint('Error getting family: $e');
      return null;
    }
  }

  Future<Family?> getUserFamily() async {
    try {
      final user = _auth.currentUser;
      debugPrint('getUserFamily: user = ${user?.uid}');
      if (user == null) return null;

      debugPrint('getUserFamily: Fetching user document...');
      final userDoc = await _firestore.collection('users').doc(user.uid).get();
      debugPrint('getUserFamily: User doc exists = ${userDoc.exists}');
      if (!userDoc.exists) return null;

      final familyId = userDoc.data()?['familyId'] as String?;
      debugPrint('getUserFamily: familyId = $familyId');
      if (familyId == null) return null;

      debugPrint('getUserFamily: Fetching family document...');
      return getFamily(familyId);
    } on Exception catch (e, stackTrace) {
      debugPrint('Error getting user family: $e');
      debugPrint('Stack trace: $stackTrace');
      return null;
    }
  }

  Future<bool> updateFamily(String familyId, {String? name}) async {
    try {
      final updates = <String, dynamic>{
        'updatedAt': Timestamp.fromDate(DateTime.now()),
      };

      if (name != null) updates['name'] = name;

      await _familiesCollection.doc(familyId).update(updates);
      return true;
    } on Exception catch (e) {
      debugPrint('Error updating family: $e');
      return false;
    }
  }

  Future<bool> addMember(String familyId, String userId) async {
    try {
      await _familiesCollection.doc(familyId).update({
        'members': FieldValue.arrayUnion([userId]),
        'updatedAt': Timestamp.fromDate(DateTime.now()),
      });

      // Update or create user document with familyId
      await _firestore.collection('users').doc(userId).set({
        'familyId': familyId,
        'uid': userId,
        'updatedAt': Timestamp.fromDate(DateTime.now()),
      }, SetOptions(merge: true));

      return true;
    } on Exception catch (e) {
      debugPrint('Error adding member: $e');
      return false;
    }
  }

  Future<bool> removeMember(String familyId, String userId) async {
    try {
      final family = await getFamily(familyId);
      if (family == null) return false;

      // Don't allow removing the creator
      if (family.createdBy == userId) {
        debugPrint('Cannot remove family creator');
        return false;
      }

      await _familiesCollection.doc(familyId).update({
        'members': FieldValue.arrayRemove([userId]),
        'updatedAt': Timestamp.fromDate(DateTime.now()),
      });

      // Remove familyId from user document
      await _firestore.collection('users').doc(userId).update({
        'familyId': FieldValue.delete(),
      });

      return true;
    } on Exception catch (e) {
      debugPrint('Error removing member: $e');
      return false;
    }
  }

  Future<bool> deleteFamily(String familyId) async {
    try {
      final family = await getFamily(familyId);
      if (family == null) return false;

      final user = _auth.currentUser;
      if (user == null || family.createdBy != user.uid) {
        debugPrint('Only family creator can delete the family');
        return false;
      }

      // Remove familyId from all member documents
      final batch = _firestore.batch();
      for (final memberId in family.members) {
        // Use set with merge to handle non-existent documents
        batch.set(_firestore.collection('users').doc(memberId), {
          'familyId': FieldValue.delete(),
          'updatedAt': Timestamp.fromDate(DateTime.now()),
        }, SetOptions(merge: true));
      }

      // Delete family document
      batch.delete(_familiesCollection.doc(familyId));

      await batch.commit();
      return true;
    } on Exception catch (e) {
      debugPrint('Error deleting family: $e');
      return false;
    }
  }

  Stream<Family?> watchFamily(String familyId) {
    return _familiesCollection.doc(familyId).snapshots().map((doc) {
      if (!doc.exists) return null;
      return Family.fromFirestore(doc);
    });
  }

  Stream<Family?> watchUserFamily() {
    final user = _auth.currentUser;
    if (user == null) return Stream.value(null);

    return _firestore.collection('users').doc(user.uid).snapshots().asyncMap((
      userDoc,
    ) async {
      if (!userDoc.exists) return null;

      final familyId = userDoc.data()?['familyId'] as String?;
      if (familyId == null) return null;

      final familyDoc = await _familiesCollection.doc(familyId).get();
      if (!familyDoc.exists) return null;

      return Family.fromFirestore(familyDoc);
    });
  }
}
