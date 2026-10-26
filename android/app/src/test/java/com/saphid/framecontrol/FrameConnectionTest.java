package com.saphid.framecontrol;

import org.junit.Rule;
import org.junit.Test;
import org.junit.rules.TemporaryFolder;

import java.io.File;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.attribute.PosixFilePermissions;
import java.util.Arrays;
import java.util.Collections;
import java.util.TreeSet;
import java.util.concurrent.TimeUnit;

import static org.junit.Assert.*;

/** Runs the generated headset shell against a temporary HOME. */
public class FrameConnectionTest {
    @Rule public TemporaryFolder temporary = new TemporaryFolder();

    private static final String KEY = "rsa-sha2-256 AAAAB3NzaC1yc2EAAAADAQAB frame-control 'phone'";
    private static final String MAC = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIMac mac";

    private static final class Result {
        final int exit;
        final String output;

        Result(int exit, String output) { this.exit = exit; this.output = output; }
    }

    private static Result sh(File home, String command) throws Exception {
        ProcessBuilder builder = new ProcessBuilder("/bin/sh", "-c", command);
        builder.environment().put("HOME", home.getPath());
        builder.redirectError(ProcessBuilder.Redirect.to(new File("/dev/null")));
        Process process = builder.start();
        java.io.ByteArrayOutputStream bytes = new java.io.ByteArrayOutputStream();
        try (java.io.InputStream in = process.getInputStream()) {
            byte[] buffer = new byte[4096];
            for (int n; (n = in.read(buffer)) != -1; ) bytes.write(buffer, 0, n);
        }
        String output = new String(bytes.toByteArray(), StandardCharsets.UTF_8);
        assertTrue("Shell timed out", process.waitFor(10, TimeUnit.SECONDS));
        return new Result(process.exitValue(), output);
    }

    private String authorize(String existing) throws Exception {
        File home = temporary.newFolder();
        File keys = new File(home, ".ssh/authorized_keys");
        if (existing != null) {
            assertTrue(keys.getParentFile().mkdirs());
            Files.write(keys.toPath(), existing.getBytes(StandardCharsets.UTF_8));
        }
        for (int i = 0; i < 2; i++) assertEquals(0, sh(home, FrameConnection.authorizeCommand(KEY)).exit);
        assertEquals("rw-------", PosixFilePermissions.toString(Files.getPosixFilePermissions(keys.toPath())));
        return new String(Files.readAllBytes(keys.toPath()), StandardCharsets.UTF_8);
    }

    @Test public void authorizingTerminatesALastLineWithoutNewlineAndIsIdempotent() throws Exception {
        assertEquals(KEY + "\n", authorize(null));
        assertEquals(KEY + "\n", authorize(""));
        assertEquals(MAC + "\n" + KEY + "\n", authorize(MAC));
        assertEquals(MAC + "\n" + KEY + "\n", authorize(MAC + "\n"));
        assertEquals(MAC + "\nother\n" + KEY + "\n", authorize(MAC + "\nother"));
        // Already present as an unterminated last line: left exactly as it was.
        assertEquals(MAC + "\n" + KEY, authorize(MAC + "\n" + KEY));
    }

    @Test public void accountListingSeparatesAbsentUserdataFromEmptyAccounts() throws Exception {
        File home = temporary.newFolder();
        Result absent = sh(home, FrameConnection.ACCOUNTS_COMMAND);
        assertEquals(0, absent.exit);
        assertEquals("absent\n", absent.output);
        assertTrue(FrameConnection.parseAccounts(absent.output).isEmpty());
        File userdata = new File(home, ".local/share/Steam/userdata");
        assertTrue(userdata.mkdirs());
        assertEquals("present\n", sh(home, FrameConnection.ACCOUNTS_COMMAND).output);
        for (String directory : Arrays.asList("123", "4567890", "anonymous", "0123456789012", "12a"))
            assertTrue(new File(userdata, directory).mkdir());
        Files.write(new File(userdata, "999").toPath(), new byte[]{1});
        Result present = sh(home, FrameConnection.ACCOUNTS_COMMAND);
        assertEquals(0, present.exit);
        assertEquals(new TreeSet<>(Arrays.asList("123", "4567890")),
                FrameConnection.parseAccounts(present.output));
        // An unreadable root is an error, never an empty account list.
        File broken = temporary.newFolder();
        File file = new File(broken, ".local/share/Steam/userdata");
        assertTrue(file.getParentFile().mkdirs());
        Files.write(file.toPath(), new byte[]{1});
        assertNotEquals(0, sh(broken, FrameConnection.ACCOUNTS_COMMAND).exit);
    }

    @Test public void unexpectedAccountOutputIsRejected() throws Exception {
        for (String output : Arrays.asList("", "absent", "present", "present\n123", "absent\n123\n",
                "present\nabc\n", "present\n\n", "ready\n", "present\n12 3\n")) {
            try {
                FrameConnection.parseAccounts(output);
                fail("Accepted " + output);
            } catch (IOException expected) {
                // Fail closed: the poll is retried and no baseline changes.
            }
        }
        assertEquals(Collections.emptySet(), FrameConnection.parseAccounts("present\n"));
    }
}
