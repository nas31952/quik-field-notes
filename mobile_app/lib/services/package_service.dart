/// Package Exporter Service for Quik Field Notesing App
/// Bundles photos, GPX tracks, waypoints, and thoughts into portable *.scoutpkg
import 'dart:io';
import 'dart:convert';
import 'package:archive/archive.dart';
import 'package:archive/archive_io.dart';
import 'package:path_provider/path_provider.dart';
import 'package:share_plus/share_plus.dart';
import '../models/scout_models.dart';

class PackageService {
  static Future<File> createScoutingPackage({
    required String projectId,
    required String crewName,
    required String scoutName,
    required List<JournalThought> thoughts,
    required List<WaypointItem> waypoints,
    required List<ScoutPhotoItem> photos,
    required List<Map<String, dynamic>> trackPoints,
  }) async {
    final archive = Archive();

    // 1. Manifest
    final manifest = {
      'package_version': '2.0',
      'project_id': projectId,
      'crew_name': crewName,
      'scout_name': scoutName,
      'export_timestamp': DateTime.now().toIso8601String(),
      'summary': {
        'photo_count': photos.length,
        'waypoint_count': waypoints.length,
        'journal_count': thoughts.length,
        'track_points_count': trackPoints.length,
      }
    };
    final manifestBytes = utf8.encode(jsonEncode(manifest));
    archive.addFile(ArchiveFile('manifest.json', manifestBytes.length, manifestBytes));

    // 2. Journal Entries
    final journalData = {
      'project_id': projectId,
      'entries': thoughts.map((t) => t.toJson()).toList(),
    };
    final journalBytes = utf8.encode(jsonEncode(journalData));
    archive.addFile(ArchiveFile('journal.json', journalBytes.length, journalBytes));

    // 3. Waypoints
    final wpsData = waypoints.map((w) => w.toJson()).toList();
    final wpsBytes = utf8.encode(jsonEncode(wpsData));
    archive.addFile(ArchiveFile('waypoints.json', wpsBytes.length, wpsBytes));

    // 4. Track GPX
    final gpxBuffer = StringBuffer();
    gpxBuffer.writeln('<?xml version="1.0" encoding="UTF-8"?>');
    gpxBuffer.writeln('<gpx version="1.1" creator="Quik Field Notes" xmlns="http://www.topografix.com/GPX/1/1">');
    gpxBuffer.writeln('  <trk><name>$projectId Scout Track</name><trkseg>');
    for (final pt in trackPoints) {
      gpxBuffer.writeln('    <trkpt lat="${pt['lat']}" lon="${pt['lon']}"><time>${pt['time']}</time></trkpt>');
    }
    gpxBuffer.writeln('  </trkseg></trk>');
    gpxBuffer.writeln('</gpx>');
    final gpxBytes = utf8.encode(gpxBuffer.toString());
    archive.addFile(ArchiveFile('track.gpx', gpxBytes.length, gpxBytes));

    // 5. Photos and photos.json
    final photosMeta = photos.map((p) => p.toJson()).toList();
    final photosMetaBytes = utf8.encode(jsonEncode(photosMeta));
    archive.addFile(ArchiveFile('photos.json', photosMetaBytes.length, photosMetaBytes));

    for (final p in photos) {
      final photoFile = File(p.filePath);
      if (await photoFile.exists()) {
        final photoBytes = await photoFile.readAsBytes();
        archive.addFile(ArchiveFile('photos/${p.filename}', photoBytes.length, photoBytes));
      }
    }

    // Zip encode
    final encoder = ZipEncoder();
    final zipData = encoder.encode(archive);

    final tempDir = await getTemporaryDirectory();
    final safeName = projectId.replaceAll(RegExp(r'[^a-zA-Z0-9_\-]'), '_');
    final dateStr = DateTime.now().toIso8601String().substring(0, 10);
    final outFile = File('${tempDir.path}/${safeName}_Scouting_Package_$dateStr.scoutpkg');
    await outFile.writeAsBytes(zipData!);

    return outFile;
  }

  static Future<void> sharePackage(File packageFile) async {
    await Share.shareXFiles(
      [XFile(packageFile.path)],
      text: 'Field Scouting Package (*.scoutpkg) for Desktop Suite Import',
    );
  }
}

