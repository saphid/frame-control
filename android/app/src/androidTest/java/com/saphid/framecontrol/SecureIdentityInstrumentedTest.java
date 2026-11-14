package com.saphid.framecontrol;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertTrue;

import android.content.Context;

import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;

import com.jcraft.jsch.JSch;

import org.junit.Test;
import org.junit.runner.RunWith;

/** Runs against Android Keystore, which a host JVM test cannot emulate. */
@RunWith(AndroidJUnit4.class)
public final class SecureIdentityInstrumentedTest {
    @Test public void generatedKeyDecryptsForSshWithoutTouchingTheAppIdentity() throws Exception {
        Context context = InstrumentationRegistry.getInstrumentation().getTargetContext()
                .createDeviceProtectedStorageContext();
        // Device-protected preferences are separate from the app's normal identity.
        context.getSharedPreferences("frame-identity", Context.MODE_PRIVATE).edit().clear().commit();
        try {
            SecureIdentity identity = new SecureIdentity(context);
            String publicLine = identity.publicLine();
            assertTrue(publicLine.startsWith("ssh-rsa "));
            assertEquals(publicLine, identity.publicLine());
            JSch ssh = new JSch();
            identity.addTo(ssh); // Exercises Keystore AES-GCM decryption.
            assertEquals(1, ssh.getIdentityRepository().getIdentities().size());
        } finally {
            context.getSharedPreferences("frame-identity", Context.MODE_PRIVATE).edit().clear().commit();
        }
    }
}
