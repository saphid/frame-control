package com.saphid.framecontrol.core

import com.sun.net.httpserver.HttpServer
import java.io.ByteArrayOutputStream
import java.net.InetSocketAddress
import org.junit.Assert.*
import org.junit.Test

class TunnelDownloadTest {
    @Test fun downloadsBytesWithTheSessionHeaderAndAllowsOnlySameOriginRedirects() {
        val server = HttpServer.create(InetSocketAddress("127.0.0.1", 0), 0)
        val other = HttpServer.create(InetSocketAddress("127.0.0.1", 0), 0)
        var leaked = false
        var authorized = false
        val data = ByteArray(512 * 1024 + 3) { (it % 255).toByte() }
        server.createContext("/file") { e ->
            authorized = e.requestHeaders.getFirst("X-Frame-UI") == "test-session"
            e.sendResponseHeaders(if (authorized) 200 else 403, data.size.toLong())
            e.responseBody.use { it.write(data) }
        }
        server.createContext("/same") { e -> e.responseHeaders.add("Location", "/file"); e.sendResponseHeaders(302, -1); e.close() }
        server.createContext("/escape") { e -> e.responseHeaders.add("Location", "http://127.0.0.1:${other.address.port}/stolen"); e.sendResponseHeaders(302, -1); e.close() }
        other.createContext("/stolen") { e -> leaked = true; e.sendResponseHeaders(200, -1); e.close() }
        server.start(); other.start()
        try {
            val policy = OriginPolicy(server.address.port)
            val out = ByteArrayOutputStream()
            TunnelDownload.copy("${policy.origin}/same", policy, "test-session", { true }) { offset, bytes ->
                assertEquals(out.size().toLong(), offset)
                out.write(bytes)
            }
            assertTrue(authorized)
            assertArrayEquals(data, out.toByteArray())
            assertTrue(runCatching {
                TunnelDownload.copy("${policy.origin}/escape", policy, "test-session", { true }) { _, _ -> fail("escaped download") }
            }.isFailure)
            assertFalse("No request or key reaches the other origin", leaked)
        } finally { server.stop(0); other.stop(0) }
    }
}
