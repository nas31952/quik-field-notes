package com.quikfieldnotes.app

import android.content.ContentValues
import android.media.MediaScannerConnection
import android.os.Build
import android.os.Environment
import android.provider.MediaStore
import android.util.Base64
import android.view.WindowManager
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel
import java.io.File
import java.io.FileOutputStream

class MainActivity : FlutterActivity() {
    private val channelName = "com.quikfieldnotes.app/native"

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, channelName).setMethodCallHandler { call, result ->
            when (call.method) {
                "saveFileToDownloads" -> {
                    val filename = call.argument<String>("filename") ?: "export.dat"
                    val mimeType = call.argument<String>("mimeType") ?: "application/octet-stream"
                    val base64Data = call.argument<String>("base64Data") ?: ""
                    try {
                        val bytes = Base64.decode(base64Data, Base64.DEFAULT)
                        val savedPath = saveToDownloads(filename, mimeType, bytes)
                        result.success(savedPath)
                    } catch (e: Exception) {
                        result.error("SAVE_FAILED", e.message, null)
                    }
                }
                "setKeepScreenOn" -> {
                    val enabled = call.argument<Boolean>("enabled") ?: true
                    runOnUiThread {
                        if (enabled) {
                            window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
                        } else {
                            window.clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
                        }
                    }
                    result.success(enabled)
                }
                else -> result.notImplemented()
            }
        }
    }

    private fun saveToDownloads(filename: String, mimeType: String, bytes: ByteArray): String {
        val safeName = filename.replace(Regex("[^a-zA-Z0-9._-]"), "_")
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            val values = ContentValues().apply {
                put(MediaStore.Downloads.DISPLAY_NAME, safeName)
                put(MediaStore.Downloads.MIME_TYPE, mimeType)
                put(MediaStore.Downloads.RELATIVE_PATH, Environment.DIRECTORY_DOWNLOADS + "/QuikFieldNotes")
            }
            val resolver = applicationContext.contentResolver
            val uri = resolver.insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, values)
                ?: throw IllegalStateException("Unable to create download entry")
            resolver.openOutputStream(uri)?.use { out ->
                out.write(bytes)
            } ?: throw IllegalStateException("Unable to open download output stream")
            return "Downloads/QuikFieldNotes/$safeName"
        } else {
            @Suppress("DEPRECATION")
            val dir = File(Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DOWNLOADS), "QuikFieldNotes")
            if (!dir.exists()) dir.mkdirs()
            val outFile = File(dir, safeName)
            FileOutputStream(outFile).use { it.write(bytes) }
            MediaScannerConnection.scanFile(
                applicationContext,
                arrayOf(outFile.absolutePath),
                arrayOf(mimeType),
                null
            )
            return outFile.absolutePath
        }
    }
}
