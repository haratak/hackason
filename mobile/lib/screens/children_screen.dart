import 'package:flutter/material.dart';
import 'package:kids_diary/models/child.dart';
import 'package:kids_diary/providers/children_provider.dart';
import 'package:kids_diary/providers/family_provider.dart';
import 'package:provider/provider.dart';

class ChildrenScreen extends StatefulWidget {
  const ChildrenScreen({super.key});

  @override
  State<ChildrenScreen> createState() => _ChildrenScreenState();
}

class _ChildrenScreenState extends State<ChildrenScreen> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<ChildrenProvider>().loadChildren();
    });
  }

  @override
  Widget build(BuildContext context) {
    final childrenProvider = context.watch<ChildrenProvider>();
    final familyProvider = context.watch<FamilyProvider>();

    if (!familyProvider.hasFamily) {
      return Scaffold(
        appBar: AppBar(
          title: const Text('子供情報'),
        ),
        body: const Center(
          child: Text('先にファミリーを作成してください'),
        ),
      );
    }

    return Scaffold(
      appBar: AppBar(
        title: const Text('子供情報'),
      ),
      body: childrenProvider.isLoading
          ? const Center(child: CircularProgressIndicator())
          : childrenProvider.hasChildren
              ? _buildChildrenList(context, childrenProvider)
              : _buildEmptyState(context),
      floatingActionButton: FloatingActionButton(
        onPressed: () => _showAddChildDialog(context, childrenProvider),
        child: const Icon(Icons.add),
      ),
    );
  }

  Widget _buildChildrenList(BuildContext context, ChildrenProvider provider) {
    return ListView.builder(
      padding: const EdgeInsets.all(16),
      itemCount: provider.children.length,
      itemBuilder: (context, index) {
        final child = provider.children[index];
        return _buildChildCard(context, child, provider);
      },
    );
  }

  Widget _buildChildCard(BuildContext context, Child child, ChildrenProvider provider) {
    return Card(
      margin: const EdgeInsets.only(bottom: 16),
      child: ListTile(
        leading: CircleAvatar(
          backgroundColor: child.gender == Gender.male ? Colors.blue : Colors.pink,
          child: Text(
            child.name.isNotEmpty ? child.name[0] : '?',
            style: const TextStyle(color: Colors.white),
          ),
        ),
        title: Text(child.nickname ?? child.name),
        subtitle: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('${child.age}歳 (${_formatDate(child.birthDate)})'),
            if (child.relationship != null) Text('続柄: ${child.relationship}'),
          ],
        ),
        trailing: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            IconButton(
              icon: const Icon(Icons.edit),
              onPressed: () => _showEditChildDialog(context, provider, child),
            ),
            IconButton(
              icon: const Icon(Icons.delete),
              onPressed: () => _showDeleteChildDialog(context, provider, child),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildEmptyState(BuildContext context) {
    return const Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(
            Icons.child_care,
            size: 100,
            color: Colors.grey,
          ),
          SizedBox(height: 16),
          Text(
            '子供情報がありません',
            style: TextStyle(fontSize: 18, color: Colors.grey),
          ),
          SizedBox(height: 8),
          Text(
            '右下の+ボタンから追加してください',
            style: TextStyle(color: Colors.grey),
          ),
        ],
      ),
    );
  }

  void _showAddChildDialog(BuildContext context, ChildrenProvider provider) {
    showDialog<void>(
      context: context,
      builder: (context) => _ChildFormDialog(
        onSave: (name, birthDate, gender, nickname, relationship) async {
          final success = await provider.createChild(
            name: name,
            birthDate: birthDate,
            gender: gender,
            nickname: nickname,
            relationship: relationship,
          );
          if (!success && context.mounted) {
            ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(content: Text(provider.error ?? 'エラーが発生しました')),
            );
          }
        },
      ),
    );
  }

  void _showEditChildDialog(BuildContext context, ChildrenProvider provider, Child child) {
    showDialog<void>(
      context: context,
      builder: (context) => _ChildFormDialog(
        child: child,
        onSave: (name, birthDate, gender, nickname, relationship) async {
          final success = await provider.updateChild(
            child.id,
            name: name,
            birthDate: birthDate,
            gender: gender,
            nickname: nickname,
            relationship: relationship,
          );
          if (!success && context.mounted) {
            ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(content: Text(provider.error ?? 'エラーが発生しました')),
            );
          }
        },
      ),
    );
  }

  void _showDeleteChildDialog(BuildContext context, ChildrenProvider provider, Child child) {
    showDialog<void>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('子供情報を削除'),
        content: Text('${child.name}さんの情報を削除しますか？'),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(),
            child: const Text('キャンセル'),
          ),
          ElevatedButton(
            onPressed: () async {
              Navigator.of(context).pop();
              final success = await provider.deleteChild(child.id);
              if (!success && context.mounted) {
                ScaffoldMessenger.of(context).showSnackBar(
                  SnackBar(content: Text(provider.error ?? 'エラーが発生しました')),
                );
              }
            },
            style: ElevatedButton.styleFrom(
              backgroundColor: Colors.red,
              foregroundColor: Colors.white,
            ),
            child: const Text('削除'),
          ),
        ],
      ),
    );
  }

  String _formatDate(DateTime date) {
    return '${date.year}年${date.month}月${date.day}日';
  }
}

class _ChildFormDialog extends StatefulWidget {
  final Child? child;
  final void Function(String, DateTime, Gender, String?, String?) onSave;

  const _ChildFormDialog({
    required this.onSave,
    this.child,
  });

  @override
  State<_ChildFormDialog> createState() => _ChildFormDialogState();
}

class _ChildFormDialogState extends State<_ChildFormDialog> {
  final _formKey = GlobalKey<FormState>();
  final _nameController = TextEditingController();
  final _nicknameController = TextEditingController();
  final _relationshipController = TextEditingController();
  late DateTime _birthDate;
  late Gender _gender;

  @override
  void initState() {
    super.initState();
    if (widget.child != null) {
      _nameController.text = widget.child!.name;
      _nicknameController.text = widget.child!.nickname ?? '';
      _relationshipController.text = widget.child!.relationship ?? '';
      _birthDate = widget.child!.birthDate;
      _gender = widget.child!.gender;
    } else {
      _birthDate = DateTime.now().subtract(const Duration(days: 365 * 3));
      _gender = Gender.male;
    }
  }

  @override
  void dispose() {
    _nameController.dispose();
    _nicknameController.dispose();
    _relationshipController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: Text(widget.child == null ? '子供を追加' : '子供情報を編集'),
      content: SingleChildScrollView(
        child: Form(
          key: _formKey,
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              TextFormField(
                controller: _nameController,
                decoration: const InputDecoration(labelText: '名前 *'),
                validator: (value) {
                  if (value == null || value.trim().isEmpty) {
                    return '名前を入力してください';
                  }
                  return null;
                },
              ),
              const SizedBox(height: 16),
              TextFormField(
                controller: _nicknameController,
                decoration: const InputDecoration(labelText: 'ニックネーム'),
              ),
              const SizedBox(height: 16),
              TextFormField(
                controller: _relationshipController,
                decoration: const InputDecoration(labelText: '続柄'),
              ),
              const SizedBox(height: 16),
              ListTile(
                title: const Text('生年月日'),
                subtitle: Text(_formatDate(_birthDate)),
                trailing: const Icon(Icons.calendar_today),
                onTap: () async {
                  final picked = await showDatePicker(
                    context: context,
                    initialDate: _birthDate,
                    firstDate: DateTime(2000),
                    lastDate: DateTime.now(),
                  );
                  if (picked != null) {
                    setState(() {
                      _birthDate = picked;
                    });
                  }
                },
              ),
              const SizedBox(height: 16),
              const Text('性別'),
              Row(
                children: [
                  Expanded(
                    child: RadioListTile<Gender>(
                      title: const Text('男'),
                      value: Gender.male,
                      groupValue: _gender,
                      onChanged: (value) {
                        setState(() {
                          _gender = value!;
                        });
                      },
                    ),
                  ),
                  Expanded(
                    child: RadioListTile<Gender>(
                      title: const Text('女'),
                      value: Gender.female,
                      groupValue: _gender,
                      onChanged: (value) {
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
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(),
          child: const Text('キャンセル'),
        ),
        ElevatedButton(
          onPressed: () {
            if (_formKey.currentState!.validate()) {
              Navigator.of(context).pop();
              widget.onSave(
                _nameController.text.trim(),
                _birthDate,
                _gender,
                _nicknameController.text.trim().isEmpty ? null : _nicknameController.text.trim(),
                _relationshipController.text.trim().isEmpty ? null : _relationshipController.text.trim(),
              );
            }
          },
          child: const Text('保存'),
        ),
      ],
    );
  }

  String _formatDate(DateTime date) {
    return '${date.year}年${date.month}月${date.day}日';
  }
}
