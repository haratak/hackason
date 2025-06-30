import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:firebase_auth/firebase_auth.dart';
import 'package:flutter/foundation.dart';
import 'package:mobile/models/analysis_result.dart';

class AnalysisResultService {
  final FirebaseFirestore _firestore = FirebaseFirestore.instance;
  final FirebaseAuth _auth = FirebaseAuth.instance;

  CollectionReference get _analysisResultsCollection =>
      _firestore.collection('analysis_results');

  Future<List<AnalysisResult>> getUserAnalysisResults() async {
    try {
      final user = _auth.currentUser;
      debugPrint('AnalysisResultService.getUserAnalysisResults: user = ${user?.uid}');
      if (user == null) return [];

      final querySnapshot = await _analysisResultsCollection
          .where('user_id', isEqualTo: user.uid)
          .orderBy('created_at', descending: true)
          .get();

      return querySnapshot.docs
          .map(
            (doc) =>
                AnalysisResult.fromJson(doc.data()! as Map<String, dynamic>, doc.id),
          )
          .toList();
    } catch (e) {
      debugPrint('Error getting user analysis results: $e');
      return [];
    }
  }

  Future<List<AnalysisResult>> getChildAnalysisResults(String childId) async {
    try {
      final querySnapshot = await _analysisResultsCollection
          .where('child_id', isEqualTo: childId)
          .orderBy('created_at', descending: true)
          .get();

      return querySnapshot.docs
          .map(
            (doc) =>
                AnalysisResult.fromJson(doc.data()! as Map<String, dynamic>, doc.id),
          )
          .toList();
    } catch (e) {
      debugPrint('Error getting child analysis results: $e');
      return [];
    }
  }

  Future<List<AnalysisResult>> getFamilyChildrenAnalysisResults(List<String> childIds) async {
    if (childIds.isEmpty) return [];

    debugPrint('AnalysisResultService: Getting analysis results for childIds: $childIds');

    // Firestore whereIn limit is 10
    if (childIds.length > 10) {
      debugPrint('Warning: Too many children (${childIds.length}), limiting to 10');
      childIds = childIds.take(10).toList();
    }

    try {
      debugPrint('AnalysisResultService: Querying with child_id...');
      final querySnapshot = await _analysisResultsCollection
          .where('child_id', whereIn: childIds)
          .orderBy('created_at', descending: true)
          .get();

      debugPrint('AnalysisResultService: Found ${querySnapshot.docs.length} analysis results');

      return querySnapshot.docs
          .map(
            (doc) =>
                AnalysisResult.fromJson(doc.data()! as Map<String, dynamic>, doc.id),
          )
          .toList();
    } catch (e) {
      debugPrint('Error getting family children analysis results: $e');
      debugPrint('Stack trace: ${StackTrace.current}');
      return [];
    }
  }

  Stream<List<AnalysisResult>> watchUserAnalysisResults() {
    final user = _auth.currentUser;
    if (user == null) return Stream.value([]);

    return _analysisResultsCollection
        .where('user_id', isEqualTo: user.uid)
        .orderBy('created_at', descending: true)
        .snapshots()
        .map(
          (snapshot) => snapshot.docs
              .map(
                (doc) => AnalysisResult.fromJson(
                  doc.data()! as Map<String, dynamic>,
                  doc.id,
                ),
              )
              .toList(),
        );
  }

  Stream<List<AnalysisResult>> watchChildAnalysisResults(String childId) {
    return _analysisResultsCollection
        .where('child_id', isEqualTo: childId)
        .orderBy('created_at', descending: true)
        .snapshots()
        .map(
          (snapshot) => snapshot.docs
              .map(
                (doc) => AnalysisResult.fromJson(
                  doc.data()! as Map<String, dynamic>,
                  doc.id,
                ),
              )
              .toList(),
        );
  }

  Stream<List<AnalysisResult>> watchFamilyChildrenAnalysisResults(List<String> childIds) {
    if (childIds.isEmpty) return Stream.value([]);

    // Firestore whereIn limit is 10
    if (childIds.length > 10) {
      childIds = childIds.take(10).toList();
    }

    return _analysisResultsCollection
        .where('child_id', whereIn: childIds)
        .orderBy('created_at', descending: true)
        .snapshots()
        .map(
          (snapshot) => snapshot.docs
              .map(
                (doc) => AnalysisResult.fromJson(
                  doc.data()! as Map<String, dynamic>,
                  doc.id,
                ),
              )
              .toList(),
        );
  }

  Future<AnalysisResult?> getAnalysisResult(String id) async {
    try {
      final doc = await _analysisResultsCollection.doc(id).get();
      if (!doc.exists) return null;
      return AnalysisResult.fromJson(doc.data()! as Map<String, dynamic>, doc.id);
    } catch (e) {
      debugPrint('Error getting analysis result: $e');
      return null;
    }
  }
}
