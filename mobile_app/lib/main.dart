/// Quik Field Notes — Mobile Field Companion (Android & iOS)
/// Powered by Nasrullah Khan
/// Features: Full-Screen GIS Canvas, High-Speed GNSS Tracking,
/// "Fast & Furious" Multi-Accent Speech-to-Text Engine (Arab & Asian English, Roman Urdu, Roman Arabic, Native Arabic/Urdu),
/// and Standardized *.scoutpkg Synchronisation.

import 'dart:io';
import 'package:flutter/material.dart';
import 'package:geolocator/geolocator.dart';
import 'package:speech_to_text/speech_to_text.dart' as stt;
import 'package:image_picker/image_picker.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';
import 'models/scout_models.dart';
import 'services/package_service.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const QuikFieldNotesApp());
}

class QuikFieldNotesApp extends StatelessWidget {
  const QuikFieldNotesApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Quik Field Notes',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        brightness: Brightness.dark,
        scaffoldBackgroundColor: const Color(0xFF0A0F1D),
        primaryColor: const Color(0xFF38BDF8),
        colorScheme: const ColorScheme.dark(
          primary: Color(0xFF38BDF8),
          secondary: Color(0xFF0284C7),
          surface: Color(0xFF1E293B),
          background: Color(0xFF0A0F1D),
        ),
      ),
      home: const QFieldMainScreen(),
    );
  }
}

class QFieldMainScreen extends StatefulWidget {
  const QFieldMainScreen({super.key});

  @override
  State<QFieldMainScreen> createState() => _QFieldMainScreenState();
}

class _QFieldMainScreenState extends State<QFieldMainScreen> with SingleTickerProviderStateMixin {
  // Project & Crew State
  String _projectId = 'No Project';
  final String _crewName = 'Crew S-86';
  final String _scoutName = 'Field Scout';

  // Live in-memory data
  final List<JournalThought> _thoughts = [];
  final List<WaypointItem> _waypoints = [];
  final List<ScoutPhotoItem> _photos = [];
  final List<Map<String, dynamic>> _trackPoints = [];

  // Map & GIS state
  final MapController _mapController = MapController();
  Position? _currentPosition;
  bool _isTracking = false;
  int _activeLayerIndex = 0; // 0 = Satellite, 1 = OSM
  LatLng _mapCenter = const LatLng(24.5, 50.5);

  // Fast & Furious Speech-to-Text Engine
  final stt.SpeechToText _speech = stt.SpeechToText();
  bool _isSpeechAvailable = false;
  bool _isListening = false;
  String _selectedAccentMode = 'en_SA';
  final TextEditingController _voiceTextController = TextEditingController();
  String _selectedSectionId = 'auto';

  // Drawer Animation Controller
  late AnimationController _drawerAnimController;
  bool _isDrawerOpen = false;

  final List<Map<String, String>> _accentOptions = [
    {'code': 'en_SA', 'label': '🇸🇦 English (Saudi/Arab Accent)'},
    {'code': 'en_IN', 'label': '🇵🇰 English (South Asian Accent)'},
    {'code': 'roman_urdu', 'label': '🇵🇰 Roman Urdu (Urdu in Latin Script)'},
    {'code': 'roman_arabic', 'label': '🇸🇦 Roman Arabic (Arabizi / Franco-Arabic)'},
    {'code': 'ar_SA', 'label': '🇸🇦 العربية (Native Arabic)'},
    {'code': 'ur_PK', 'label': '🇵🇰 اردو (Native Urdu)'},
    {'code': 'en_US', 'label': '🌐 International English'},
  ];

  @override
  void initState() {
    super.initState();
    _drawerAnimController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 280),
    );
    _initGeolocation();
    _initSpeech();
  }

  @override
  void dispose() {
    _drawerAnimController.dispose();
    _voiceTextController.dispose();
    super.dispose();
  }

  /* --------------------------------------------------------------------------
     1. HIGH-ACCURACY GEOLOCATION & LIVE TRACKING
     -------------------------------------------------------------------------- */
  Future<void> _initGeolocation() async {
    bool serviceEnabled = await Geolocator.isLocationServiceEnabled();
    if (!serviceEnabled) return;

    LocationPermission permission = await Geolocator.checkPermission();
    if (permission == LocationPermission.denied) {
      permission = await Geolocator.requestPermission();
      if (permission == LocationPermission.denied) return;
    }

    Geolocator.getPositionStream(
      locationSettings: const LocationSettings(
        accuracy: LocationAccuracy.high,
        distanceFilter: 3,
      ),
    ).listen((Position pos) {
      if (!mounted) return;
      setState(() {
        _currentPosition = pos;
        if (_isTracking) {
          _trackPoints.add({
            'lat': pos.latitude,
            'lon': pos.longitude,
            'ele': pos.altitude,
            'time': DateTime.now().toIso8601String(),
          });
        }
      });
    });
  }

  void _toggleTracking() {
    setState(() {
      _isTracking = !_isTracking;
    });
    final snack = SnackBar(
      content: Text(
        _isTracking ? '🔴 Track Recording Started' : '⏹ Track Stopped (${_trackPoints.length} points logged)',
        style: const TextStyle(fontWeight: FontWeight.bold),
      ),
      backgroundColor: _isTracking ? const Color(0xFFEF4444) : const Color(0xFF10B981),
      duration: const Duration(seconds: 2),
    );
    ScaffoldMessenger.of(context).showSnackBar(snack);
  }

  void _centerOnGps() {
    if (_currentPosition != null) {
      _mapController.move(
        LatLng(_currentPosition!.latitude, _currentPosition!.longitude),
        16.0,
      );
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('GNSS fix searching...')),
      );
    }
  }

  void _toggleMapLayer() {
    setState(() {
      _activeLayerIndex = (_activeLayerIndex + 1) % 2;
    });
    final name = _activeLayerIndex == 0 ? 'ESRI Satellite' : 'OpenStreetMap';
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text('Switched to: $name'), duration: const Duration(seconds: 1)),
    );
  }

  /* --------------------------------------------------------------------------
     2. FAST & FURIOUS MULTI-ACCENT SPEECH ENGINE
     -------------------------------------------------------------------------- */
  Future<void> _initSpeech() async {
    try {
      _isSpeechAvailable = await _speech.initialize(
        onError: (e) {
          if (mounted) setState(() => _isListening = false);
        },
        onStatus: (status) {
          if (status == 'done' && mounted) {
            setState(() => _isListening = false);
          }
        },
      );
    } catch (_) {}
  }

  String _getLocaleForEngine(String mode) {
    switch (mode) {
      case 'en_SA':
        return 'en_SA';
      case 'en_IN':
        return 'en_IN';
      case 'roman_urdu':
      case 'ur_PK':
        return 'ur_PK';
      case 'roman_arabic':
      case 'ar_SA':
        return 'ar_SA';
      default:
        return 'en_US';
    }
  }

  void _toggleSpeech() async {
    if (!_isSpeechAvailable) {
      await _initSpeech();
      if (!_isSpeechAvailable) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Speech recognition not available on this device')),
        );
        return;
      }
    }

    if (_isListening) {
      await _speech.stop();
      setState(() => _isListening = false);
    } else {
      final localeId = _getLocaleForEngine(_selectedAccentMode);
      setState(() => _isListening = true);

      // Open drawer so the user sees real-time transcription
      if (!_isDrawerOpen) _toggleDrawer();

      await _speech.listen(
        localeId: localeId,
        listenMode: stt.ListenMode.dictation,
        partialResults: true, // Streaming instant feedback ("Fast & Furious")
        onResult: (result) {
          if (!mounted) return;
          String transcribed = result.recognizedWords;

          // Process through seismic accent & transliteration normalizer
          transcribed = _normalizeSeismicSpeech(transcribed, _selectedAccentMode);

          setState(() {
            _voiceTextController.text = transcribed;
            _autoAssessSection(transcribed);
          });
        },
      );
    }
  }

  String _normalizeSeismicSpeech(String input, String mode) {
    String text = input.trim();

    if (mode == 'roman_urdu') {
      text = _transliterateUrduToRoman(text);
    } else if (mode == 'roman_arabic') {
      text = _transliterateArabicToRoman(text);
    }

    // Seismic domain phonetic substitutions for Arab & Asian accents
    final replacements = {
      RegExp(r'\b(sabka|sabkah|sebkha)\b', caseSensitive: false): 'Sabkha',
      RegExp(r'\b(wibrator|vibrater|vibro buggy)\b', caseSensitive: false): 'Vibrator',
      RegExp(r'\b(jabal|gebel)\b', caseSensitive: false): 'Jebel',
      RegExp(r'\b(pipe line|utility line)\b', caseSensitive: false): 'Pipeline',
      RegExp(r'\b(dikaaka|dikaka)\b', caseSensitive: false): 'Sand Dikaka',
      RegExp(r'\b(mustashfa|aspatal)\b', caseSensitive: false): 'Hospital',
      RegExp(r'\b(tasreeh|clearance)\b', caseSensitive: false): 'Permitting Clearance',
      RegExp(r'\b(khatar|hira risk)\b', caseSensitive: false): 'HSE Hazard',
      RegExp(r'\b(nefood|nafud)\b', caseSensitive: false): 'Sand Dunes',
    };

    replacements.forEach((pattern, value) {
      text = text.replaceAll(pattern, value);
    });

    return text;
  }

  String _transliterateUrduToRoman(String urduStr) {
    const uMap = {
      'ا': 'a', 'آ': 'aa', 'ب': 'b', 'پ': 'p', 'ت': 't', 'ٹ': 't', 'ث': 's',
      'ج': 'j', 'چ': 'ch', 'ح': 'h', 'خ': 'kh', 'د': 'd', 'ڈ': 'd', 'ذ': 'z',
      'ر': 'r', 'ڑ': 'r', 'ز': 'z', 'ژ': 'zh', 'س': 's', 'ش': 'sh', 'ص': 's',
      'ض': 'z', 'ط': 't', 'ظ': 'z', 'ع': 'a', 'غ': 'gh', 'ف': 'f', 'ق': 'q',
      'ک': 'k', 'گ': 'g', 'ل': 'l', 'م': 'm', 'ن': 'n', 'ں': 'n', 'و': 'w',
      'ہ': 'h', 'ھ': 'h', 'ء': '', 'ی': 'y', 'ے': 'e', ' ': ' '
    };
    final sb = StringBuffer();
    for (int i = 0; i < urduStr.length; i++) {
      final ch = urduStr[i];
      sb.write(uMap[ch] ?? ch);
    }
    return sb.toString();
  }

  String _transliterateArabicToRoman(String arStr) {
    const aMap = {
      'ا': 'a', 'أ': 'a', 'إ': 'e', 'آ': 'aa', 'ب': 'b', 'ت': 't', 'ث': 'th',
      'ج': 'j', 'ح': '7', 'خ': 'kh', 'د': 'd', 'ذ': 'th', 'ر': 'r', 'ز': 'z',
      'س': 's', 'ش': 'sh', 'ص': '9', 'ض': 'd', 'ط': '6', 'ظ': 'z', 'ع': '3',
      'غ': 'gh', 'ف': 'f', 'ق': '8', 'ك': 'k', 'ل': 'l', 'م': 'm', 'ن': 'n',
      'ه': 'h', 'ة': 'a', 'و': 'w', 'ي': 'y', 'ى': 'a', ' ': ' '
    };
    final sb = StringBuffer();
    for (int i = 0; i < arStr.length; i++) {
      final ch = arStr[i];
      sb.write(aMap[ch] ?? ch);
    }
    return sb.toString();
  }

  void _autoAssessSection(String text) {
    final lower = text.toLowerCase();
    if (lower.contains('road') || lower.contains('highway') || lower.contains('access') || lower.contains('asphalt') || lower.contains('rasta')) {
      _selectedSectionId = 'sec_03_access';
    } else if (lower.contains('dune') || lower.contains('sand') || lower.contains('sabkha') || lower.contains('ret') || lower.contains('jebel')) {
      _selectedSectionId = 'sec_06_terrain';
    } else if (lower.contains('permit') || lower.contains('gate') || lower.contains('clearance') || lower.contains('security')) {
      _selectedSectionId = 'sec_08_permits';
    } else if (lower.contains('camp') || lower.contains('staging') || lower.contains('generator')) {
      _selectedSectionId = 'sec_09_camps';
    } else if (lower.contains('hospital') || lower.contains('clinic') || lower.contains('medevac') || lower.contains('doctor')) {
      _selectedSectionId = 'sec_10_hospitals';
    } else if (lower.contains('stuck') || lower.contains('obstacle') || lower.contains('slip face')) {
      _selectedSectionId = 'sec_11_difficulties';
    } else if (lower.contains('hazard') || lower.contains('hira') || lower.contains('heat') || lower.contains('snake')) {
      _selectedSectionId = 'sec_12_hazards';
    }
  }

  /* --------------------------------------------------------------------------
     3. SAVING THOUGHTS & WAYPOINTS
     -------------------------------------------------------------------------- */
  void _saveThought() {
    final text = _voiceTextController.text.trim();
    if (text.isEmpty) return;

    final thought = JournalThought(
      id: 'TH_${DateTime.now().millisecondsSinceEpoch}',
      timestamp: DateTime.now().toString().substring(0, 19),
      text: text,
      latitude: _currentPosition?.latitude,
      longitude: _currentPosition?.longitude,
      sectionId: _selectedSectionId == 'auto' ? 'sec_06_terrain' : _selectedSectionId,
      categoryName: _getCategoryLabel(_selectedSectionId),
    );

    setState(() {
      _thoughts.insert(0, thought);
      _voiceTextController.clear();
      _isListening = false;
    });

    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('💾 Thought saved to Field Journal!'), duration: Duration(seconds: 1)),
    );
  }

  String _getCategoryLabel(String secId) {
    switch (secId) {
      case 'sec_03_access': return 'Access & Road';
      case 'sec_06_terrain': return 'Terrain & Dunes';
      case 'sec_08_permits': return 'Permits & Standoff';
      case 'sec_09_camps': return 'Fly Camps';
      case 'sec_10_hospitals': return 'Hospital & Medevac';
      case 'sec_11_difficulties': return 'Surface Obstacles';
      case 'sec_12_hazards': return 'HSE Hazards';
      default: return 'General Field Observation';
    }
  }

  Future<void> _openQuickWaypointModal() async {
    final lat = _currentPosition?.latitude ?? _mapCenter.latitude;
    final lon = _currentPosition?.longitude ?? _mapCenter.longitude;

    final nameController = TextEditingController();
    final notesController = TextEditingController();
    String category = 'Sabkha';

    await showDialog(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (context, setDlgState) => AlertDialog(
          backgroundColor: const Color(0xFF1E293B),
          title: const Text('📍 Quick Waypoint Drop', style: TextStyle(color: Color(0xFF38BDF8), fontWeight: FontWeight.bold)),
          content: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('GNSS: ${lat.toStringAsFixed(5)}, ${lon.toStringAsFixed(5)}', style: const TextStyle(fontSize: 11, color: Colors.grey)),
                const SizedBox(height: 10),
                TextField(
                  controller: nameController,
                  decoration: const InputDecoration(
                    labelText: 'Waypoint Name / Obstacle',
                    filled: true,
                    fillColor: Color(0xFF0F172A),
                  ),
                ),
                const SizedBox(height: 10),
                DropdownButtonFormField<String>(
                  value: category,
                  dropdownColor: const Color(0xFF0F172A),
                  decoration: const InputDecoration(labelText: 'Category', filled: true, fillColor: Color(0xFF0F172A)),
                  items: const [
                    DropdownMenuItem(value: 'Sabkha', child: Text('Sabkha / Salt Flat')),
                    DropdownMenuItem(value: 'Sand Dune', child: Text('High Dune / Slip Face')),
                    DropdownMenuItem(value: 'Pipeline', child: Text('Pipeline Corridor')),
                    DropdownMenuItem(value: 'Escarpment', child: Text('Escarpment / Jebel')),
                    DropdownMenuItem(value: 'Fly Camp', child: Text('Fly Camp Proposal')),
                    DropdownMenuItem(value: 'Hazard', child: Text('HSE Hazard / Warning')),
                  ],
                  onChanged: (val) {
                    if (val != null) setDlgState(() => category = val);
                  },
                ),
                const SizedBox(height: 10),
                TextField(
                  controller: notesController,
                  maxLines: 2,
                  decoration: const InputDecoration(
                    labelText: 'Field Notes',
                    filled: true,
                    fillColor: Color(0xFF0F172A),
                  ),
                ),
              ],
            ),
          ),
          actions: [
            TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Cancel')),
            ElevatedButton(
              style: ElevatedButton.styleFrom(backgroundColor: const Color(0xFF0284C7)),
              onPressed: () {
                final wp = WaypointItem(
                  name: nameController.text.trim().isEmpty ? category : nameController.text.trim(),
                  note: '${category}: ${notesController.text.trim()}',
                  latitude: lat,
                  longitude: lon,
                  timestamp: DateTime.now().toIso8601String(),
                );
                setState(() => _waypoints.add(wp));
                Navigator.pop(ctx);
                ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('📍 Saved Waypoint: ${wp.name}')));
              },
              child: const Text('Save Waypoint'),
            ),
          ],
        ),
      ),
    );
  }

  bool _promptPhotoNotes = true;

  Future<void> _capturePhoto() async {
    final picker = ImagePicker();
    final photo = await picker.pickImage(source: ImageSource.camera, imageQuality: 85);
    if (photo != null) {
      String photoCaption = '';
      if (_promptPhotoNotes && mounted) {
        final comment = await _showPhotoNoteDialog(photo.path);
        if (comment != null) photoCaption = comment;
      }

      final photoItem = ScoutPhotoItem(
        filePath: photo.path,
        filename: 'PHOTO_${DateTime.now().millisecondsSinceEpoch}.jpg',
        caption: photoCaption,
        note: photoCaption,
        latitude: _currentPosition?.latitude,
        longitude: _currentPosition?.longitude,
        timestamp: DateTime.now().toIso8601String(),
      );
      setState(() => _photos.add(photoItem));
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('📷 Geotagged Photo Saved (${_photos.length} total)')),
        );
      }
    }
  }

  Future<String?> _showPhotoNoteDialog(String imagePath) async {
    final noteController = TextEditingController();
    bool isDictating = false;

    return showDialog<String>(
      context: context,
      barrierDismissible: false,
      builder: (ctx) => StatefulBuilder(
        builder: (context, setDlgState) {
          return AlertDialog(
            backgroundColor: const Color(0xFF1E293B),
            title: const Text('📷 Photo Observation / Note', style: TextStyle(color: Color(0xFF38BDF8), fontWeight: FontWeight.bold, fontSize: 16)),
            content: SingleChildScrollView(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  ClipRRect(
                    borderRadius: BorderRadius.circular(8),
                    child: Image.file(File(imagePath), height: 130, width: double.infinity, fit: BoxFit.cover),
                  ),
                  const SizedBox(height: 8),
                  Text('GNSS: ${_currentPosition != null ? "±${_currentPosition!.accuracy.round()}m" : "No GPS fix"}', style: const TextStyle(fontSize: 11, color: Colors.grey)),
                  const SizedBox(height: 8),
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      const Text('Photo Note / Caption:', style: TextStyle(fontSize: 12, fontWeight: FontWeight.bold)),
                      ElevatedButton.icon(
                        style: ElevatedButton.styleFrom(
                          backgroundColor: isDictating ? const Color(0xFFEF4444) : const Color(0xFF0284C7),
                          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                        ),
                        onPressed: () async {
                          if (isDictating) {
                            await _speech.stop();
                            setDlgState(() => isDictating = false);
                          } else {
                            if (!_isSpeechAvailable) await _initSpeech();
                            setDlgState(() => isDictating = true);
                            await _speech.listen(
                              localeId: _getLocaleForEngine(_selectedAccentMode),
                              onResult: (res) {
                                setDlgState(() {
                                  noteController.text = _normalizeSeismicSpeech(res.recognizedWords, _selectedAccentMode);
                                });
                              },
                            );
                          }
                        },
                        icon: Icon(isDictating ? Icons.graphic_eq : Icons.mic, size: 14),
                        label: Text(isDictating ? 'Listening...' : 'Dictate', style: const TextStyle(fontSize: 11)),
                      ),
                    ],
                  ),
                  const SizedBox(height: 6),
                  TextField(
                    controller: noteController,
                    maxLines: 2,
                    decoration: const InputDecoration(
                      hintText: 'Speak or type note for this photo...',
                      filled: true,
                      fillColor: Color(0xFF0F172A),
                    ),
                  ),
                ],
              ),
            ),
            actions: [
              TextButton(onPressed: () => Navigator.pop(ctx, ''), child: const Text('Skip')),
              ElevatedButton(
                style: ElevatedButton.styleFrom(backgroundColor: const Color(0xFF0284C7)),
                onPressed: () => Navigator.pop(ctx, noteController.text.trim()),
                child: const Text('Save Note'),
              ),
            ],
          );
        },
      ),
    );
  }

  Future<void> _exportPackage() async {
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('📦 Bundling *.scoutpkg archive...')),
    );
    try {
      final pkgFile = await PackageService.createScoutingPackage(
        projectId: _projectId,
        crewName: _crewName,
        scoutName: _scoutName,
        thoughts: _thoughts,
        waypoints: _waypoints,
        photos: _photos,
        trackPoints: _trackPoints,
      );
      await PackageService.sharePackage(pkgFile);
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Export error: $e')));
    }
  }

  void _toggleDrawer() {
    setState(() {
      _isDrawerOpen = !_isDrawerOpen;
      if (_isDrawerOpen) {
        _drawerAnimController.forward();
      } else {
        _drawerAnimController.reverse();
      }
    });
  }

  /* --------------------------------------------------------------------------
     4. QFIELD GIS CANVAS BUILD
     -------------------------------------------------------------------------- */
  @override
  Widget build(BuildContext context) {
    final screenHeight = MediaQuery.of(context).size.height;

    return Scaffold(
      body: Stack(
        children: [
          // FULL SCREEN MAP
          FlutterMap(
            mapController: _mapController,
            options: MapOptions(
              initialCenter: _mapCenter,
              initialZoom: 13.0,
              onPositionChanged: (pos, _) {
                if (pos.center != null) _mapCenter = pos.center!;
              },
            ),
            children: [
              TileLayer(
                urlTemplate: _activeLayerIndex == 0
                    ? 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}'
                    : 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
                userAgentPackageName: 'com.quikfieldnotes.app',
              ),
              if (_trackPoints.isNotEmpty)
                PolylineLayer(
                  polylines: [
                    Polyline(
                      points: _trackPoints.map((pt) => LatLng(pt['lat'], pt['lon'])).toList(),
                      strokeWidth: 4.0,
                      color: const Color(0xFFEF4444),
                    ),
                  ],
                ),
              MarkerLayer(
                markers: [
                  if (_currentPosition != null)
                    Marker(
                      point: LatLng(_currentPosition!.latitude, _currentPosition!.longitude),
                      width: 22,
                      height: 22,
                      child: Container(
                        decoration: BoxDecoration(
                          shape: BoxShape.circle,
                          color: const Color(0xFF00F0FF),
                          border: Border.all(color: Colors.white, width: 3),
                          boxShadow: const [BoxShadow(color: Color(0xFF00F0FF), blurRadius: 10)],
                        ),
                      ),
                    ),
                  ..._waypoints.map(
                    (wp) => Marker(
                      point: LatLng(wp.latitude, wp.longitude),
                      width: 32,
                      height: 32,
                      child: const Icon(Icons.location_pin, color: Color(0xFFF59E0B), size: 32),
                    ),
                  ),
                ],
              ),
            ],
          ),

          // QFIELD CENTER CROSSHAIR RETICLE
          Center(
            child: SizedBox(
              width: 36,
              height: 36,
              child: Stack(
                alignment: Alignment.center,
                children: [
                  Container(width: 28, height: 2, color: const Color(0xFF00F0FF)),
                  Container(width: 2, height: 28, color: const Color(0xFF00F0FF)),
                  Container(
                    width: 6,
                    height: 6,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      color: Colors.white,
                      border: Border.all(color: const Color(0xFF00F0FF), width: 1.5),
                    ),
                  ),
                ],
              ),
            ),
          ),

          // TOP FLOATING HUD
          SafeArea(
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
              child: Row(
                children: [
                  // Project Pill
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                    decoration: BoxDecoration(
                      color: const Color(0xEA1E293B),
                      borderRadius: BorderRadius.circular(14),
                      border: Border.all(color: Colors.lightBlueAccent.withOpacity(0.3)),
                    ),
                    child: Row(
                      children: [
                        Container(
                          width: 8,
                          height: 8,
                          decoration: const BoxDecoration(shape: BoxShape.circle, color: Color(0xFF10B981)),
                        ),
                        const SizedBox(width: 8),
                        Text(_projectId, style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 13)),
                        const SizedBox(width: 8),
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                          decoration: BoxDecoration(
                            color: const Color(0xFF0284C7).withOpacity(0.3),
                            borderRadius: BorderRadius.circular(8),
                          ),
                          child: Text(
                            'GNSS: ±${_currentPosition?.accuracy.round() ?? '--'}m',
                            style: const TextStyle(fontSize: 10, color: Color(0xFF38BDF8), fontWeight: FontWeight.bold),
                          ),
                        ),
                      ],
                    ),
                  ),
                  const Spacer(),
                  // Tracking Toggle
                  ElevatedButton.icon(
                    style: ElevatedButton.styleFrom(
                      backgroundColor: _isTracking ? const Color(0xFFEF4444) : const Color(0xFF10B981),
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
                      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                    ),
                    onPressed: _toggleTracking,
                    icon: Icon(_isTracking ? Icons.stop : Icons.fiber_manual_record, size: 14),
                    label: Text(_isTracking ? 'Stop' : 'Track', style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 12)),
                  ),
                ],
              ),
            ),
          ),

          // FLOATING SIDE ACTION DOCK (QField Style)
          Positioned(
            right: 12,
            top: screenHeight * 0.28,
            child: Column(
              children: [
                _buildDockButton(icon: Icons.my_location, onTap: _centerOnGps, tooltip: 'Center GNSS'),
                const SizedBox(height: 12),
                // Hero Voice Button
                GestureDetector(
                  onTap: _toggleSpeech,
                  child: Container(
                    width: 58,
                    height: 58,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      gradient: LinearGradient(
                        colors: _isListening
                            ? [const Color(0xFFEF4444), const Color(0xFFB91C1C)]
                            : [const Color(0xFF0284C7), const Color(0xFF0369A1)],
                      ),
                      border: Border.all(color: _isListening ? const Color(0xFFF87171) : const Color(0xFF38BDF8), width: 2),
                      boxShadow: [
                        BoxShadow(
                          color: _isListening ? const Color(0xAAEF4444) : const Color(0x6638BDF8),
                          blurRadius: 18,
                          spreadRadius: 2,
                        ),
                      ],
                    ),
                    child: Icon(_isListening ? Icons.graphic_eq : Icons.mic, color: Colors.white, size: 28),
                  ),
                ),
                const SizedBox(height: 12),
                _buildDockButton(icon: Icons.add_location_alt, onTap: _openQuickWaypointModal, tooltip: 'Add Waypoint'),
                const SizedBox(height: 12),
                _buildDockButton(icon: Icons.camera_alt, onTap: _capturePhoto, tooltip: 'Geotagged Camera'),
                const SizedBox(height: 12),
                _buildDockButton(icon: Icons.layers, onTap: _toggleMapLayer, tooltip: 'Switch Map'),
                const SizedBox(height: 12),
                _buildDockButton(icon: Icons.folder, onTap: _toggleDrawer, tooltip: 'Field Journal'),
              ],
            ),
          ),

          // BOTTOM SLIDING DRAWER / JOURNAL PANEL
          AnimatedPositioned(
            duration: const Duration(milliseconds: 280),
            curve: Curves.easeOutCubic,
            left: 0,
            right: 0,
            bottom: _isDrawerOpen ? 0 : -(screenHeight * 0.65 - 58),
            height: screenHeight * 0.65,
            child: Container(
              decoration: BoxDecoration(
                color: const Color(0xF01E293B),
                borderRadius: const BorderRadius.vertical(top: Radius.circular(20)),
                border: Border.all(color: Colors.lightBlueAccent.withOpacity(0.25)),
                boxShadow: const [BoxShadow(color: Colors.black54, blurRadius: 25)],
              ),
              child: Column(
                children: [
                  // Handle & Header
                  GestureDetector(
                    onTap: _toggleDrawer,
                    child: Container(
                      width: double.infinity,
                      padding: const EdgeInsets.symmetric(vertical: 8),
                      child: Column(
                        children: [
                          Container(width: 40, height: 4, decoration: BoxDecoration(color: Colors.grey, borderRadius: BorderRadius.circular(2))),
                          const SizedBox(height: 4),
                          Padding(
                            padding: const EdgeInsets.symmetric(horizontal: 16),
                            child: Row(
                              mainAxisAlignment: MainAxisAlignment.spaceBetween,
                              children: [
                                Row(
                                  children: [
                                    const Text('⚡ Field Journal & Voice Feed', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 13)),
                                    const SizedBox(width: 8),
                                    Container(
                                      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 1),
                                      decoration: BoxDecoration(color: const Color(0xFF0284C7), borderRadius: BorderRadius.circular(10)),
                                      child: Text('${_thoughts.length}', style: const TextStyle(fontSize: 10, fontWeight: FontWeight.bold)),
                                    ),
                                  ],
                                ),
                                Text(_isDrawerOpen ? '▼ Close' : '▲ Pull Up', style: const TextStyle(fontSize: 11, color: Color(0xFF38BDF8), fontWeight: FontWeight.bold)),
                              ],
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),

                  // Drawer Body
                  Expanded(
                    child: SingleChildScrollView(
                      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          // Fast & Furious Voice Box
                          Container(
                            padding: const EdgeInsets.all(12),
                            decoration: BoxDecoration(
                              color: const Color(0xFF0F172A),
                              borderRadius: BorderRadius.circular(12),
                              border: Border.all(color: const Color(0xFF334155)),
                            ),
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Row(
                                  children: [
                                    const Text('🎙️ Accent / Language:', style: TextStyle(fontSize: 11, color: Color(0xFF38BDF8), fontWeight: FontWeight.bold)),
                                    const Spacer(),
                                    DropdownButton<String>(
                                      value: _selectedAccentMode,
                                      dropdownColor: const Color(0xFF0F172A),
                                      underline: const SizedBox(),
                                      style: const TextStyle(fontSize: 11, color: Color(0xFF38BDF8), fontWeight: FontWeight.bold),
                                      items: _accentOptions.map((opt) => DropdownMenuItem(value: opt['code'], child: Text(opt['label']!))).toList(),
                                      onChanged: (val) {
                                        if (val != null) setState(() => _selectedAccentMode = val);
                                      },
                                    ),
                                  ],
                                ),
                                const SizedBox(height: 8),
                                TextField(
                                  controller: _voiceTextController,
                                  maxLines: 3,
                                  decoration: InputDecoration(
                                    hintText: 'Speak in Arab/Asian English, Roman Urdu, or Roman Arabic...',
                                    hintStyle: const TextStyle(fontSize: 12, color: Colors.grey),
                                    filled: true,
                                    fillColor: const Color(0xFF0A0F1D),
                                    border: OutlineInputBorder(borderRadius: BorderRadius.circular(8), borderSide: BorderSide.none),
                                  ),
                                ),
                                const SizedBox(height: 8),
                                Row(
                                  children: [
                                    ElevatedButton(
                                      style: ElevatedButton.styleFrom(backgroundColor: const Color(0xFF0284C7)),
                                      onPressed: _saveThought,
                                      child: const Text('💾 Save Thought', style: TextStyle(fontSize: 12, fontWeight: FontWeight.bold)),
                                    ),
                                    const Spacer(),
                                    OutlinedButton.icon(
                                      onPressed: _exportPackage,
                                      icon: const Icon(Icons.share, size: 14),
                                      label: const Text('Export .scoutpkg', style: TextStyle(fontSize: 11)),
                                    ),
                                  ],
                                ),
                              ],
                            ),
                          ),

                          const SizedBox(height: 14),
                          const Text('📋 Daily Observations Timeline', style: TextStyle(fontSize: 13, fontWeight: FontWeight.bold)),
                          const SizedBox(height: 8),

                          if (_thoughts.isEmpty)
                            const Center(child: Padding(padding: EdgeInsets.all(16), child: Text('No observations recorded yet. Tap 🎙️ to speak.', style: TextStyle(fontSize: 12, color: Colors.grey))))
                          else
                            ..._thoughts.map((t) => Container(
                              margin: const EdgeInsets.only(bottom: 8),
                              padding: const EdgeInsets.all(10),
                              decoration: const BoxDecoration(
                                color: Color(0xFF0F172A),
                                border: Border(left: BorderSide(color: Color(0xFF38BDF8), width: 3)),
                                borderRadius: BorderRadius.horizontal(right: Radius.circular(8)),
                              ),
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Row(
                                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                                    children: [
                                      Text('🕒 ${t.timestamp}', style: const TextStyle(fontSize: 10, color: Colors.grey)),
                                      Container(
                                        padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 1),
                                        decoration: BoxDecoration(color: const Color(0xFF0284C7), borderRadius: BorderRadius.circular(6)),
                                        child: Text(t.categoryName, style: const TextStyle(fontSize: 9, fontWeight: FontWeight.bold)),
                                      ),
                                    ],
                                  ),
                                  const SizedBox(height: 4),
                                  Text(t.text, style: const TextStyle(fontSize: 12)),
                                ],
                              ),
                            )),
                        ],
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildDockButton({required IconData icon, required VoidCallback onTap, required String tooltip}) {
    return Container(
      width: 48,
      height: 48,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        color: const Color(0xEA1E293B),
        border: Border.all(color: Colors.lightBlueAccent.withOpacity(0.3), width: 1.5),
        boxShadow: const [BoxShadow(color: Colors.black45, blurRadius: 10)],
      ),
      child: IconButton(
        icon: Icon(icon, color: const Color(0xFF38BDF8), size: 22),
        onPressed: onTap,
        tooltip: tooltip,
      ),
    );
  }
}
