package com.saphid.framecontrol;

import android.security.keystore.KeyGenParameterSpec;
import android.security.keystore.KeyProperties;
import com.jcraft.jsch.Identity;
import java.io.ByteArrayOutputStream;
import java.io.DataOutputStream;
import java.math.BigInteger;
import java.nio.charset.StandardCharsets;
import java.security.KeyPairGenerator;
import java.security.KeyStore;
import java.security.PrivateKey;
import java.security.Signature;
import java.security.interfaces.RSAPublicKey;
import java.util.Base64;

/** The SSH private key is a non-exportable Android Keystore signing key. */
final class PhoneIdentity implements Identity {
  private static final String ALIAS = "frame-control-ssh-v1";
  private final PrivateKey key;
  private final byte[] publicBlob;

  PhoneIdentity() throws Exception {
    KeyStore store = KeyStore.getInstance("AndroidKeyStore");
    store.load(null);
    if (!store.containsAlias(ALIAS)) {
      KeyPairGenerator generator = KeyPairGenerator.getInstance("RSA", "AndroidKeyStore");
      generator.initialize(
          new KeyGenParameterSpec.Builder(ALIAS, KeyProperties.PURPOSE_SIGN)
              .setKeySize(3072)
              .setDigests(KeyProperties.DIGEST_SHA256, KeyProperties.DIGEST_SHA512)
              .setSignaturePaddings(KeyProperties.SIGNATURE_PADDING_RSA_PKCS1)
              .build());
      generator.generateKeyPair();
    }
    key = (PrivateKey) store.getKey(ALIAS, null);
    RSAPublicKey publicKey = (RSAPublicKey) store.getCertificate(ALIAS).getPublicKey();
    publicBlob =
        blob(
            "ssh-rsa".getBytes(StandardCharsets.US_ASCII),
            integer(publicKey.getPublicExponent()),
            integer(publicKey.getModulus()));
  }

  private static byte[] integer(BigInteger value) {
    return value.toByteArray();
  }

  private static byte[] blob(byte[]... strings) throws Exception {
    ByteArrayOutputStream bytes = new ByteArrayOutputStream();
    DataOutputStream out = new DataOutputStream(bytes);
    for (byte[] s : strings) {
      out.writeInt(s.length);
      out.write(s);
    }
    return bytes.toByteArray();
  }

  String authorizedKey(String install) {
    return "ssh-rsa "
        + Base64.getEncoder().encodeToString(publicBlob)
        + " frame-control-android-"
        + install;
  }

  @Override
  public byte[] getPublicKeyBlob() {
    return publicBlob.clone();
  }

  @Override
  public byte[] getSignature(byte[] data) {
    return getSignature(data, "rsa-sha2-512");
  }

  @Override
  public byte[] getSignature(byte[] data, String algorithm) {
    try {
      if (!algorithm.equals("rsa-sha2-256") && !algorithm.equals("rsa-sha2-512")) return null;
      Signature signer =
          Signature.getInstance(
              algorithm.equals("rsa-sha2-512") ? "SHA512withRSA" : "SHA256withRSA");
      signer.initSign(key);
      signer.update(data);
      return blob(algorithm.getBytes(StandardCharsets.US_ASCII), signer.sign());
    } catch (Exception e) {
      return null;
    }
  }

  @Override
  public boolean setPassphrase(byte[] ignored) {
    return true;
  }

  @Override
  public String getAlgName() {
    return "ssh-rsa";
  }

  @Override
  public String getName() {
    return ALIAS;
  }

  @Override
  public boolean isEncrypted() {
    return false;
  }

  @Override
  public void clear() {
    /* Keystore owns the key; disconnect never deletes it. */
  }
}
