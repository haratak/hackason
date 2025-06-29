import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:firebase_auth/firebase_auth.dart';
import 'package:firebase_core/firebase_core.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:google_sign_in/google_sign_in.dart';

class AuthProvider extends ChangeNotifier {
  final FirebaseAuth _auth = FirebaseAuth.instance;
  final GoogleSignIn _googleSignIn = GoogleSignIn.instance;
  final FirebaseFirestore _firestore = FirebaseFirestore.instanceFor(
    app: Firebase.app(),
  );

  User? _user;
  bool _isLoading = false;

  User? get user => _user;
  bool get isLoading => _isLoading;
  bool get isAuthenticated => _user != null;

  AuthProvider() {
    _initializeAuth();
  }

  Future<void> _initializeAuth() async {
    try {
      debugPrint('AuthProvider: Initializing auth...');
      
      // Firebase Auth state changes listener
      _auth.authStateChanges().listen((User? user) {
        debugPrint('AuthProvider: Auth state changed - user: ${user?.uid}');
        _user = user;
        notifyListeners();
      });

      // GoogleSignIn doesn't need explicit initialization in standard flow

      // Don't attempt lightweight authentication in constructor
      // It can cause issues and should be done explicitly
    } catch (e, stackTrace) {
      debugPrint('=== Auth Initialization Error ===');
      debugPrint('Error: $e');
      debugPrint('Stack trace:\n$stackTrace');
      debugPrint('==============================');
      // Don't rethrow - allow app to continue
    }
  }

  Future<void> signInWithGoogle() async {
    debugPrint('AuthProvider: Starting Google Sign-In');
    try {
      _isLoading = true;
      notifyListeners();

      // Try different approaches based on platform capabilities
      debugPrint('AuthProvider: Checking authentication support...');
      
      // Use authenticate method if supported
      if (_googleSignIn.supportsAuthenticate()) {
        debugPrint('AuthProvider: Using authenticate() method');
        
        final googleUser = await _googleSignIn.authenticate();
        debugPrint('AuthProvider: Google user authenticated: ${googleUser.email}');
        
        // Get authentication details
        final googleAuth = googleUser.authentication;
        
        // Create credential with just ID token
        debugPrint('AuthProvider: Creating Firebase credential with ID token only');
        final credential = GoogleAuthProvider.credential(
          idToken: googleAuth.idToken,
        );
        
        // Sign in to Firebase
        await _signInWithCredential(credential);
      } else {
        debugPrint('AuthProvider: Platform does not support authenticate()');
        throw Exception('Google Sign-In not supported on this platform');
      }

      debugPrint('AuthProvider: Sign-in complete. isAuthenticated: $isAuthenticated');
      _isLoading = false;
      notifyListeners();
    } catch (e, stackTrace) {
      _isLoading = false;
      notifyListeners();
      debugPrint('=== Google Sign-In Error ===');
      debugPrint('Error type: ${e.runtimeType}');
      debugPrint('Error message: $e');
      debugPrint('Stack trace:\n$stackTrace');
      debugPrint('========================');
      rethrow;
    }
  }

  Future<void> _signInWithCredential(OAuthCredential credential) async {
    debugPrint('AuthProvider: Signing in to Firebase...');
    final userCredential = await _auth.signInWithCredential(credential);
    debugPrint('AuthProvider: Firebase sign-in successful. User: ${userCredential.user?.uid}');

    // Create or update user document
    if (userCredential.user != null) {
      debugPrint('AuthProvider: Creating/updating user document');
      await _createOrUpdateUserDocument(userCredential.user!);
    }
  }

  Future<void> signOut() async {
    try {
      _isLoading = true;
      notifyListeners();

      await _googleSignIn.signOut();
      await _auth.signOut();

      _isLoading = false;
      notifyListeners();
    } catch (e, stackTrace) {
      _isLoading = false;
      notifyListeners();
      debugPrint('=== Sign Out Error ===');
      debugPrint('Error: $e');
      debugPrint('Stack trace:\n$stackTrace');
      debugPrint('===================');
      rethrow;
    }
  }

  Future<void> _createOrUpdateUserDocument(User user) async {
    try {
      debugPrint('Creating/updating user document for: ${user.uid}');
      await _firestore.collection('users').doc(user.uid).set({
        'uid': user.uid,
        'email': user.email,
        'displayName': user.displayName,
        'photoURL': user.photoURL,
        'createdAt': FieldValue.serverTimestamp(),
        'lastLoginAt': FieldValue.serverTimestamp(),
      }, SetOptions(merge: true));
      debugPrint('User document created/updated successfully');
    } catch (e, stackTrace) {
      debugPrint('=== User Document Error ===');
      debugPrint('Error creating/updating user document: $e');
      debugPrint('Stack trace:\n$stackTrace');
      debugPrint('========================');
      rethrow; // エラーを再スローして上位で処理
    }
  }
}
