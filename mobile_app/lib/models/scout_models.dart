/// Data models for the Quik Field Notes
import 'dart:convert';

class JournalThought {
  final String id;
  final String timestamp;
  String text;
  final double? latitude;
  final double? longitude;
  String sectionId;
  String categoryName;

  JournalThought({
    required this.id,
    required this.timestamp,
    required this.text,
    this.latitude,
    this.longitude,
    this.sectionId = 'sec_01_overview',
    this.categoryName = 'Overview',
  });

  Map<String, dynamic> toJson() => {
    'entry_id': id,
    'timestamp': timestamp,
    'text': text,
    'lat': latitude,
    'lon': longitude,
    'section_id': sectionId,
    'category_name': categoryName,
    'source_type': 'mobile_speech_to_text',
  };

  factory JournalThought.fromJson(Map<String, dynamic> json) => JournalThought(
    id: json['entry_id'] ?? '',
    timestamp: json['timestamp'] ?? '',
    text: json['text'] ?? '',
    latitude: json['lat']?.toDouble(),
    longitude: json['lon']?.toDouble(),
    sectionId: json['section_id'] ?? 'sec_01_overview',
    categoryName: json['category_name'] ?? 'Overview',
  );
}

class WaypointItem {
  final String name;
  String note;
  final double latitude;
  final double longitude;
  final double elevation;
  final String timestamp;

  WaypointItem({
    required this.name,
    required this.note,
    required this.latitude,
    required this.longitude,
    this.elevation = 0.0,
    required this.timestamp,
  });

  Map<String, dynamic> toJson() => {
    'name': name,
    'note': note,
    'lat': latitude,
    'lon': longitude,
    'elevation': elevation,
    'time': timestamp,
  };
}

class ScoutPhotoItem {
  final String filePath;
  final String filename;
  String caption;
  String note;
  final double? latitude;
  final double? longitude;
  final String timestamp;

  ScoutPhotoItem({
    required this.filePath,
    required this.filename,
    this.caption = '',
    this.note = '',
    this.latitude,
    this.longitude,
    required this.timestamp,
  });

  Map<String, dynamic> toJson() => {
    'filename': filename,
    'caption': caption,
    'note': note,
    'lat': latitude,
    'lon': longitude,
    'has_gps': latitude != null && longitude != null,
    'timestamp': timestamp,
  };
}

