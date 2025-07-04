import 'package:flutter/material.dart';
import 'package:kids_diary/providers/auth_provider.dart';
import 'package:kids_diary/screens/family_screen.dart';
import 'package:provider/provider.dart';

class SettingsScreen extends StatelessWidget {
  const SettingsScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final authProvider = Provider.of<AuthProvider>(context);
    
    return Scaffold(
      appBar: AppBar(
        title: const Text('設定'),
      ),
      body: ListView(
        children: [
          ListTile(
            leading: const Icon(Icons.person),
            title: const Text('アカウント'),
            subtitle: Text(authProvider.user?.email ?? ''),
          ),
          const Divider(),
          ListTile(
            leading: const Icon(Icons.family_restroom),
            title: const Text('ファミリー設定'),
            subtitle: const Text('ファミリーとお子様の情報を管理'),
            trailing: const Icon(Icons.arrow_forward_ios),
            onTap: () {
              Navigator.push(
                context,
                MaterialPageRoute(builder: (context) => const FamilyScreen()),
              );
            },
          ),
          const Divider(),
          ListTile(
            leading: const Icon(Icons.logout, color: Colors.red),
            title: const Text(
              'ログアウト',
              style: TextStyle(color: Colors.red),
            ),
            onTap: () => _showLogoutDialog(context),
          ),
        ],
      ),
    );
  }
  
  void _showLogoutDialog(BuildContext context) {
    showDialog<void>(
      context: context,
      builder: (BuildContext context) {
        return AlertDialog(
          title: const Text('ログアウト'),
          content: const Text('ログアウトしますか？'),
          actions: [
            TextButton(
              onPressed: () => Navigator.of(context).pop(),
              child: const Text('キャンセル'),
            ),
            TextButton(
              onPressed: () async {
                Navigator.of(context).pop();
                final authProvider = Provider.of<AuthProvider>(context, listen: false);
                await authProvider.signOut();
              },
              child: const Text(
                'ログアウト',
                style: TextStyle(color: Colors.red),
              ),
            ),
          ],
        );
      },
    );
  }
}
