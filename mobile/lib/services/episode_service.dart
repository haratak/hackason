import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:firebase_auth/firebase_auth.dart';
import 'package:flutter/foundation.dart';
import 'package:mobile/models/episode.dart';

class EpisodeService {
  final FirebaseFirestore _firestore = FirebaseFirestore.instance;
  final FirebaseAuth _auth = FirebaseAuth.instance;

  CollectionReference get _episodesCollection =>
      _firestore.collection('episodes');

  Future<List<Episode>> getUserEpisodes() async {
    try {
      final user = _auth.currentUser;
      debugPrint('EpisodeService.getUserEpisodes: user = ${user?.uid}');
      if (user == null) return [];

      final querySnapshot = await _episodesCollection
          .where('user_id', isEqualTo: user.uid)
          .orderBy('created_at', descending: true)
          .get();

      return querySnapshot.docs
          .map(
            (doc) =>
                Episode.fromJson(doc.data()! as Map<String, dynamic>, doc.id),
          )
          .toList();
    } catch (e) {
      // Try with camelCase field names
      try {
        final user = _auth.currentUser;
        if (user == null) return [];

        final querySnapshot = await _episodesCollection
            .where('userId', isEqualTo: user.uid)
            .orderBy('createdAt', descending: true)
            .get();

        return querySnapshot.docs
            .map(
              (doc) =>
                  Episode.fromJson(doc.data()! as Map<String, dynamic>, doc.id),
            )
            .toList();
      } catch (e) {
        debugPrint('Error getting user episodes: $e');
        return [];
      }
    }
  }

  Future<List<Episode>> getChildEpisodes(String childId) async {
    try {
      final querySnapshot = await _episodesCollection
          .where('child_id', isEqualTo: childId)
          .orderBy('created_at', descending: true)
          .get();

      return querySnapshot.docs
          .map(
            (doc) =>
                Episode.fromJson(doc.data()! as Map<String, dynamic>, doc.id),
          )
          .toList();
    } catch (e) {
      // Try with camelCase field names
      try {
        final querySnapshot = await _episodesCollection
            .where('childId', isEqualTo: childId)
            .orderBy('createdAt', descending: true)
            .get();

        return querySnapshot.docs
            .map(
              (doc) =>
                  Episode.fromJson(doc.data()! as Map<String, dynamic>, doc.id),
            )
            .toList();
      } catch (e) {
        debugPrint('Error getting child episodes: $e');
        return [];
      }
    }
  }

  Future<List<Episode>> getFamilyChildrenEpisodes(List<String> childIds) async {
    if (childIds.isEmpty) return [];

    debugPrint('EpisodeService: Getting episodes for childIds: $childIds');

    // Firestore whereIn limit is 10
    if (childIds.length > 10) {
      debugPrint('Warning: Too many children (${childIds.length}), limiting to 10');
      childIds = childIds.take(10).toList();
    }

    try {
      debugPrint('EpisodeService: Querying with child_id (snake_case)...');
      final querySnapshot = await _episodesCollection
          .where('child_id', whereIn: childIds)
          .orderBy('created_at', descending: true)
          .get();

      debugPrint('EpisodeService: Found ${querySnapshot.docs.length} episodes with snake_case');

      return querySnapshot.docs
          .map(
            (doc) =>
                Episode.fromJson(doc.data()! as Map<String, dynamic>, doc.id),
          )
          .toList();
    } catch (e) {
      debugPrint('Error with snake_case fields: $e');
      
      // Try with camelCase field names
      try {
        debugPrint('EpisodeService: Trying with childId (camelCase)...');
        final querySnapshot = await _episodesCollection
            .where('childId', whereIn: childIds)
            .orderBy('createdAt', descending: true)
            .get();

        debugPrint('EpisodeService: Found ${querySnapshot.docs.length} episodes with camelCase');

        return querySnapshot.docs
            .map(
              (doc) =>
                  Episode.fromJson(doc.data()! as Map<String, dynamic>, doc.id),
            )
            .toList();
      } catch (e2) {
        debugPrint('Error getting family children episodes: $e2');
        debugPrint('Stack trace: ${StackTrace.current}');
        return [];
      }
    }
  }

  Stream<List<Episode>> watchUserEpisodes() {
    final user = _auth.currentUser;
    if (user == null) return Stream.value([]);

    return _episodesCollection
        .where('user_id', isEqualTo: user.uid)
        .orderBy('created_at', descending: true)
        .snapshots()
        .handleError((error) {
          // Try with camelCase field names
          return _episodesCollection
              .where('userId', isEqualTo: user.uid)
              .orderBy('createdAt', descending: true)
              .snapshots();
        })
        .map(
          (snapshot) => snapshot.docs
              .map(
                (doc) => Episode.fromJson(
                  doc.data()! as Map<String, dynamic>,
                  doc.id,
                ),
              )
              .toList(),
        );
  }

  Stream<List<Episode>> watchChildEpisodes(String childId) {
    return _episodesCollection
        .where('child_id', isEqualTo: childId)
        .orderBy('created_at', descending: true)
        .snapshots()
        .handleError((error) {
          // Try with camelCase field names
          return _episodesCollection
              .where('childId', isEqualTo: childId)
              .orderBy('createdAt', descending: true)
              .snapshots();
        })
        .map(
          (snapshot) => snapshot.docs
              .map(
                (doc) => Episode.fromJson(
                  doc.data()! as Map<String, dynamic>,
                  doc.id,
                ),
              )
              .toList(),
        );
  }

  Stream<List<Episode>> watchFamilyChildrenEpisodes(List<String> childIds) {
    if (childIds.isEmpty) return Stream.value([]);

    // Firestore whereIn limit is 10
    if (childIds.length > 10) {
      childIds = childIds.take(10).toList();
    }

    return _episodesCollection
        .where('child_id', whereIn: childIds)
        .orderBy('created_at', descending: true)
        .snapshots()
        .handleError((error) {
          // Try with camelCase field names
          return _episodesCollection
              .where('childId', whereIn: childIds)
              .orderBy('createdAt', descending: true)
              .snapshots();
        })
        .map(
          (snapshot) => snapshot.docs
              .map(
                (doc) => Episode.fromJson(
                  doc.data()! as Map<String, dynamic>,
                  doc.id,
                ),
              )
              .toList(),
        );
  }

  Future<Episode?> getEpisode(String episodeId) async {
    try {
      final doc = await _episodesCollection.doc(episodeId).get();
      if (!doc.exists) return null;
      return Episode.fromJson(doc.data()! as Map<String, dynamic>, doc.id);
    } catch (e) {
      debugPrint('Error getting episode: $e');
      return null;
    }
  }
}
