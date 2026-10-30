package com.saphid.framecontrol.core

import java.io.ByteArrayOutputStream
import java.util.Base64
import org.junit.Assert.*
import org.junit.Test

class SaveTransferTest {
    @Test fun chunkedTransferKeepsByteIntegrityAndCommitsOnlyAfterCompletion() {
        val bytes = ByteArray(SaveTransfer.CHUNK * 3 + 71) { (it % 251).toByte() }
        val out = ByteArrayOutputStream()
        var committed = false
        var discarded = false
        val t = SaveTransfer(out, bytes.size.toLong(), { committed = true }, { discarded = true })
        bytes.asList().chunked(SaveTransfer.CHUNK).forEachIndexed { i, chunk ->
            t.append(i.toLong() * SaveTransfer.CHUNK, Base64.getEncoder().encodeToString(chunk.toByteArray()))
            assertFalse(committed)
        }
        t.finish()
        t.close()
        assertTrue(committed)
        assertFalse(discarded)
        assertArrayEquals(bytes, out.toByteArray())
    }

    @Test fun incompleteOrOutOfOrderSaveNeverCommitsAndDiscardsOnce() {
        for (wrongOrder in listOf(false, true)) {
            var committed = false
            var discarded = 0
            val t = SaveTransfer(ByteArrayOutputStream(), 12, { committed = true }, { discarded++ })
            assertTrue(runCatching {
                t.append(if (wrongOrder) 1 else 0, byteArrayOf(1, 2, 3))
                t.finish()
            }.isFailure)
            t.close()
            assertFalse(committed)
            assertEquals(1, discarded)
        }
    }

    @Test fun encodedChunksAreBoundedBeforeDecodeAndSizeCannotOverrun() {
        for (tooLarge in listOf(false, true)) {
            var discarded = false
            val t = SaveTransfer(ByteArrayOutputStream(), 2, {}, { discarded = true })
            assertTrue(runCatching {
                if (tooLarge) t.append(0, "A".repeat(SaveTransfer.CHUNK * 2)) else t.append(0, byteArrayOf(1, 2, 3))
            }.isFailure)
            assertTrue(discarded)
        }
    }
}
