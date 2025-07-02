import 'package:flutter/material.dart';
import 'package:kids_diary/screens/settings_screen.dart';
import 'package:kids_diary/screens/unified_timeline_screen.dart';
import 'package:kids_diary/screens/weekly_notebook_screen.dart';

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
    WeeklyNotebookScreen(),
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
            icon: Icon(Icons.menu_book),
            label: '週刊ノート',
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
