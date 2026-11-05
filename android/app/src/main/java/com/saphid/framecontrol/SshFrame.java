package com.saphid.framecontrol;

import android.content.Context;
import android.content.SharedPreferences;
import android.util.Base64;

import com.jcraft.jsch.ChannelExec;
import com.jcraft.jsch.ChannelSftp;
import com.jcraft.jsch.HostKey;
import com.jcraft.jsch.HostKeyRepository;
import com.jcraft.jsch.JSch;
import com.jcraft.jsch.Session;
import com.jcraft.jsch.UserInfo;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.io.PipedInputStream;
import java.io.PipedOutputStream;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.SecureRandom;
import java.util.Arrays;
import java.util.concurrent.TimeUnit;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/** An SSH session, private SFTP deployment, and loopback-only tunnel to the shared server. */
final class SshFrame implements AutoCloseable {
    interface HostApproval { boolean approve(String host, String fingerprint); }
    private static final Pattern PORT = Pattern.compile("Frame Control on http://127\\.0\\.0\\.1:(\\d+)\\s");
    private final Context context;
    private final String host;
    private final String user;
    private final HostApproval approval;
    private final SecureIdentity identity;
    private Session session;
    private ChannelExec server;
    private PipedOutputStream serverInput;
    private int localPort;

    SshFrame(Context context, String host, String user, HostApproval approval) {
        this.context = context.getApplicationContext();
        this.host = host;
        this.user = user;
        this.approval = approval;
        this.identity = new SecureIdentity(context);
    }

    String publicKey() throws Exception { return identity.publicLine(); }

    void pair(String password) throws Exception {
        if (password.isEmpty()) throw new IllegalArgumentException("Enter the Developer Mode password");
        connect(password);
        String key = identity.publicLine();
        String file = "~/.ssh/authorized_keys";
        check("umask 077; mkdir -p ~/.ssh && touch " + file + " && chmod 700 ~/.ssh && chmod 600 " + file
                + " && { grep -qxF " + quote(key) + " " + file + " || { "
                + "[ -s " + file + " ] && [ -n \"$(tail -c 1 " + file + ")\" ] && printf '\\n' >> " + file
                + "; printf '%s\\n' " + quote(key) + " >> " + file + "; }; }", 20000);
        session.disconnect();
        session = null;
        connect(null);
    }

    void connect(String password) throws Exception {
        close();
        JSch jsch = new JSch();
        jsch.setHostKeyRepository(new PinnedHosts(context, approval));
        if (password == null) identity.addTo(jsch);
        Session next = jsch.getSession(user, host, 22);
        next.setConfig("StrictHostKeyChecking", "yes");
        next.setConfig("PreferredAuthentications", password == null ? "publickey" : "password");
        if (password != null) next.setPassword(password);
        next.connect(10000);
        session = next;
    }

    int start() throws Exception {
        if (session == null || !session.isConnected()) throw new IllegalStateException("Frame is disconnected");
        check("command -v python3 >/dev/null && python3 -c 'import sys; assert sys.version_info >= (3, 8)'", 10000);
        String version;
        try (InputStream in = context.getAssets().open("frame-bundle.version")) {
            byte[] bytes = new byte[64];
            int count = 0, read;
            while (count < bytes.length && (read = in.read(bytes, count, bytes.length - count)) > 0) count += read;
            version = new String(bytes, 0, count, StandardCharsets.US_ASCII).trim();
        }
        if (!version.matches("[0-9a-f]{16}")) throw new IllegalStateException("Invalid app bundle version");
        String dir = ".cache/frame-control/" + version;
        if (exec("test -f " + dir + "/ui/server.py", 10000).status != 0) {
            check("mkdir -p .cache/frame-control", 10000);
            ChannelSftp sftp = (ChannelSftp) session.openChannel("sftp");
            sftp.connect(10000);
            try (InputStream in = context.getAssets().open("frame-bundle.tar.gz")) {
                sftp.put(in, dir + ".tar.gz");
            } finally { sftp.disconnect(); }
            check("rm -rf " + dir + ".tmp && mkdir " + dir + ".tmp && tar xzf " + dir
                    + ".tar.gz -C " + dir + ".tmp && rm -f " + dir + ".tar.gz && rm -rf " + dir
                    + " && mv " + dir + ".tmp " + dir, 120000);
        }
        String key = randomKey();
        currentKey = key;
        String command = "cd " + dir + " && FRAME_LOCAL=1 FRAME_UI_KEY=" + key
                + " FRAME_DEVICE=Android FRAME_CLIENT=" + quote("android-" + identity.publicLine().hashCode())
                + " exec python3 -I -u -B \"$PWD/ui/server.py\" --port 0 --exit-on-eof 2>&1";
        ChannelExec channel = (ChannelExec) session.openChannel("exec");
        PipedInputStream stdin = new PipedInputStream();
        serverInput = new PipedOutputStream(stdin);
        channel.setInputStream(stdin);
        channel.setCommand(command);
        InputStream stdout = channel.getInputStream();
        channel.connect(10000);
        server = channel;
        StringBuilder output = new StringBuilder();
        long deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(30);
        byte[] buf = new byte[4096];
        int remotePort = 0;
        while (System.nanoTime() < deadline && !channel.isClosed()) {
            while (stdout.available() > 0) {
                int n = stdout.read(buf, 0, Math.min(buf.length, stdout.available()));
                if (n > 0) output.append(new String(buf, 0, n, StandardCharsets.UTF_8));
            }
            Matcher match = PORT.matcher(output);
            if (match.find()) { remotePort = Integer.parseInt(match.group(1)); break; }
            Thread.sleep(50);
        }
        if (remotePort < 1 || remotePort > 65535) {
            throw new IllegalStateException("Frame Control server did not start: " + output);
        }
        Thread drain = new Thread(() -> {
            byte[] discard = new byte[4096];
            try { while (stdout.read(discard) != -1) {} }
            catch (Exception ignored) { /* The SSH session owns this stream. */ }
        }, "frame-server-console");
        drain.setDaemon(true);
        drain.start();
        localPort = session.setPortForwardingL("127.0.0.1", 0, "127.0.0.1", remotePort);
        return localPort;
    }

    private String check(String command, int timeout) throws Exception {
        Result result = exec(command, timeout);
        if (result.status != 0) throw new IllegalStateException(result.output.isEmpty() ? "Frame command failed" : result.output);
        return result.output;
    }

    private Result exec(String command, int timeout) throws Exception {
        ChannelExec channel = (ChannelExec) session.openChannel("exec");
        channel.setCommand("{ " + command + "; } 2>&1; printf '\\n@@rc=%s\\n' \"$?\"");
        InputStream in = channel.getInputStream();
        channel.connect(10000);
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        long deadline = System.nanoTime() + TimeUnit.MILLISECONDS.toNanos(timeout);
        byte[] buf = new byte[4096];
        try {
            while (System.nanoTime() < deadline && !channel.isClosed()) {
                while (in.available() > 0) {
                    int n = in.read(buf, 0, Math.min(in.available(), buf.length));
                    if (n > 0) out.write(buf, 0, n);
                }
                Thread.sleep(25);
            }
            if (!channel.isClosed()) throw new IllegalStateException("Frame command timed out");
            while (in.available() > 0) {
                int n = in.read(buf, 0, Math.min(in.available(), buf.length));
                if (n > 0) out.write(buf, 0, n);
            }
            String text = new String(out.toByteArray(), StandardCharsets.UTF_8);
            int marker = text.lastIndexOf("@@rc=");
            if (marker < 0) throw new IllegalStateException("Frame command did not return a status: " + text);
            return new Result(text.substring(0, marker).trim(), Integer.parseInt(text.substring(marker + 5).trim()));
        } finally { channel.disconnect(); }
    }

    private static String quote(String s) { return "'" + s.replace("'", "'\\''") + "'"; }
    private static String randomKey() {
        byte[] bytes = new byte[32]; new SecureRandom().nextBytes(bytes);
        return Base64.encodeToString(bytes, Base64.NO_WRAP | Base64.URL_SAFE | Base64.NO_PADDING);
    }
    String pageUrl() { return "http://127.0.0.1:" + localPort + "/?key=" + currentKey; }
    private String currentKey;
    private static final class Result {
        final String output;
        final int status;
        Result(String output, int status) { this.output = output; this.status = status; }
    }

    @Override public void close() {
        try { if (serverInput != null) serverInput.close(); } catch (Exception ignored) {}
        if (server != null) server.disconnect();
        if (session != null) session.disconnect();
        serverInput = null; server = null; session = null; localPort = 0; currentKey = null;
    }

    /** Pins exactly the SSH host key bytes after a first-pair fingerprint confirmation. */
    private static final class PinnedHosts implements HostKeyRepository {
        private final SharedPreferences prefs;
        private final HostApproval approval;
        PinnedHosts(Context context, HostApproval approval) {
            prefs = context.getSharedPreferences("frame-hosts", Context.MODE_PRIVATE);
            this.approval = approval;
        }
        @Override public int check(String host, byte[] key) {
            String saved = prefs.getString(host, null);
            if (saved != null) return MessageDigest.isEqual(Base64.decode(saved, Base64.DEFAULT), key) ? OK : CHANGED;
            try {
                byte[] digest = MessageDigest.getInstance("SHA-256").digest(key);
                String fingerprint = "SHA256:" + Base64.encodeToString(digest, Base64.NO_WRAP | Base64.NO_PADDING);
                if (!approval.approve(host, fingerprint)) return NOT_INCLUDED;
                return prefs.edit().putString(host, Base64.encodeToString(key, Base64.NO_WRAP)).commit() ? OK : NOT_INCLUDED;
            } catch (Exception e) { return NOT_INCLUDED; }
        }
        @Override public void add(HostKey hostKey, UserInfo ui) {}
        @Override public void remove(String host, String type) {}
        @Override public void remove(String host, String type, byte[] key) {}
        @Override public String getKnownHostsRepositoryID() { return "Frame Control pinned hosts"; }
        @Override public HostKey[] getHostKey() { return new HostKey[0]; }
        @Override public HostKey[] getHostKey(String host, String type) { return new HostKey[0]; }
    }
}
