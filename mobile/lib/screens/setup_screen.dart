import 'package:flutter/material.dart';
import 'package:mobile/models/child.dart';
import 'package:mobile/providers/children_provider.dart';
import 'package:mobile/providers/family_provider.dart';
import 'package:mobile/screens/home_screen.dart';
import 'package:mobile/screens/login_screen.dart';
import 'package:provider/provider.dart';

class SetupScreen extends StatefulWidget {
  const SetupScreen({super.key});

  @override
  State<SetupScreen> createState() => _SetupScreenState();
}

class _SetupScreenState extends State<SetupScreen> {
  int _currentStep = 0;
  bool _isLoading = false;
  final _familyNameController = TextEditingController();
  final _childNameController = TextEditingController();
  final _childNicknameController = TextEditingController();
  DateTime _birthDate = DateTime.now().subtract(const Duration(days: 365 * 3));
  Gender _gender = Gender.male;

  @override
  void dispose() {
    _familyNameController.dispose();
    _childNameController.dispose();
    _childNicknameController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Stack(
      children: [
        Scaffold(
          appBar: AppBar(
            title: const Text('初期設定'),
            automaticallyImplyLeading: false,
            leading: TextButton(
              child: const Text('戻る'),
              onPressed: () {
                Navigator.of(context).pushReplacement(
                  MaterialPageRoute<void>(
                    builder: (context) => const LoginScreen(),
                  ),
                );
              },
            ),
          ),
          body: Stepper(
            currentStep: _currentStep,
            onStepContinue: _isLoading ? null : _onStepContinue,
            onStepCancel: _isLoading
                ? null
                : (_currentStep > 0 ? _onStepCancel : null),
            controlsBuilder: (context, details) {
              return Row(
                children: [
                  ElevatedButton(
                    onPressed: _isLoading ? null : details.onStepContinue,
                    child: Text(_currentStep < 1 ? '次へ' : '完了'),
                  ),
                  const SizedBox(width: 8),
                  if (_currentStep > 0)
                    TextButton(
                      onPressed: _isLoading ? null : details.onStepCancel,
                      child: const Text('戻る'),
                    ),
                ],
              );
            },
            steps: [
              Step(
                title: const Text('ファミリー設定'),
                content: Column(
                  children: [
                    const Text(
                      'まずはファミリー名を設定してください',
                      style: TextStyle(fontSize: 16),
                    ),
                    const SizedBox(height: 16),
                    TextField(
                      controller: _familyNameController,
                      enabled: !_isLoading,
                      decoration: const InputDecoration(
                        labelText: 'ファミリー名',
                        hintText: '例: 田中家',
                        border: OutlineInputBorder(),
                      ),
                    ),
                  ],
                ),
                isActive: _currentStep >= 0,
              ),
              Step(
                title: const Text('お子様情報'),
                content: Column(
                  children: [
                    const Text(
                      'お子様の情報を入力してください',
                      style: TextStyle(fontSize: 16),
                    ),
                    const SizedBox(height: 16),
                    TextField(
                      controller: _childNameController,
                      enabled: !_isLoading,
                      decoration: const InputDecoration(
                        labelText: 'お名前',
                        border: OutlineInputBorder(),
                      ),
                    ),
                    const SizedBox(height: 16),
                    TextField(
                      controller: _childNicknameController,
                      enabled: !_isLoading,
                      decoration: const InputDecoration(
                        labelText: 'ニックネーム（任意）',
                        border: OutlineInputBorder(),
                      ),
                    ),
                    const SizedBox(height: 16),
                    ListTile(
                      title: const Text('生年月日'),
                      subtitle: Text(_formatDate(_birthDate)),
                      trailing: const Icon(Icons.calendar_today),
                      onTap: _isLoading ? null : _selectBirthDate,
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(8),
                        side: BorderSide(color: Colors.grey.shade400),
                      ),
                    ),
                    const SizedBox(height: 16),
                    const Text('性別'),
                    Row(
                      children: [
                        Expanded(
                          child: RadioListTile<Gender>(
                            title: const Text('男の子'),
                            value: Gender.male,
                            groupValue: _gender,
                            onChanged: _isLoading
                                ? null
                                : (value) {
                                    setState(() {
                                      _gender = value!;
                                    });
                                  },
                          ),
                        ),
                        Expanded(
                          child: RadioListTile<Gender>(
                            title: const Text('女の子'),
                            value: Gender.female,
                            groupValue: _gender,
                            onChanged: _isLoading
                                ? null
                                : (value) {
                                    setState(() {
                                      _gender = value!;
                                    });
                                  },
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
                isActive: _currentStep >= 1,
              ),
            ],
          ),
        ),
        if (_isLoading)
          Positioned.fill(
            child: ColoredBox(
              color: Colors.black.withOpacity(0.7),
              child: Center(
                child: Container(
                  padding: const EdgeInsets.all(24),
                  decoration: BoxDecoration(
                    color: Colors.white,
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: const Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      CircularProgressIndicator(),
                      SizedBox(height: 16),
                      Text(
                        '処理中...',
                        style: TextStyle(
                          fontSize: 16,
                          fontWeight: FontWeight.w500,
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ),
      ],
    );
  }

  Future<void> _onStepContinue() async {
    if (!mounted) return;

    if (_currentStep == 0) {
      // Validate family name
      if (_familyNameController.text.trim().isEmpty) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('ファミリー名を入力してください')),
        );
        return;
      }

      setState(() {
        _isLoading = true;
      });
      debugPrint('SetupScreen: Loading started for family creation');

      try {
        // Create family
        final familyProvider = context.read<FamilyProvider>();

        // 最小表示時間を確保するために並列で実行
        final results = await Future.wait([
          familyProvider.createFamily(_familyNameController.text.trim()),
          Future.delayed(const Duration(milliseconds: 500)), // 最小0.5秒表示
        ]);

        final success = results[0] as bool;

        if (!mounted) return;

        if (success) {
          setState(() {
            _currentStep++;
            _isLoading = false;
          });
        } else {
          setState(() {
            _isLoading = false;
          });
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(
              content: Text('ファミリーの作成に失敗しました'),
            ),
          );
        }
      } catch (e, stackTrace) {
        debugPrint('=== Family Creation Error ===');
        debugPrint('Error: $e');
        debugPrint('Stack trace:\n$stackTrace');
        debugPrint('=========================');
        
        if (!mounted) return;
        setState(() {
          _isLoading = false;
        });
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('エラーが発生しました')),
        );
      }
    } else if (_currentStep == 1) {
      // Validate child name
      if (_childNameController.text.trim().isEmpty) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('お子様の名前を入力してください')),
        );
        return;
      }

      setState(() {
        _isLoading = true;
      });

      try {
        // Create child
        final childrenProvider = context.read<ChildrenProvider>();
        final success = await childrenProvider.createChild(
          name: _childNameController.text.trim(),
          birthDate: _birthDate,
          gender: _gender,
          nickname: _childNicknameController.text.trim().isEmpty
              ? null
              : _childNicknameController.text.trim(),
        );

        if (!mounted) return;

        if (success) {
          await Navigator.of(context).pushReplacement(
            MaterialPageRoute<void>(builder: (context) => const HomeScreen()),
          );
        } else {
          setState(() {
            _isLoading = false;
          });
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(
              content: Text('お子様情報の登録に失敗しました'),
            ),
          );
        }
      } catch (e, stackTrace) {
        debugPrint('=== Child Creation Error ===');
        debugPrint('Error: $e');
        debugPrint('Stack trace:\n$stackTrace');
        debugPrint('=========================');
        
        if (!mounted) return;
        setState(() {
          _isLoading = false;
        });
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('エラーが発生しました')),
        );
      }
    }
  }

  void _onStepCancel() {
    if (!mounted) return;
    setState(() {
      _currentStep--;
    });
  }

  Future<void> _selectBirthDate() async {
    final picked = await showDatePicker(
      context: context,
      initialDate: _birthDate,
      firstDate: DateTime(2000),
      lastDate: DateTime.now(),
    );
    if (picked != null && mounted) {
      setState(() {
        _birthDate = picked;
      });
    }
  }

  String _formatDate(DateTime date) {
    return '${date.year}年${date.month}月${date.day}日';
  }
}
