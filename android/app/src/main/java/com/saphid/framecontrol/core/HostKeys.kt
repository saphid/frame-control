package com.saphid.framecontrol.core

import com.jcraft.jsch.HostKey
import com.jcraft.jsch.HostKeyRepository
import com.jcraft.jsch.UserInfo
import java.nio.ByteBuffer
import java.security.MessageDigest
import java.util.Base64
import java.util.concurrent.atomic.AtomicReference

/** A host key as the Frame presented it: the SSH public-key blob and the type named inside it. */
class FrameHostKey private constructor(val type: String, private val blob: ByteArray) {
    val bytes: ByteArray get() = blob.copyOf()

    /** OpenSSH's form, as `ssh-keygen -lf` and the first-connection prompt show it. */
    val fingerprint: String
        get() = "SHA256:" + Base64.getEncoder().withoutPadding().encodeToString(MessageDigest.getInstance("SHA-256").digest(blob))

    /** "type base64", as in known_hosts. */
    fun encode(): String = "$type ${Base64.getEncoder().encodeToString(blob)}"

    override fun equals(other: Any?) = other is FrameHostKey && type == other.type && blob.contentEquals(other.blob)
    override fun hashCode() = blob.contentHashCode()
    override fun toString() = "$type $fingerprint"

    companion object {
        fun fromBlob(blob: ByteArray): FrameHostKey? {
            if (blob.size < 4) return null
            val buf = ByteBuffer.wrap(blob)
            val len = buf.int
            if (len <= 0 || len > 64 || len > buf.remaining()) return null
            val type = String(blob, 4, len, Charsets.US_ASCII)
            if (!type.all { it.isLetterOrDigit() || it in "-@._" }) return null
            return FrameHostKey(type, blob.copyOf())
        }

        fun decode(text: String?): FrameHostKey? {
            val parts = text?.trim()?.split(' ') ?: return null
            if (parts.size != 2) return null
            val blob = runCatching { Base64.getDecoder().decode(parts[1]) }.getOrNull() ?: return null
            return fromBlob(blob)?.takeIf { it.type == parts[0] }
        }
    }
}

/** What the user is asked before anything (a password included) goes to a Frame not seen before. */
data class HostKeyQuestion(
    val settings: FrameSettings,
    val key: FrameHostKey,
    /** The key this app trusted for the Frame before, when the new one is different. */
    val previous: FrameHostKey?,
)

/**
 * The app's only host key check. With a pinned key, that key and nothing else is accepted
 * (ssh's StrictHostKeyChecking=yes, and there is no "accept the new key" path: the user has
 * to pair again). Without one, `confirm` must say yes to the exact fingerprint first.
 * Called by JSch during key exchange, before authentication starts.
 */
class HostKeyGate(
    private val settings: FrameSettings,
    private val pinned: FrameHostKey?,
    private val previous: FrameHostKey?,
    private val confirm: (HostKeyQuestion) -> Boolean,
) : HostKeyRepository {
    enum class Outcome { NONE, MATCHED, CONFIRMED, DECLINED, CHANGED }

    private val _seen = AtomicReference<FrameHostKey?>()
    private val _outcome = AtomicReference(Outcome.NONE)
    val seen: FrameHostKey? get() = _seen.get()
    val outcome: Outcome get() = _outcome.get()

    override fun check(host: String?, key: ByteArray?): Int {
        val presented = key?.let(FrameHostKey::fromBlob)
        if (presented == null) {
            _outcome.set(Outcome.DECLINED)
            return HostKeyRepository.NOT_INCLUDED
        }
        _seen.set(presented)
        if (pinned != null) {
            val same = presented == pinned
            _outcome.set(if (same) Outcome.MATCHED else Outcome.CHANGED)
            return if (same) HostKeyRepository.OK else HostKeyRepository.CHANGED
        }
        val yes = runCatching { confirm(HostKeyQuestion(settings, presented, previous?.takeIf { it != presented })) }.getOrDefault(false)
        _outcome.set(if (yes) Outcome.CONFIRMED else Outcome.DECLINED)
        return if (yes) HostKeyRepository.OK else HostKeyRepository.NOT_INCLUDED
    }

    // The controller saves a confirmed key itself, after the whole pairing has worked.
    override fun add(hostkey: HostKey?, ui: UserInfo?) {}
    override fun remove(host: String?, type: String?) {}
    override fun remove(host: String?, type: String?, key: ByteArray?) {}
    override fun getKnownHostsRepositoryID() = "Frame Control"
    override fun getHostKey(): Array<HostKey> = emptyArray()
    override fun getHostKey(host: String?, type: String?): Array<HostKey> = emptyArray()
}
