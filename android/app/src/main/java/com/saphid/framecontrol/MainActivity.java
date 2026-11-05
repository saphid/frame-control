package com.saphid.framecontrol;

import android.Manifest;
import android.app.Activity;
import android.app.AlertDialog;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.ContentValues;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Environment;
import android.provider.MediaStore;
import android.text.InputType;
import android.util.Base64;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.webkit.JsPromptResult;
import android.webkit.JsResult;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.webkit.WebResourceRequest;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import androidx.webkit.WebMessageCompat;
import androidx.webkit.WebViewCompat;
import androidx.webkit.WebViewFeature;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.OutputStream;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;

/** Android phone shell for the same Frame-hosted page used by the iOS and desktop apps. */
public final class MainActivity extends Activity {
    private static final int BACKGROUND = Color.rgb(14, 20, 27);
    private static final int PANEL = Color.rgb(25, 34, 45);
    private static final int TEXT = Color.rgb(238, 244, 251);
    private static final int MUTED = Color.rgb(159, 176, 195);
    private static final int BLUE = Color.rgb(47, 115, 220);
    private static final String NOTIFICATIONS = "frame-control-local";
    private static final int PICK_FILE = 71;
    private final ExecutorService worker = Executors.newSingleThreadExecutor();
    private SshFrame frame;
    private WebView web;
    private ValueCallback<Uri[]> fileCallback;
    private EditText hostField;
    private EditText userField;
    private EditText passwordField;
    private int generation;
    private int localPort;

    @Override protected void onCreate(Bundle state) {
        super.onCreate(state);
        getWindow().setStatusBarColor(BACKGROUND);
        getWindow().setNavigationBarColor(BACKGROUND);
        if (WebViewFeature.isFeatureSupported(WebViewFeature.WEB_MESSAGE_LISTENER)
                && WebViewFeature.isFeatureSupported(WebViewFeature.DOCUMENT_START_SCRIPT)) {
            String host = getPreferences(MODE_PRIVATE).getString("host", "");
            if (!host.isEmpty()) { showMessage("Connecting to your Frame…"); connect(host,
                    getPreferences(MODE_PRIVATE).getString("user", "steamos"), null); }
            else showSetup(null);
        } else showMessage("Android System WebView needs an update before Frame Control can open securely.");
    }

    private int dp(int n) { return Math.round(n * getResources().getDisplayMetrics().density); }
    private TextView label(String text, int size, int color) {
        TextView view = new TextView(this);
        view.setText(text); view.setTextSize(size); view.setTextColor(color);
        return view;
    }
    private EditText field(String hint, String value, boolean secret) {
        EditText view = new EditText(this);
        view.setHint(hint); view.setText(value); view.setSingleLine(true);
        view.setTextColor(TEXT); view.setHintTextColor(MUTED);
        view.setInputType(secret ? InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_PASSWORD
                : InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_URI);
        view.setPadding(dp(12), dp(12), dp(12), dp(12));
        view.setBackgroundColor(PANEL);
        return view;
    }
    private LinearLayout stack() {
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(dp(20), dp(28), dp(20), dp(20));
        root.setBackgroundColor(BACKGROUND);
        return root;
    }
    private void add(LinearLayout root, View view, int marginTop) {
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(-1, -2);
        params.topMargin = dp(marginTop); root.addView(view, params);
    }
    private Button button(String text, Runnable action) {
        Button view = new Button(this);
        view.setText(text); view.setTextColor(TEXT); view.setBackgroundTintList(
                android.content.res.ColorStateList.valueOf(BLUE));
        view.setOnClickListener(v -> action.run());
        return view;
    }
    private void showMessage(String message) {
        LinearLayout root = stack();
        add(root, label("Frame Control", 25, TEXT), 0);
        add(root, label(message, 16, MUTED), 24);
        setContentView(root);
    }
    private void showSetup(String error) {
        ++generation;
        closeFrame();
        LinearLayout root = stack();
        add(root, label("Connect to your Steam Frame", 25, TEXT), 0);
        add(root, label("The Frame and this phone need to be on the same network. Enable Developer Mode and set a user password on the headset.", 15, MUTED), 12);
        if (error != null) add(root, label(error, 15, Color.rgb(255, 140, 140)), 18);
        String savedHost = getPreferences(MODE_PRIVATE).getString("host", "frame.local");
        String savedUser = getPreferences(MODE_PRIVATE).getString("user", "steamos");
        hostField = field("Frame address", savedHost, false);
        userField = field("Frame user", savedUser, false);
        passwordField = field("Developer password", "", true);
        add(root, hostField, 24); add(root, userField, 10); add(root, passwordField, 10);
        add(root, label("On first connection, confirm the Frame's SSH fingerprint. Your password is used once to add this phone's key; it is never saved.", 13, MUTED), 16);
        add(root, button("Connect", () -> {
            String host = hostField.getText().toString().trim();
            String user = userField.getText().toString().trim();
            String password = passwordField.getText().toString();
            passwordField.setText("");
            if (host.isEmpty() || user.isEmpty()) { showSetup("Enter the Frame address and user."); return; }
            showMessage("Connecting to " + host + "…");
            connect(host, user, password.isEmpty() ? null : password);
        }), 24);
        if (getPreferences(MODE_PRIVATE).contains("host")) {
            add(root, button("Forget this Frame", () -> {
                getPreferences(MODE_PRIVATE).edit().clear().apply();
                getSharedPreferences("frame-hosts", MODE_PRIVATE).edit().clear().apply();
                showSetup(null);
            }), 12);
        }
        ScrollView scroll = new ScrollView(this);
        scroll.setFillViewport(true);
        scroll.addView(root);
        setContentView(scroll);
    }

    private void connect(String host, String user, String password) {
        int mine = ++generation;
        worker.execute(() -> {
            SshFrame next = new SshFrame(this, host, user, this::approveHostKey);
            try {
                if (password == null) next.connect(null); else next.pair(password);
                int port = next.start();
                runOnUiThread(() -> {
                    if (mine != generation) { next.close(); return; }
                    frame = next; localPort = port;
                    getPreferences(MODE_PRIVATE).edit().putString("host", host).putString("user", user).apply();
                    showWeb(next.pageUrl());
                });
            } catch (Exception error) {
                next.close();
                runOnUiThread(() -> { if (mine == generation) showSetup("Couldn't connect: " + error.getMessage()); });
            }
        });
    }

    private boolean approveHostKey(String host, String fingerprint) {
        CountDownLatch decision = new CountDownLatch(1);
        AtomicBoolean accepted = new AtomicBoolean(false);
        runOnUiThread(() -> new AlertDialog.Builder(this).setTitle("Confirm your Frame")
                .setMessage("The Frame at " + host + " presented this SSH key:\n\n" + fingerprint
                        + "\n\nConfirm it on the headset or through another trusted connection before continuing.")
                .setPositiveButton("Trust this key", (dialog, which) -> { accepted.set(true); decision.countDown(); })
                .setNegativeButton("Cancel", (dialog, which) -> decision.countDown())
                .setOnCancelListener(dialog -> decision.countDown()).show());
        try { return decision.await(120, TimeUnit.SECONDS) && accepted.get(); }
        catch (InterruptedException e) { Thread.currentThread().interrupt(); return false; }
    }

    private void showWeb(String url) {
        web = new WebView(this);
        web.setBackgroundColor(BACKGROUND);
        web.getSettings().setJavaScriptEnabled(true);
        web.getSettings().setDomStorageEnabled(true);
        web.getSettings().setMediaPlaybackRequiresUserGesture(false);
        web.getSettings().setAllowFileAccess(false);
        web.getSettings().setAllowContentAccess(true);
        web.setWebViewClient(new WebViewClient() {
            @Override public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                Uri uri = request.getUrl();
                if ("http".equals(uri.getScheme()) && "127.0.0.1".equals(uri.getHost())
                        && uri.getPort() == localPort) return false;
                try { startActivity(new Intent(Intent.ACTION_VIEW, uri)); }
                catch (Exception ignored) { new AlertDialog.Builder(MainActivity.this)
                        .setMessage("No app can open " + uri).setPositiveButton("OK", null).show(); }
                return true;
            }
        });
        web.setWebChromeClient(new WebChromeClient() {
            @Override public boolean onShowFileChooser(WebView view, ValueCallback<Uri[]> callback, FileChooserParams params) {
                if (fileCallback != null) fileCallback.onReceiveValue(null);
                fileCallback = callback;
                try { startActivityForResult(params.createIntent(), PICK_FILE); return true; }
                catch (Exception e) { fileCallback = null; callback.onReceiveValue(null); return false; }
            }
            @Override public boolean onJsAlert(WebView view, String url, String message, JsResult result) {
                new AlertDialog.Builder(MainActivity.this).setMessage(message)
                        .setPositiveButton("OK", (d, w) -> result.confirm()).show(); return true;
            }
            @Override public boolean onJsConfirm(WebView view, String url, String message, JsResult result) {
                new AlertDialog.Builder(MainActivity.this).setMessage(message)
                        .setPositiveButton("OK", (d, w) -> result.confirm())
                        .setNegativeButton("Cancel", (d, w) -> result.cancel()).show(); return true;
            }
        });
        String allowed = "http://127.0.0.1:" + localPort;
        WebViewCompat.addWebMessageListener(web, "FrameNative", java.util.Collections.singleton(allowed),
                (view, message, sourceOrigin, isMainFrame, replyProxy) -> {
                    if (!isMainFrame || !"http".equals(sourceOrigin.getScheme())
                            || !"127.0.0.1".equals(sourceOrigin.getHost()) || sourceOrigin.getPort() != localPort)
                        return;
                    handleBridge(message);
                });
        WebViewCompat.addDocumentStartJavaScript(web, BRIDGE, java.util.Collections.singleton(allowed));
        setContentView(web);
        web.loadUrl(url);
    }

    private static final String BRIDGE = "(() => { const waiting = new Map(); let seq = 0; "
            + "window.__frameReply = (id, ok, json) => { const p = waiting.get(id); if (!p) return; waiting.delete(id); "
            + "if (ok) p.resolve(JSON.parse(json)); else p.reject(new Error(JSON.parse(json))); }; "
            + "const call = (name,arg) => new Promise((resolve,reject) => { const id=++seq; waiting.set(id,{resolve,reject}); "
            + "FrameNative.postMessage(JSON.stringify({id,name,arg:arg??null})); }); "
            + "window.frameApp = { platform:'android', preferences:{read:()=>call('preferencesRead'),"
            + "write:(key,value)=>call('preferencesWrite',{key,value})}, "
            + "notify:(message,request)=>call('notify',{message,request}), "
            + "readClipboard:()=>call('readClipboard'), writeClipboard:(value)=>call('writeClipboard',value), "
            + "setUpConnection:()=>call('setUpConnection'), open:(what)=>call('open',what), "
            + "saveImages:(images)=>call('saveImages',images) }; })();";

    private void handleBridge(WebMessageCompat message) {
        int id = -1;
        try {
            JSONObject request = new JSONObject(message.getData());
            id = request.getInt("id");
            String name = request.getString("name");
            Object arg = request.opt("arg");
            switch (name) {
                case "preferencesRead": {
                    JSONObject values = new JSONObject();
                    for (String key : new String[]{"mvSeparate", "padUsed"}) {
                        String value = getPreferences(MODE_PRIVATE).getString("pref." + key, null);
                        if ("0".equals(value) || "1".equals(value)) values.put(key, value);
                    }
                    reply(id, true, values); break;
                }
                case "preferencesWrite": {
                    JSONObject values = (JSONObject) arg;
                    String key = values.getString("key"), value = values.getString("value");
                    if (!("mvSeparate".equals(key) || "padUsed".equals(key)) || !("0".equals(value) || "1".equals(value)))
                        throw new IllegalArgumentException("Invalid preference");
                    getPreferences(MODE_PRIVATE).edit().putString("pref." + key, value).apply();
                    reply(id, true, true); break;
                }
                case "readClipboard": {
                    ClipboardManager clipboard = (ClipboardManager) getSystemService(CLIPBOARD_SERVICE);
                    ClipData clip = clipboard.getPrimaryClip();
                    reply(id, true, clip == null || clip.getItemCount() == 0 ? "" : String.valueOf(clip.getItemAt(0).coerceToText(this)));
                    break;
                }
                case "writeClipboard": {
                    ClipboardManager clipboard = (ClipboardManager) getSystemService(CLIPBOARD_SERVICE);
                    clipboard.setPrimaryClip(ClipData.newPlainText("Frame Control", String.valueOf(arg)));
                    reply(id, true, true); break;
                }
                case "setUpConnection": { reply(id, true, JSONObject.NULL); showSetup(null); break; }
                case "open": { reply(id, true, openExternal(String.valueOf(arg))); break; }
                case "saveImages": { reply(id, true, saveImages((JSONArray) arg)); break; }
                case "notify": { reply(id, true, notifyLocal((JSONObject) arg)); break; }
                default: throw new IllegalArgumentException("Unknown phone action");
            }
        } catch (Exception error) { if (id > 0) reply(id, false, error.getMessage()); }
    }

    private void reply(int id, boolean ok, Object value) {
        if (web == null) return;
        String json;
        if (value == null || value == JSONObject.NULL) json = "null";
        else if (value instanceof JSONObject || value instanceof JSONArray || value instanceof Number || value instanceof Boolean)
            json = value.toString();
        else json = JSONObject.quote(String.valueOf(value));
        web.evaluateJavascript("window.__frameReply(" + id + "," + ok + "," + JSONObject.quote(json) + ")", null);
    }

    private JSONObject openExternal(String what) throws Exception {
        String target;
        switch (what) {
            case "steamlink": target = "steamlink://"; break;
            case "rdp": target = "rdp://"; break;
            case "terminal": target = "ssh://" + getPreferences(MODE_PRIVATE).getString("user", "steamos") + "@"
                    + getPreferences(MODE_PRIVATE).getString("host", "frame.local"); break;
            case "sftp": target = "sftp://" + getPreferences(MODE_PRIVATE).getString("user", "steamos") + "@"
                    + getPreferences(MODE_PRIVATE).getString("host", "frame.local"); break;
            default: throw new IllegalArgumentException("This app cannot open " + what);
        }
        startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(target)));
        return new JSONObject().put("message", "Opening " + what);
    }

    private JSONObject saveImages(JSONArray images) throws Exception {
        if (images.length() == 0 || images.length() > 20) throw new IllegalArgumentException("Choose 1–20 images");
        for (int index = 0; index < images.length(); index++) {
            JSONObject image = images.getJSONObject(index);
            String encoded = image.getString("data");
            if (encoded.length() > 25_000_000) throw new IllegalArgumentException("Image is too large");
            byte[] bytes = Base64.decode(encoded, Base64.DEFAULT);
            boolean png = bytes.length > 8 && bytes[0] == (byte) 0x89 && bytes[1] == 0x50 && bytes[2] == 0x4e;
            boolean jpeg = bytes.length > 3 && bytes[0] == (byte) 0xff && bytes[1] == (byte) 0xd8;
            if (!png && !jpeg) throw new IllegalArgumentException("Unsupported image format");
            ContentValues values = new ContentValues();
            values.put(MediaStore.Images.Media.DISPLAY_NAME, "Frame Control " + System.currentTimeMillis() + "-" + index + (png ? ".png" : ".jpg"));
            values.put(MediaStore.Images.Media.MIME_TYPE, png ? "image/png" : "image/jpeg");
            if (Build.VERSION.SDK_INT >= 29) values.put(MediaStore.Images.Media.RELATIVE_PATH, Environment.DIRECTORY_PICTURES + "/Frame Control");
            Uri uri = getContentResolver().insert(MediaStore.Images.Media.EXTERNAL_CONTENT_URI, values);
            if (uri == null) throw new IllegalStateException("Could not save image");
            try (OutputStream out = getContentResolver().openOutputStream(uri)) {
                if (out == null) throw new IllegalStateException("Could not open image output");
                out.write(bytes);
            }
        }
        return new JSONObject().put("message", "Saved " + images.length() + " image(s) to Photos");
    }

    private boolean notifyLocal(JSONObject arg) throws Exception {
        String text = arg.getString("message");
        if (text.isEmpty() || text.length() > 500) throw new IllegalArgumentException("Invalid notification");
        if (Build.VERSION.SDK_INT >= 33 && checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
            if (arg.optBoolean("request")) requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS}, 72);
            return false;
        }
        NotificationManager manager = (NotificationManager) getSystemService(NOTIFICATION_SERVICE);
        manager.createNotificationChannel(new NotificationChannel(NOTIFICATIONS, "Frame Control reminders", NotificationManager.IMPORTANCE_DEFAULT));
        android.app.Notification notification = new android.app.Notification.Builder(this, NOTIFICATIONS)
                .setSmallIcon(android.R.drawable.ic_dialog_info).setContentTitle("Frame Control")
                .setContentText(text).setAutoCancel(true).build();
        manager.notify((int) System.currentTimeMillis(), notification);
        return true;
    }

    @Override protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode == PICK_FILE && fileCallback != null) {
            fileCallback.onReceiveValue(WebChromeClient.FileChooserParams.parseResult(resultCode, data));
            fileCallback = null;
        }
    }
    @Override public void onBackPressed() {
        if (web != null && web.canGoBack()) web.goBack(); else showSetup(null);
    }
    private void closeFrame() {
        if (web != null) { web.destroy(); web = null; }
        if (frame != null) { SshFrame old = frame; frame = null; old.close(); }
        localPort = 0;
    }
    @Override protected void onDestroy() {
        ++generation; closeFrame(); worker.shutdownNow(); super.onDestroy();
    }
}
