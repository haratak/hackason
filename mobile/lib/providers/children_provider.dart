import 'package:flutter/material.dart';
import 'package:mobile/models/child.dart';
import 'package:mobile/services/children_service.dart';

class ChildrenProvider extends ChangeNotifier {
  final ChildrenService _childrenService = ChildrenService();
  
  List<Child> _children = [];
  bool _isLoading = false;
  String? _error;

  List<Child> get children => _children;
  bool get isLoading => _isLoading;
  String? get error => _error;
  bool get hasChildren => _children.isNotEmpty;

  Future<void> loadChildren() async {
    _isLoading = true;
    _error = null;
    notifyListeners();

    try {
      _children = await _childrenService.getFamilyChildren();
    } on Exception catch (e) {
      _error = 'Failed to load children: $e';
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  Future<bool> createChild({
    required String name,
    required DateTime birthDate,
    required Gender gender,
    String? nickname,
    String? relationship,
  }) async {
    _isLoading = true;
    _error = null;
    notifyListeners();

    try {
      final child = await _childrenService.createChild(
        name: name,
        birthDate: birthDate,
        gender: gender,
        nickname: nickname,
        relationship: relationship,
      );
      
      if (child != null) {
        _children
          ..add(child)
          ..sort((a, b) => a.createdAt.compareTo(b.createdAt));
        _isLoading = false;
        notifyListeners();
        return true;
      } else {
        _error = 'Failed to create child';
        _isLoading = false;
        notifyListeners();
        return false;
      }
    } on Exception catch (e) {
      _error = 'Error creating child: $e';
      _isLoading = false;
      notifyListeners();
      return false;
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
    _isLoading = true;
    _error = null;
    notifyListeners();

    try {
      final success = await _childrenService.updateChild(
        childId,
        name: name,
        birthDate: birthDate,
        gender: gender,
        nickname: nickname,
        relationship: relationship,
      );
      
      if (success) {
        final index = _children.indexWhere((c) => c.id == childId);
        if (index != -1) {
          final updated = _children[index].copyWith(
            name: name ?? _children[index].name,
            birthDate: birthDate ?? _children[index].birthDate,
            gender: gender ?? _children[index].gender,
            nickname: nickname ?? _children[index].nickname,
            relationship: relationship ?? _children[index].relationship,
            updatedAt: DateTime.now(),
          );
          _children[index] = updated;
        }
      } else {
        _error = 'Failed to update child';
      }
      
      _isLoading = false;
      notifyListeners();
      return success;
    } on Exception catch (e) {
      _error = 'Error updating child: $e';
      _isLoading = false;
      notifyListeners();
      return false;
    }
  }

  Future<bool> deleteChild(String childId) async {
    _isLoading = true;
    _error = null;
    notifyListeners();

    try {
      final success = await _childrenService.deleteChild(childId);
      
      if (success) {
        _children.removeWhere((c) => c.id == childId);
      } else {
        _error = 'Failed to delete child';
      }
      
      _isLoading = false;
      notifyListeners();
      return success;
    } on Exception catch (e) {
      _error = 'Error deleting child: $e';
      _isLoading = false;
      notifyListeners();
      return false;
    }
  }

  Child? getChildById(String childId) {
    try {
      return _children.firstWhere((c) => c.id == childId);
    } on Exception {
      return null;
    }
  }

  void clearError() {
    _error = null;
    notifyListeners();
  }

  void reset() {
    _children = [];
    _isLoading = false;
    _error = null;
    notifyListeners();
  }
}
