package com.saphid.framecontrol;

import android.content.Context;
import android.content.SharedPreferences;
import android.security.keystore.KeyGenParameterSpec;
import android.security.keystore.KeyProperties;
import android.util.Base64;

import com.jcraft.jsch.JSch;
import com.jcraft.jsch.KeyPair;

import java.io.ByteArrayOutputStream;
import java.nio.charset.StandardCharsets;
import java.security.KeyStore;
import java.util.Arrays;

import javax.crypto.Cipher;
import javax.crypto.KeyGenerator;
import javax.crypto.SecretKey;
import javax.crypto.spec.GCMParameterSpec;

/** One install's SSH identity. Private bytes are encrypted by a non-exportable Android Keystore key. */
final class SecureIdentity {
    private static final String ALIAS = "frame-control-ssh-wrap";
    private static final String PRIVATE = "ssh.private";
    private static final String PUBLIC = "ssh.public";
    private final SharedPreferences prefs;

    SecureIdentity(Context context) {
        prefs = context.getSharedPreferences("frame-identity", Context.MODE_PRIVATE);
    }

    String publicLine() throws Exception {
        ensure();
        return prefs.getString(PUBLIC, "").trim();
    }

    void addTo(JSch jsch) throws Exception {
        ensure();
        byte[] sealed = Base64.decode(prefs.getString(PRIVATE, ""), Base64.DEFAULT);
        if (sealed.length < 13) throw new IllegalStateException("Invalid saved phone key");
        byte[] iv = Arrays.copyOfRange(sealed, 0, 12);
        byte[] ciphertext = Arrays.copyOfRange(sealed, 12, sealed.length);
        Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
        cipher.init(Cipher.DECRYPT_MODE, wrapKey(), new GCMParameterSpec(128, iv));
        byte[] privateKey = cipher.doFinal(ciphertext);
        try {
            jsch.addIdentity("frame-control-android", privateKey, null, null);
        } finally {
            Arrays.fill(privateKey, (byte) 0);
        }
    }

    private void ensure() throws Exception {
        if (prefs.contains(PRIVATE) && prefs.contains(PUBLIC)) return;
        KeyPair pair = KeyPair.genKeyPair(new JSch(), KeyPair.RSA, 3072);
        ByteArrayOutputStream secret = new ByteArrayOutputStream();
        ByteArrayOutputStream pub = new ByteArrayOutputStream();
        try {
            pair.writePrivateKey(secret);
            pair.writePublicKey(pub, "frame-control@Android");
            Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
            // Android Keystore generates its own GCM IV; supplying one for
            // encryption is rejected by its randomized-encryption policy.
            cipher.init(Cipher.ENCRYPT_MODE, wrapKey());
            byte[] iv = cipher.getIV();
            if (iv == null || iv.length != 12) throw new IllegalStateException("Invalid Keystore IV");
            byte[] encrypted = cipher.doFinal(secret.toByteArray());
            byte[] sealed = new byte[iv.length + encrypted.length];
            System.arraycopy(iv, 0, sealed, 0, iv.length);
            System.arraycopy(encrypted, 0, sealed, iv.length, encrypted.length);
            if (!prefs.edit().putString(PRIVATE, Base64.encodeToString(sealed, Base64.NO_WRAP))
                    .putString(PUBLIC, new String(pub.toByteArray(), StandardCharsets.UTF_8)).commit()) {
                throw new IllegalStateException("Could not save the phone key");
            }
        } finally {
            pair.dispose();
            byte[] bytes = secret.toByteArray();
            Arrays.fill(bytes, (byte) 0);
        }
    }

    private SecretKey wrapKey() throws Exception {
        KeyStore store = KeyStore.getInstance("AndroidKeyStore");
        store.load(null);
        if (store.containsAlias(ALIAS)) return (SecretKey) store.getKey(ALIAS, null);
        KeyGenerator generator = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore");
        generator.init(new KeyGenParameterSpec.Builder(ALIAS,
                KeyProperties.PURPOSE_ENCRYPT | KeyProperties.PURPOSE_DECRYPT)
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                .setKeySize(256).build());
        return generator.generateKey();
    }
}
