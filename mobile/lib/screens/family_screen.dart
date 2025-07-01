import 'package:flutter/material.dart';
import 'package:kids_diary/providers/auth_provider.dart';
import 'package:kids_diary/providers/family_provider.dart';
import 'package:kids_diary/screens/children_screen.dart';
import 'package:provider/provider.dart';

class FamilyScreen extends StatefulWidget {
  const FamilyScreen({super.key});

  @override
  State<FamilyScreen> createState() => _FamilyScreenState();
}

class _FamilyScreenState extends State<FamilyScreen> {
  final _familyNameController = TextEditingController();

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<FamilyProvider>().loadUserFamily();
    });
  }

  @override
  void dispose() {
    _familyNameController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final familyProvider = context.watch<FamilyProvider>();

    return Scaffold(
      appBar: AppBar(
        title: const Text('ファミリー管理'),
      ),
      body: familyProvider.isLoading
          ? const Center(child: CircularProgressIndicator())
          : familyProvider.hasFamily
              ? _buildFamilyView(context, familyProvider)
              : _buildNoFamilyView(context, familyProvider),
    );
  }

  Widget _buildFamilyView(BuildContext context, FamilyProvider familyProvider) {
    final family = familyProvider.currentFamily!;
    final currentUserId = context.read<AuthProvider>().user?.uid;
    final isCreator = currentUserId == family.createdBy;

    return Padding(
      padding: const EdgeInsets.all(16.0),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16.0),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Text(
                        family.name,
                        style: Theme.of(context).textTheme.headlineSmall,
                      ),
                      if (isCreator)
                        IconButton(
                          icon: const Icon(Icons.edit),
                          onPressed: () => _showEditFamilyDialog(context, familyProvider),
                        ),
                    ],
                  ),
                  const SizedBox(height: 8),
                  Text('メンバー数: ${family.members.length}'),
                  Text('作成日: ${_formatDate(family.createdAt)}'),
                ],
              ),
            ),
          ),
          const SizedBox(height: 16),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                'メンバー',
                style: Theme.of(context).textTheme.titleMedium,
              ),
              ElevatedButton.icon(
                onPressed: () {
                  Navigator.push(
                    context,
                    MaterialPageRoute<void>(builder: (context) => const ChildrenScreen()),
                  );
                },
                icon: const Icon(Icons.child_care),
                label: const Text('子供情報'),
              ),
            ],
          ),
          const SizedBox(height: 8),
          Expanded(
            child: ListView.builder(
              itemCount: family.members.length,
              itemBuilder: (context, index) {
                final memberId = family.members[index];
                final isCurrentUser = memberId == currentUserId;
                final canRemove = isCreator && !isCurrentUser && memberId != family.createdBy;

                return ListTile(
                  leading: const CircleAvatar(
                    child: Icon(Icons.person),
                  ),
                  title: Text(memberId),
                  subtitle: memberId == family.createdBy ? const Text('作成者') : null,
                  trailing: canRemove
                      ? IconButton(
                          icon: const Icon(Icons.remove_circle),
                          onPressed: () => _removeMember(context, familyProvider, memberId),
                        )
                      : null,
                );
              },
            ),
          ),
          if (isCreator) ...[
            const SizedBox(height: 16),
            SizedBox(
              width: double.infinity,
              child: ElevatedButton.icon(
                onPressed: () => _showDeleteFamilyDialog(context, familyProvider),
                icon: const Icon(Icons.delete),
                label: const Text('ファミリーを削除'),
                style: ElevatedButton.styleFrom(
                  backgroundColor: Colors.red,
                  foregroundColor: Colors.white,
                ),
              ),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildNoFamilyView(BuildContext context, FamilyProvider familyProvider) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(
              Icons.family_restroom,
              size: 100,
              color: Colors.grey,
            ),
            const SizedBox(height: 16),
            const Text(
              'ファミリーに参加していません',
              style: TextStyle(fontSize: 18),
            ),
            const SizedBox(height: 32),
            ElevatedButton.icon(
              onPressed: () => _showCreateFamilyDialog(context, familyProvider),
              icon: const Icon(Icons.add),
              label: const Text('ファミリーを作成'),
            ),
          ],
        ),
      ),
    );
  }

  void _showCreateFamilyDialog(BuildContext context, FamilyProvider familyProvider) {
    _familyNameController.clear();
    showDialog<void>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('ファミリーを作成'),
        content: TextField(
          controller: _familyNameController,
          decoration: const InputDecoration(
            labelText: 'ファミリー名',
            hintText: '例: 田中家',
          ),
          autofocus: true,
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(),
            child: const Text('キャンセル'),
          ),
          ElevatedButton(
            onPressed: () async {
              final name = _familyNameController.text.trim();
              if (name.isNotEmpty) {
                Navigator.of(context).pop();
                final success = await familyProvider.createFamily(name);
                if (!success && context.mounted) {
                  ScaffoldMessenger.of(context).showSnackBar(
                    SnackBar(content: Text(familyProvider.error ?? 'エラーが発生しました')),
                  );
                }
              }
            },
            child: const Text('作成'),
          ),
        ],
      ),
    );
  }

  void _showEditFamilyDialog(BuildContext context, FamilyProvider familyProvider) {
    _familyNameController.text = familyProvider.currentFamily?.name ?? '';
    showDialog<void>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('ファミリー名を編集'),
        content: TextField(
          controller: _familyNameController,
          decoration: const InputDecoration(
            labelText: 'ファミリー名',
          ),
          autofocus: true,
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(),
            child: const Text('キャンセル'),
          ),
          ElevatedButton(
            onPressed: () async {
              final name = _familyNameController.text.trim();
              if (name.isNotEmpty) {
                Navigator.of(context).pop();
                final success = await familyProvider.updateFamilyName(name);
                if (!success && context.mounted) {
                  ScaffoldMessenger.of(context).showSnackBar(
                    SnackBar(content: Text(familyProvider.error ?? 'エラーが発生しました')),
                  );
                }
              }
            },
            child: const Text('更新'),
          ),
        ],
      ),
    );
  }

  void _showDeleteFamilyDialog(BuildContext context, FamilyProvider familyProvider) {
    showDialog<void>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('ファミリーを削除'),
        content: const Text('本当にファミリーを削除しますか？この操作は取り消せません。'),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(),
            child: const Text('キャンセル'),
          ),
          ElevatedButton(
            onPressed: () async {
              Navigator.of(context).pop();
              final success = await familyProvider.deleteFamily();
              if (!success && context.mounted) {
                ScaffoldMessenger.of(context).showSnackBar(
                  SnackBar(content: Text(familyProvider.error ?? 'エラーが発生しました')),
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

  void _removeMember(BuildContext context, FamilyProvider familyProvider, String memberId) {
    showDialog<void>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('メンバーを削除'),
        content: const Text('このメンバーをファミリーから削除しますか？'),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(),
            child: const Text('キャンセル'),
          ),
          ElevatedButton(
            onPressed: () async {
              Navigator.of(context).pop();
              final success = await familyProvider.removeMember(memberId);
              if (!success && context.mounted) {
                ScaffoldMessenger.of(context).showSnackBar(
                  SnackBar(content: Text(familyProvider.error ?? 'エラーが発生しました')),
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
    return '${date.year}/${date.month.toString().padLeft(2, '0')}/${date.day.toString().padLeft(2, '0')}';
  }
}
