import 'package:flutter/material.dart';

import 'controller.dart';
import 'shell.dart';

class AiosApp extends StatefulWidget {
  const AiosApp({super.key});

  @override
  State<AiosApp> createState() => _AiosAppState();
}

class _AiosAppState extends State<AiosApp> {
  late final AiosController controller;

  @override
  void initState() {
    super.initState();
    controller = AiosController()..initialize();
    controller.addListener(_refresh);
  }

  void _refresh() => setState(() {});

  @override
  void dispose() {
    controller.removeListener(_refresh);
    controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final brightness = controller.darkMode ? Brightness.dark : Brightness.light;
    final scheme = ColorScheme.fromSeed(
      seedColor: const Color(0xFFA7FF3C),
      brightness: brightness,
      surface: controller.darkMode
          ? const Color(0xFF121512)
          : const Color(0xFFF5F6F2),
    );
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      title: 'AiOS Assistant',
      theme: ThemeData(
        colorScheme: scheme,
        useMaterial3: true,
        scaffoldBackgroundColor: scheme.surface,
        cardTheme: CardThemeData(
          elevation: 0,
          margin: EdgeInsets.zero,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(8),
            side: BorderSide(color: scheme.outlineVariant),
          ),
        ),
        inputDecorationTheme: const InputDecorationTheme(
          border: OutlineInputBorder(),
        ),
      ),
      home: AiosShell(controller: controller),
    );
  }
}
