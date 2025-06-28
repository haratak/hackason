import 'package:firebase_auth/firebase_auth.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:google_sign_in/google_sign_in.dart';

class AuthProvider extends ChangeNotifier {
  final FirebaseAuth _auth = FirebaseAuth.instance;
  final GoogleSignIn _googleSignIn = GoogleSignIn.instance;
  bool _isInitialized = false;

  User? _user;
  bool _isLoading = false;

  User? get user => _user;
  bool get isLoading => _isLoading;
  bool get isAuthenticated => _user != null;

  AuthProvider() {
    _initializeAuth();
  }

  Future<void> _initializeAuth() async {
    // Firebase Auth state changes listener
    _auth.authStateChanges().listen((User? user) {
      _user = user;
      notifyListeners();
    });

    // Initialize GoogleSignIn
    await _googleSignIn.initialize();
    _isInitialized = true;

    // Try lightweight authentication
    await _googleSignIn.attemptLightweightAuthentication();
  }

  Future<void> signInWithGoogle() async {
    try {
      _isLoading = true;
      notifyListeners();

      if (!_isInitialized) {
        await _googleSignIn.initialize();
        _isInitialized = true;
      }

      // Check if platform supports authenticate
      if (!_googleSignIn.supportsAuthenticate()) {
        throw Exception('Google Sign-In not supported on this platform');
      }

      // Authenticate the user
      final googleUser = await _googleSignIn.authenticate();

      // Get authentication tokens
      final googleAuth = googleUser.authentication;
      
      // Get access token from authorization client
      final authorization = 
          await googleUser.authorizationClient.authorizationForScopes([]);
      
      // Create Firebase credential
      final credential = GoogleAuthProvider.credential(
        accessToken: authorization?.accessToken,
        idToken: googleAuth.idToken,
      );

      // Sign in to Firebase
      await _auth.signInWithCredential(credential);

      _isLoading = false;
      notifyListeners();
    } on Exception catch (e) {
      _isLoading = false;
      notifyListeners();
      debugPrint('Google Sign-In failed: $e');
      throw Exception('Google Sign-In failed: $e');
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
    } on Exception catch (e) {
      _isLoading = false;
      notifyListeners();
      debugPrint('Sign out failed: $e');
      throw Exception('Sign out failed: $e');
    }
  }
}
