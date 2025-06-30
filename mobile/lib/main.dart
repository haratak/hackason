import 'package:firebase_core/firebase_core.dart';
import 'package:flutter/material.dart';
import 'package:mobile/firebase_options.dart';
import 'package:mobile/providers/auth_provider.dart';
import 'package:mobile/providers/children_provider.dart';
import 'package:mobile/providers/family_provider.dart';
import 'package:mobile/providers/storage_provider.dart';
import 'package:mobile/screens/home_screen.dart';
import 'package:mobile/screens/login_screen.dart';
import 'package:mobile/screens/setup_screen.dart';
import 'package:provider/provider.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await Firebase.initializeApp(
    options: DefaultFirebaseOptions.currentPlatform,
  );
  runApp(const MyApp());
}

class MyApp extends StatelessWidget {
  const MyApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MultiProvider(
      providers: [
        ChangeNotifierProvider(create: (_) => AuthProvider()),
        ChangeNotifierProvider(create: (_) => StorageProvider()),
        ChangeNotifierProvider(create: (_) => FamilyProvider()),
        ChangeNotifierProvider(create: (_) => ChildrenProvider()),
      ],
      child: MaterialApp(
        title: '連絡帳クライアント',
        theme: ThemeData(
          primarySwatch: Colors.blue,
          useMaterial3: true,
        ),
        home: const AuthWrapper(),
      ),
    );
  }
}

class AuthWrapper extends StatelessWidget {
  const AuthWrapper({super.key});

  @override
  Widget build(BuildContext context) {
    final authProvider = context.watch<AuthProvider>();

    debugPrint(
      'AuthWrapper: isAuthenticated = ${authProvider.isAuthenticated}',
    );
    debugPrint('AuthWrapper: user = ${authProvider.user?.uid}');

    if (authProvider.isAuthenticated) {
      return const SetupChecker();
    } else {
      return const LoginScreen();
    }
  }
}

class SetupChecker extends StatefulWidget {
  const SetupChecker({super.key});

  @override
  State<SetupChecker> createState() => _SetupCheckerState();
}

class _SetupCheckerState extends State<SetupChecker> {
  bool _isInitializing = true;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _checkSetup();
    });
  }

  Future<void> _checkSetup() async {
    debugPrint('SetupChecker: Starting setup check...');
    final familyProvider = context.read<FamilyProvider>();
    final childrenProvider = context.read<ChildrenProvider>();

    // Load family and children data
    debugPrint('SetupChecker: Loading user family...');
    await familyProvider.loadUserFamily();
    debugPrint('SetupChecker: hasFamily = ${familyProvider.hasFamily}');

    if (familyProvider.hasFamily) {
      debugPrint('SetupChecker: Loading children...');
      await childrenProvider.loadChildren();
      debugPrint('SetupChecker: hasChildren = ${childrenProvider.hasChildren}');
    }

    if (mounted) {
      setState(() {
        _isInitializing = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_isInitializing) {
      return const Scaffold(
        body: Center(
          child: CircularProgressIndicator(),
        ),
      );
    }

    final familyProvider = context.watch<FamilyProvider>();
    final childrenProvider = context.watch<ChildrenProvider>();

    // Check if setup is needed
    if (!familyProvider.hasFamily || !childrenProvider.hasChildren) {
      return const SetupScreen();
    }

    return const HomeScreen();
  }
}
