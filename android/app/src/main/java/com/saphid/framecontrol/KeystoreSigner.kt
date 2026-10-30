package com.saphid.framecontrol

import android.content.Context
import android.content.pm.PackageManager
import android.os.Build
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyInfo
import android.security.keystore.KeyProperties
import android.security.keystore.StrongBoxUnavailableException
import com.saphid.framecontrol.core.SshSigner
import java.security.KeyFactory
import java.security.KeyPairGenerator
import java.security.KeyStore
import java.security.Signature
import java.security.interfaces.ECPublicKey
import java.security.spec.ECGenParameterSpec

/**
 * This phone's SSH key: ECDSA P-256 made once inside the Android Keystore (StrongBox when
 * the phone has one). The private key can't be exported, isn't in backups, and goes when
 * the app is uninstalled; the app only ever sees the public key and signatures.
 */
class KeystoreSigner(private val context: Context) : SshSigner {
    private val keyStore: KeyStore by lazy { KeyStore.getInstance(PROVIDER).apply { load(null) } }

    private val entry: KeyStore.PrivateKeyEntry by lazy {
        synchronized(LOCK) {
            (keyStore.getEntry(ALIAS, null) as? KeyStore.PrivateKeyEntry) ?: run {
                val strongBox = context.packageManager.hasSystemFeature(PackageManager.FEATURE_STRONGBOX_KEYSTORE)
                try {
                    generate(strongBox)
                } catch (e: StrongBoxUnavailableException) {
                    generate(false)
                }
                keyStore.getEntry(ALIAS, null) as KeyStore.PrivateKeyEntry
            }
        }
    }

    override val publicKey: ECPublicKey get() = entry.certificate.publicKey as ECPublicKey

    override fun sign(data: ByteArray): ByteArray = Signature.getInstance("SHA256withECDSA").run {
        initSign(entry.privateKey)
        update(data)
        sign()
    }

    /** Where the key lives, for the setup screen: "StrongBox", "secure hardware" or "software". */
    fun protection(): String = runCatching {
        val info = KeyFactory.getInstance(entry.privateKey.algorithm, PROVIDER).getKeySpec(entry.privateKey, KeyInfo::class.java)
        if (Build.VERSION.SDK_INT >= 31) {
            when (info.securityLevel) {
                KeyProperties.SECURITY_LEVEL_STRONGBOX -> "StrongBox"
                KeyProperties.SECURITY_LEVEL_TRUSTED_ENVIRONMENT -> "secure hardware"
                else -> "the Android Keystore"
            }
        } else {
            @Suppress("DEPRECATION")
            if (info.isInsideSecureHardware) "secure hardware" else "the Android Keystore"
        }
    }.getOrDefault("the Android Keystore")

    private fun generate(strongBox: Boolean) {
        val spec = KeyGenParameterSpec.Builder(ALIAS, KeyProperties.PURPOSE_SIGN)
            .setAlgorithmParameterSpec(ECGenParameterSpec("secp256r1"))
            .setDigests(KeyProperties.DIGEST_SHA256)
            .setIsStrongBoxBacked(strongBox)
            .build()
        KeyPairGenerator.getInstance(KeyProperties.KEY_ALGORITHM_EC, PROVIDER).apply { initialize(spec) }.generateKeyPair()
    }

    private companion object {
        const val PROVIDER = "AndroidKeyStore"
        const val ALIAS = "frame-control-ssh-p256-v1"
        val LOCK = Any()
    }
}
