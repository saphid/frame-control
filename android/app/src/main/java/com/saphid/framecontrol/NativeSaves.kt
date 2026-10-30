package com.saphid.framecontrol

import android.content.ContentValues
import android.net.Uri
import android.os.Environment
import android.provider.MediaStore
import android.provider.DocumentsContract
import com.saphid.framecontrol.core.SaveTransfer
import java.io.Closeable
import java.util.Base64
import java.util.UUID

/** At most one save, with small acknowledged chunks instead of whole-library base64. */
class NativeSaves(private val activity: MainActivity) : Closeable {
    private var transfer: SaveTransfer? = null
    private var token: String? = null
    private var closed = false
    val active: Boolean @Synchronized get() = transfer != null

    companion object {
        fun discardDocument(activity: MainActivity, uri: Uri) = runCatching {
            DocumentsContract.deleteDocument(activity.contentResolver, uri)
        }.getOrDefault(false)

        fun safeName(raw: String) = raw.substringAfterLast('/').substringAfterLast('\\')
            .replace(Regex("[\\p{Cntrl}/\\\\]"), "-").take(120).ifBlank { "Frame download" }

        fun imageType(b: ByteArray): Pair<String, String>? = when {
            b.size >= 8 && b.copyOfRange(0, 8).contentEquals(byteArrayOf(0x89.toByte(), 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a)) -> "image/png" to "png"
            b.size >= 3 && b[0] == 0xff.toByte() && b[1] == 0xd8.toByte() && b[2] == 0xff.toByte() -> "image/jpeg" to "jpg"
            b.size >= 12 && String(b, 0, 4, Charsets.US_ASCII) == "RIFF" && String(b, 8, 4, Charsets.US_ASCII) == "WEBP" -> "image/webp" to "webp"
            else -> null
        }
    }

    @Synchronized fun beginImage(name: String, size: Long, head: String): String {
        check(!closed && transfer == null) { "Another save is active" }
        require(size in 1..64L * 1024 * 1024 && head.length <= 64) { "Image too large or empty" }
        val (mime, ext) = imageType(Base64.getDecoder().decode(head)) ?: error("Not a PNG, JPEG or WebP image")
        val values = ContentValues().apply {
            put(MediaStore.Images.Media.DISPLAY_NAME, safeName(name).substringBeforeLast('.') + ".$ext")
            put(MediaStore.Images.Media.MIME_TYPE, mime)
            put(MediaStore.Images.Media.RELATIVE_PATH, "${Environment.DIRECTORY_PICTURES}/Frame Control")
            put(MediaStore.Images.Media.IS_PENDING, 1)
        }
        val uri = activity.contentResolver.insert(MediaStore.Images.Media.getContentUri(MediaStore.VOLUME_EXTERNAL_PRIMARY), values)
            ?: error("Couldn't create image")
        return begin(uri, size, image = true)
    }

    @Synchronized fun beginDocument(uri: Uri, size: Long): String = begin(uri, size, image = false)

    private fun begin(uri: Uri, size: Long, image: Boolean): String {
        val resolver = activity.contentResolver
        try {
            check(!closed && transfer == null) { "Save no longer available" }
            require(size in -1..SaveTransfer.MAX_SIZE) { "File too large" }
            val output = resolver.openOutputStream(uri, "wt") ?: error("Couldn't open destination")
            val id = UUID.randomUUID().toString()
            transfer = SaveTransfer(output, size, commit = {
                if (image) check(resolver.update(uri, ContentValues().apply { put(MediaStore.Images.Media.IS_PENDING, 0) }, null, null) > 0) { "Couldn't publish image" }
            }, discard = { if (image) resolver.delete(uri, null, null) else discardDocument(activity, uri) })
            token = id
            return id
        } catch (e: Exception) {
            if (image) runCatching { resolver.delete(uri, null, null) } else discardDocument(activity, uri)
            throw e
        }
    }

    @Synchronized fun append(id: String, offset: Long, data: String) = current(id).append(offset, data)
    @Synchronized fun append(id: String, offset: Long, data: ByteArray) = current(id).append(offset, data)
    @Synchronized fun finish(id: String) {
        val current = current(id)
        try { current.finish() } finally { transfer = null; token = null }
    }
    @Synchronized fun abort(id: String) {
        if (id == token) { transfer?.close(); transfer = null; token = null }
    }
    private fun current(id: String): SaveTransfer {
        check(token == id) { "Stale save" }
        return transfer ?: error("No save is active")
    }
    @Synchronized override fun close() { closed = true; transfer?.close(); transfer = null; token = null }
}
