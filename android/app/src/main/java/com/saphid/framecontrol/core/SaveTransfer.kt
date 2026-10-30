package com.saphid.framecontrol.core

import java.io.Closeable
import java.io.OutputStream
import java.util.Base64

/** One sequential transfer. A failed/interrupted write removes its incomplete destination. */
class SaveTransfer(
    private val output: OutputStream,
    private val expected: Long,
    private val commit: () -> Unit,
    private val discard: () -> Unit,
) : Closeable {
    companion object {
        const val CHUNK = 192 * 1024
        const val MAX_SIZE = 2L * 1024 * 1024 * 1024
    }
    private var written = 0L
    private var done = false
    init { require(expected in -1..MAX_SIZE) }

    @Synchronized fun append(offset: Long, encoded: String) {
        check(!done) { "Save closed" }
        try {
            require(offset == written) { "Out-of-order save chunk" }
            require(encoded.length <= ((CHUNK + 2) / 3) * 4) { "Save chunk too large" }
            append(offset, Base64.getDecoder().decode(encoded))
        } catch (e: Exception) { close(); throw e }
    }

    @Synchronized fun append(offset: Long, bytes: ByteArray) {
        check(!done) { "Save closed" }
        try {
            require(offset == written && bytes.size <= CHUNK && written + bytes.size <= MAX_SIZE &&
                (expected < 0 || written + bytes.size <= expected)) { "Unexpected save size or order" }
            output.write(bytes)
            written += bytes.size
        } catch (e: Exception) { close(); throw e }
    }

    @Synchronized fun finish() {
        check(!done) { "Save closed" }
        try {
            check(expected < 0 || written == expected) { "Save interrupted ($written of $expected bytes)" }
            output.close()
            commit()
            done = true
        } finally { if (!done) close() }
    }

    @Synchronized override fun close() {
        if (done) return
        done = true
        runCatching { output.close() }
        runCatching { discard() }
    }
}
