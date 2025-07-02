import 'package:flutter/material.dart';
import 'package:kids_diary/models/family.dart';
import 'package:kids_diary/services/family_service.dart';

class FamilyProvider extends ChangeNotifier {
  final FamilyService _familyService = FamilyService();
  
  Family? _currentFamily;
  bool _isLoading = false;
  String? _error;

  Family? get currentFamily => _currentFamily;
  bool get isLoading => _isLoading;
  String? get error => _error;
  bool get hasFamily => _currentFamily != null;

  Future<void> loadUserFamily() async {
    _isLoading = true;
    _error = null;
    notifyListeners();

    try {
      _currentFamily = await _familyService.getUserFamily();
    } on Exception catch (e) {
      _error = 'Failed to load family: $e';
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  Future<bool> createFamily(String name) async {
    _isLoading = true;
    _error = null;
    notifyListeners();

    try {
      final family = await _familyService.createFamily(name);
      if (family != null) {
        _currentFamily = family;
        _isLoading = false;
        notifyListeners();
        return true;
      } else {
        _error = 'Failed to create family';
        _isLoading = false;
        notifyListeners();
        return false;
      }
    } on Exception catch (e) {
      _error = 'Error creating family: $e';
      _isLoading = false;
      notifyListeners();
      return false;
    }
  }

  Future<bool> updateFamilyName(String name) async {
    if (_currentFamily == null) return false;

    _isLoading = true;
    _error = null;
    notifyListeners();

    try {
      final success = await _familyService.updateFamily(_currentFamily!.id, name: name);
      if (success) {
        _currentFamily = _currentFamily!.copyWith(
          name: name,
          updatedAt: DateTime.now(),
        );
      } else {
        _error = 'Failed to update family name';
      }
      _isLoading = false;
      notifyListeners();
      return success;
    } on Exception catch (e) {
      _error = 'Error updating family: $e';
      _isLoading = false;
      notifyListeners();
      return false;
    }
  }

  Future<bool> addMember(String userId) async {
    if (_currentFamily == null) return false;

    _isLoading = true;
    _error = null;
    notifyListeners();

    try {
      final success = await _familyService.addMember(_currentFamily!.id, userId);
      if (success) {
        final updatedMembers = List<String>.from(_currentFamily!.members)..add(userId);
        _currentFamily = _currentFamily!.copyWith(
          members: updatedMembers,
          updatedAt: DateTime.now(),
        );
      } else {
        _error = 'Failed to add member';
      }
      _isLoading = false;
      notifyListeners();
      return success;
    } on Exception catch (e) {
      _error = 'Error adding member: $e';
      _isLoading = false;
      notifyListeners();
      return false;
    }
  }

  Future<bool> removeMember(String userId) async {
    if (_currentFamily == null) return false;

    _isLoading = true;
    _error = null;
    notifyListeners();

    try {
      final success = await _familyService.removeMember(_currentFamily!.id, userId);
      if (success) {
        final updatedMembers = List<String>.from(_currentFamily!.members)
          ..remove(userId);
        _currentFamily = _currentFamily!.copyWith(
          members: updatedMembers,
          updatedAt: DateTime.now(),
        );
      } else {
        _error = 'Failed to remove member';
      }
      _isLoading = false;
      notifyListeners();
      return success;
    } on Exception catch (e) {
      _error = 'Error removing member: $e';
      _isLoading = false;
      notifyListeners();
      return false;
    }
  }

  Future<bool> deleteFamily() async {
    if (_currentFamily == null) return false;

    _isLoading = true;
    _error = null;
    notifyListeners();

    try {
      final success = await _familyService.deleteFamily(_currentFamily!.id);
      if (success) {
        _currentFamily = null;
      } else {
        _error = 'Failed to delete family';
      }
      _isLoading = false;
      notifyListeners();
      return success;
    } on Exception catch (e) {
      _error = 'Error deleting family: $e';
      _isLoading = false;
      notifyListeners();
      return false;
    }
  }

  void clearError() {
    _error = null;
    notifyListeners();
  }

  void reset() {
    _currentFamily = null;
    _isLoading = false;
    _error = null;
    notifyListeners();
  }
}
