import 'package:flutter/material.dart';
import 'package:mobile/screens/newsletter_list_screen.dart';
import 'package:mobile/screens/settings_screen.dart';
import 'package:mobile/screens/unified_timeline_screen.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  static _HomeScreenState? of(BuildContext context) {
    return context.findAncestorStateOfType<_HomeScreenState>();
  }

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  int _currentIndex = 0;
  
  final List<Widget> _screens = const [
    UnifiedTimelineScreen(),
    NewsletterListScreen(),
    SettingsScreen(),
  ];

  void navigateToTab(int index) {
    setState(() {
      _currentIndex = index;
    });
  }
  
  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: _screens[_currentIndex],
      bottomNavigationBar: BottomNavigationBar(
        type: BottomNavigationBarType.fixed,
        currentIndex: _currentIndex,
        onTap: (index) {
          setState(() {
            _currentIndex = index;
          });
        },
        items: const [
          BottomNavigationBarItem(
            icon: Icon(Icons.timeline),
            label: 'タイムライン',
          ),
          BottomNavigationBarItem(
            icon: Icon(Icons.article),
            label: '連絡帳',
          ),
          BottomNavigationBarItem(
            icon: Icon(Icons.settings),
            label: '設定',
          ),
        ],
      ),
    );
  }
}
