package com.saphid.framecontrol.core

import com.jcraft.jsch.Identity
import java.io.ByteArrayOutputStream
import java.math.BigInteger
import java.security.interfaces.ECPublicKey
import java.util.Base64

/**
 * This phone's SSH key, ECDSA P-256. On the phone it lives in the Android Keystore
 * (KeystoreSigner) and never leaves it: only the public key and signatures come out.
 */
interface SshSigner {
    val publicKey: ECPublicKey

    /** An ASN.1 DER SHA256withECDSA signature over data. */
    fun sign(data: ByteArray): ByteArray
}

object SshWire {
    const val ALGORITHM = "ecdsa-sha2-nistp256"
    private const val CURVE = "nistp256"

    /** The public key in SSH's wire form (RFC 5656 section 3.1). */
    fun publicKeyBlob(key: ECPublicKey): ByteArray {
        val point = ByteArray(65)
        point[0] = 4  // uncompressed
        unsigned(key.w.affineX, 32).copyInto(point, 1)
        unsigned(key.w.affineY, 32).copyInto(point, 33)
        return strings(ALGORITHM.toByteArray(), CURVE.toByteArray(), point)
    }

    /** "ecdsa-sha2-nistp256 AAAA… comment", the line for ~/.ssh/authorized_keys. */
    fun authorizedKeysLine(key: ECPublicKey, comment: String): String =
        "$ALGORITHM ${Base64.getEncoder().encodeToString(publicKeyBlob(key))} $comment"

    /** A DER ECDSA signature as SSH sends it: the algorithm, then mpint r and mpint s. */
    fun signature(der: ByteArray): ByteArray {
        val (r, s) = derToRS(der)
        val inner = ByteArrayOutputStream()
        inner.writeString(r.toByteArray())
        inner.writeString(s.toByteArray())
        return strings(ALGORITHM.toByteArray(), inner.toByteArray())
    }

    fun derToRS(der: ByteArray): Pair<BigInteger, BigInteger> {
        var i = 0
        fun length(): Int {
            val first = der[i++].toInt() and 0xff
            if (first < 0x80) return first
            var n = 0
            repeat(first and 0x7f) { n = (n shl 8) or (der[i++].toInt() and 0xff) }
            return n
        }
        fun integer(): BigInteger {
            require(der[i++].toInt() == 0x02) { "not a DER integer" }
            val len = length()
            require(len in 1..33 && i + len <= der.size) { "bad DER integer" }
            return BigInteger(1, der.copyOfRange(i, i + len)).also { i += len }
        }
        require(der.size >= 8 && der[i++].toInt() == 0x30) { "not a DER sequence" }
        require(length() == der.size - i) { "bad DER sequence length" }
        val r = integer()
        val s = integer()
        require(i == der.size) { "trailing bytes in DER signature" }
        return r to s
    }

    private fun unsigned(n: BigInteger, size: Int): ByteArray {
        val raw = n.toByteArray()
        return when {
            raw.size == size -> raw
            raw.size == size + 1 && raw[0].toInt() == 0 -> raw.copyOfRange(1, raw.size)
            raw.size < size -> ByteArray(size - raw.size) + raw
            else -> throw IllegalArgumentException("coordinate too large")
        }
    }

    private fun strings(vararg parts: ByteArray): ByteArray {
        val out = ByteArrayOutputStream()
        parts.forEach { out.writeString(it) }
        return out.toByteArray()
    }

    private fun ByteArrayOutputStream.writeString(b: ByteArray) {
        val n = b.size
        write(byteArrayOf((n ushr 24).toByte(), (n ushr 16).toByte(), (n ushr 8).toByte(), n.toByte()))
        write(b)
    }
}

/** The signer as a JSch identity, so JSch never holds a private key. */
class SignerIdentity(private val signer: SshSigner, private val label: String = "frame-control") : Identity {
    override fun setPassphrase(passphrase: ByteArray?) = true
    override fun getPublicKeyBlob(): ByteArray = SshWire.publicKeyBlob(signer.publicKey)
    override fun getSignature(data: ByteArray): ByteArray? = runCatching { SshWire.signature(signer.sign(data)) }.getOrNull()
    override fun getSignature(data: ByteArray, alg: String?): ByteArray? =
        if (alg == null || alg == SshWire.ALGORITHM) getSignature(data) else null
    override fun getAlgName() = SshWire.ALGORITHM
    override fun getName() = label
    override fun isEncrypted() = false
    override fun clear() {}
}
