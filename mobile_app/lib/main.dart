/// Quik Field Notes — Mobile Field Companion (Android & iOS)
/// Powered by Nasrullah Khan
/// Features: Full-Screen GIS Canvas, High-Speed GNSS Tracking,
/// Free Two-Finger Touch Rotation & True North Reset,
/// Local Map Overlays (.shp zip, .gpx, .kml, .geojson) with Opacity Sliders,
/// Digitizing Tool (Polygons/Lines with Field Notes),
/// Medium-Sized High-Visibility Buttons for Field Use,
/// Multi-Accent Speech-to-Text Engine, and Standardized Multi-Format Export.

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:webview_flutter/webview_flutter.dart';
import 'package:webview_flutter_android/webview_flutter_android.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:speech_to_text/speech_to_text.dart' as stt;

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  SystemChrome.setEnabledSystemUIMode(SystemUiMode.immersiveSticky);
  runApp(const QuikFieldNotesApp());
}

class QuikFieldNotesApp extends StatefulWidget {
  const QuikFieldNotesApp({super.key});

  @override
  State<QuikFieldNotesApp> createState() => _QuikFieldNotesAppState();
}

class _QuikFieldNotesAppState extends State<QuikFieldNotesApp> {
  WebViewController? _controller;
  bool _isLoading = true;
  final stt.SpeechToText _speech = stt.SpeechToText();
  bool _speechInitialized = false;

  @override
  void initState() {
    super.initState();
    _initWebView();
  }

  Future<void> _initWebView() async {
    // Request runtime hardware permissions (Location, Camera, Microphone, Storage)
    try {
      await [
        Permission.location,
        Permission.camera,
        Permission.microphone,
        Permission.storage,
      ].request();
    } catch (_) {}

    final WebViewController controller = WebViewController();

    // Android WebViewController configuration for high-precision GNSS, microphone and camera
    if (controller.platform is AndroidWebViewController) {
      final androidController = controller.platform as AndroidWebViewController;
      androidController.setGeolocationPermissionsPromptCallbacks(
        onShowPrompt: (request) async {
          return const GeolocationPermissionsResponse(allow: true, retain: true);
        },
      );
      androidController.setOnPlatformPermissionRequest(
        (request) async {
          request.grant();
        },
      );
    }

    controller
      ..setJavaScriptMode(JavaScriptMode.unrestricted)
      ..setBackgroundColor(const Color(0xFF0A0F1D))
      ..addJavaScriptChannel(
        'NativeSpeechBridge',
        onMessageReceived: (JavaScriptMessage message) {
          _handleSpeechCommand(message.message);
        },
      )
      ..setNavigationDelegate(
        NavigationDelegate(
          onPageFinished: (String url) {
            if (mounted) {
              setState(() {
                _isLoading = false;
              });
            }
          },
        ),
      )
      ..loadFlutterAsset('assets/web/index.html');

    if (mounted) {
      setState(() {
        _controller = controller;
      });
    }
  }

  Future<void> _handleSpeechCommand(String command) async {
    if (command == 'start') {
      try {
        if (!_speechInitialized) {
          _speechInitialized = await _speech.initialize(
            onError: (val) {
              final err = val.errorMsg.replaceAll("'", "\\'");
              _controller?.runJavaScript("if(window.onNativeSpeechError) window.onNativeSpeechError('$err');");
            },
            onStatus: (val) {
              _controller?.runJavaScript("if(window.onNativeSpeechStatus) window.onNativeSpeechStatus('$val');");
            },
          );
        }

        if (_speechInitialized) {
          await _speech.listen(
            onResult: (val) {
              final recognized = val.recognizedWords.replaceAll("'", "\\'").replaceAll('"', '\\"');
              final isFinal = val.finalResult;
              _controller?.runJavaScript("if(window.onNativeSpeechResult) window.onNativeSpeechResult('$recognized', $isFinal);");
            },
            cancelOnError: false,
            partialResults: true,
          );
        }
      } catch (e) {
        _controller?.runJavaScript("if(window.onNativeSpeechError) window.onNativeSpeechError('Init error');");
      }
    } else if (command == 'stop') {
      try {
        if (_speech.isListening) {
          await _speech.stop();
        }
      } catch (_) {}
    }
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Quik Field Notes',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        brightness: Brightness.dark,
        scaffoldBackgroundColor: const Color(0xFF0A0F1D),
        primaryColor: const Color(0xFF38BDF8),
      ),
      home: Scaffold(
        backgroundColor: const Color(0xFF0A0F1D),
        body: SafeArea(
          top: false,
          bottom: false,
          child: _controller == null
              ? const Center(
                  child: CircularProgressIndicator(
                    color: Color(0xFF00F0FF),
                  ),
                )
              : Stack(
                  children: [
                    WebViewWidget(controller: _controller!),
                    if (_isLoading)
                      const Center(
                        child: CircularProgressIndicator(
                          color: Color(0xFF00F0FF),
                        ),
                      ),
                  ],
                ),
        ),
      ),
    );
  }
}
