package com.saphid.framecontrol;

import android.Manifest;
import android.app.*;
import android.content.*;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.net.Uri;
import android.os.*;
import android.text.InputType;
import android.view.*;
import android.webkit.*;
import android.widget.*;
import androidx.core.content.FileProvider;
import java.util.*;
import java.util.concurrent.*;

public final class MainActivity extends Activity {
  private final ExecutorService network = Executors.newSingleThreadExecutor();
  // Journal parsing and file checks stay off the main thread.
  private final ExecutorService library = Executors.newSingleThreadExecutor();
  private boolean loading;
  private String renderedPin;
  private final Handler handler = new Handler(Looper.getMainLooper());
  private LinearLayout root, downloads;
  private FrameLayout content;
  private ScrollView companion;
  private EditText host, port, user;
  private TextView status, empty;
  private Switch gallery;
  private Button pair, connect, stop;
  private WebView web;
  private String loadedPage, librarySignature = "";
  private int downloadLimit = 100;
  private boolean busy, visible, controls;
  private ValueCallback<Uri[]> fileSelection;
  private static final int INK = Color.rgb(232, 240, 238),
      MUTED = Color.rgb(164, 183, 179),
      ACCENT = Color.rgb(124, 216, 195);
  private static final String EMPTY =
      "Pair and start syncing. Existing headset screenshots stay on the headset; new captures"
          + " will appear here.";
  private final Runnable refresh =
      new Runnable() {
        public void run() {
          if (!visible) return;
          update();
          handler.postDelayed(this, 1500);
        }
      };

  private int dp(int n) {
    return Math.round(getResources().getDisplayMetrics().density * n);
  }

  private TextView text(String value, int size, int color) {
    TextView v = new TextView(this);
    v.setText(value);
    v.setTextSize(size);
    v.setTextColor(color);
    v.setPadding(0, dp(6), 0, dp(6));
    return v;
  }

  private Button button(String label, Runnable action) {
    Button b = new Button(this);
    b.setText(label);
    b.setAllCaps(false);
    b.setOnClickListener(v -> action.run());
    return b;
  }

  private EditText field(String label, String value, int type) {
    companionBody.addView(text(label, 13, MUTED));
    EditText v = new EditText(this);
    v.setSingleLine(true);
    v.setText(value);
    v.setHint(label);
    v.setContentDescription(label);
    v.setInputType(type);
    v.setTextColor(INK);
    v.setSaveEnabled(false);
    companionBody.addView(v);
    return v;
  }

  private LinearLayout companionBody;

  @Override
  public void onCreate(Bundle state) {
    super.onCreate(state);
    root = new LinearLayout(this);
    root.setOrientation(LinearLayout.VERTICAL);
    root.setBackgroundColor(Color.rgb(17, 24, 25));
    root.setPadding(dp(20), dp(12), dp(20), dp(12));
    root.setOnApplyWindowInsetsListener(
        (v, insets) -> {
          if (Build.VERSION.SDK_INT >= 30) {
            android.graphics.Insets i =
                insets.getInsets(
                    WindowInsets.Type.systemBars() | WindowInsets.Type.displayCutout());
            v.setPadding(dp(20) + i.left, dp(12) + i.top, dp(20) + i.right, dp(12) + i.bottom);
          } else
            v.setPadding(
                dp(20) + insets.getSystemWindowInsetLeft(),
                dp(12) + insets.getSystemWindowInsetTop(),
                dp(20) + insets.getSystemWindowInsetRight(),
                dp(12) + insets.getSystemWindowInsetBottom());
          return insets;
        });
    root.addView(text("FRAME CONTROL", 13, ACCENT));
    root.addView(text("Your headset, closer.", 27, INK));
    status = text(SyncService.state(), 14, MUTED);
    status.setAccessibilityLiveRegion(View.ACCESSIBILITY_LIVE_REGION_POLITE);
    root.addView(status);
    LinearLayout tabs = new LinearLayout(this);
    tabs.addView(
        button("Screenshots", () -> show(false)), new LinearLayout.LayoutParams(0, dp(48), 1));
    tabs.addView(
        button("Headset controls", () -> show(true)), new LinearLayout.LayoutParams(0, dp(48), 1));
    root.addView(tabs);
    content = new FrameLayout(this);
    root.addView(content, new LinearLayout.LayoutParams(-1, 0, 1));
    companion = new ScrollView(this);
    companion.setFillViewport(true);
    companionBody = new LinearLayout(this);
    companionBody.setOrientation(LinearLayout.VERTICAL);
    companion.addView(companionBody);
    SharedPreferences p = SyncService.prefs(this);
    companionBody.addView(text("Connect your Steam Frame", 20, INK));
    companionBody.addView(
        text(
            "Enable Developer Mode and connect to the same network, or use your headset’s Tailscale"
                + " address.",
            14,
            MUTED));
    host =
        field(
            "Headset address",
            p.getString("host", "frame.local"),
            InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_URI);
    port = field("SSH port", Integer.toString(p.getInt("port", 22)), InputType.TYPE_CLASS_NUMBER);
    user =
        field(
            "SSH username",
            p.getString("user", "steamos"),
            InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_VISIBLE_PASSWORD);
    pair = button("Pair headset", this::probe);
    companionBody.addView(pair);
    LinearLayout actions = new LinearLayout(this);
    connect = button("Start syncing", this::startSync);
    stop = button("Stop", () -> stopService(new Intent(this, SyncService.class)));
    actions.addView(connect, new LinearLayout.LayoutParams(0, dp(52), 1));
    actions.addView(stop, new LinearLayout.LayoutParams(0, dp(52), 1));
    companionBody.addView(actions);
    companionBody.addView(text("Screenshot downloads", 20, INK));
    gallery = new Switch(this);
    gallery.setText("Save screenshots to Gallery");
    gallery.setTextColor(INK);
    gallery.setTextSize(16);
    gallery.setMinHeight(dp(56));
    gallery.setChecked(p.getBoolean("gallery", true));
    gallery.setOnCheckedChangeListener(
        (b, value) -> {
          try {
            SyncService.gallery(this, value);
            librarySignature = "";
          } catch (Exception e) {
            gallery.setOnCheckedChangeListener(null);
            gallery.setChecked(!value);
            error(SyncService.message(e));
            recreate();
          }
        });
    companionBody.addView(gallery);
    companionBody.addView(
        text(
            "New captures download automatically while sync is running. A notification keeps the"
                + " connection visible. Stop syncing to disconnect. Android may delay transfers"
                + " while the phone is locked or in battery-saving modes.",
            14,
            MUTED));
    companionBody.addView(
        text(
            "Turning Gallery off keeps new downloads in this app. Turning it on again won’t export"
                + " earlier app-only downloads.",
            14,
            MUTED));
    empty = text(EMPTY, 14, MUTED);
    companionBody.addView(empty);
    downloads = new LinearLayout(this);
    downloads.setOrientation(LinearLayout.VERTICAL);
    companionBody.addView(downloads);
    show(false);
    setContentView(root);
  }

  private void show(boolean useControls) {
    controls = useControls;
    content.removeAllViews();
    if (!controls) {
      content.addView(companion, new FrameLayout.LayoutParams(-1, -1));
      return;
    }
    String page = SyncService.page();
    if (page == null) {
      loadedPage = null;
      if (web != null) web.loadUrl("about:blank");
      content.addView(text("Start syncing to open your headset’s controls.", 17, MUTED));
      return;
    }
    if (web == null) {
      web = new WebView(this);
      web.setBackgroundColor(Color.rgb(17, 24, 25));
      WebSettings settings = web.getSettings();
      settings.setJavaScriptEnabled(true);
      settings.setDomStorageEnabled(true);
      settings.setAllowFileAccess(false);
      settings.setAllowContentAccess(false);
      settings.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
      settings.setSaveFormData(false);
      web.setWebViewClient(
          new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
              Uri url = request.getUrl();
              Uri origin = Uri.parse(loadedPage == null ? "" : loadedPage);
              if ("http".equals(url.getScheme())
                  && "127.0.0.1".equals(url.getHost())
                  && url.getPort() == origin.getPort()) return false;
              if (request.hasGesture()
                  && ("https".equals(url.getScheme()) || "http".equals(url.getScheme()))) {
                try {
                  startActivity(new Intent(Intent.ACTION_VIEW, url));
                } catch (ActivityNotFoundException ignored) {
                }
              }
              return true;
            }
          });
      web.setWebChromeClient(
          new WebChromeClient() {
            @Override
            public boolean onShowFileChooser(
                WebView w, ValueCallback<Uri[]> callback, FileChooserParams params) {
              if (fileSelection != null) fileSelection.onReceiveValue(null);
              fileSelection = callback;
              Intent choose =
                  new Intent(Intent.ACTION_OPEN_DOCUMENT)
                      .setType("*/*")
                      .addCategory(Intent.CATEGORY_OPENABLE);
              choose.putExtra(
                  Intent.EXTRA_ALLOW_MULTIPLE,
                  params.getMode() == FileChooserParams.MODE_OPEN_MULTIPLE);
              try {
                startActivityForResult(choose, 110);
              } catch (ActivityNotFoundException e) {
                fileSelection.onReceiveValue(null);
                fileSelection = null;
                return false;
              }
              return true;
            }
          });
      web.setDownloadListener(
          (url, ua, disposition, mime, length) -> {
            show(false);
            Toast.makeText(
                    this,
                    "New screenshot originals are in Screenshot downloads.",
                    Toast.LENGTH_LONG)
                .show();
          });
    }
    content.addView(web, new FrameLayout.LayoutParams(-1, -1));
    if (!page.equals(loadedPage)) {
      loadedPage = page;
      web.loadUrl(page);
    }
  }

  @Override
  protected void onActivityResult(int request, int result, Intent data) {
    super.onActivityResult(request, result, data);
    if (request == 110 && fileSelection != null) {
      fileSelection.onReceiveValue(WebChromeClient.FileChooserParams.parseResult(result, data));
      fileSelection = null;
    }
  }

  private void update() {
    if (!busy) status.setText(SyncService.state());
    boolean paired = SyncService.prefs(this).contains("pin");
    boolean running = SyncService.running();
    connect.setEnabled(paired && !busy && !running);
    pair.setEnabled(!busy && !running);
    stop.setEnabled(!busy && running);
    host.setEnabled(!running && !busy);
    port.setEnabled(!running && !busy);
    user.setEnabled(!running && !busy);
    if (controls && !Objects.equals(loadedPage, SyncService.page())) show(true);
    String pin = SyncService.prefs(this).getString("pin", null);
    if (!Objects.equals(pin, renderedPin)) {
      // Never leave another headset's originals shareable while the new library loads.
      renderedPin = pin;
      librarySignature = "";
      downloads.removeAllViews();
      empty.setText(EMPTY);
      empty.setVisibility(View.VISIBLE);
    }
    if (loading) return;
    loading = true;
    library.execute(
        () -> {
          List<SyncEngine.Item> items = null;
          Set<SyncEngine.Item> present = new HashSet<>();
          Exception failure = null;
          try {
            items = SyncService.items(this, pin);
            for (SyncEngine.Item item : items) if (item.file.exists()) present.add(item);
          } catch (Exception e) {
            failure = e;
          }
          List<SyncEngine.Item> loaded = items;
          Exception error = failure;
          runOnUiThread(
              () -> {
                loading = false;
                if (isFinishing() || isDestroyed()) return;
                // A result for a previously paired headset is discarded; the next tick reloads.
                if (!Objects.equals(pin, SyncService.prefs(this).getString("pin", null))) return;
                if (error != null) {
                  librarySignature = "";
                  empty.setVisibility(View.VISIBLE);
                  empty.setText("Could not read screenshot downloads: " + SyncService.message(error));
                  return;
                }
                render(loaded, present);
              });
        });
  }

  private void render(List<SyncEngine.Item> items, Set<SyncEngine.Item> present) {
    StringBuilder signature = new StringBuilder();
    for (var item : items)
      signature
          .append(item.file.getAbsolutePath())
          .append('|')
          .append(item.destination)
          .append('|')
          .append(present.contains(item))
          .append('\n');
    if (signature.toString().equals(librarySignature)) return;
    librarySignature = signature.toString();
    downloads.removeAllViews();
    empty.setText(EMPTY);
    empty.setVisibility(items.isEmpty() ? View.VISIBLE : View.GONE);
    int shown = 0;
    for (SyncEngine.Item item : items) {
      if (shown++ >= downloadLimit) {
        downloads.addView(
            button(
                "Show 100 more downloads",
                () -> {
                  downloadLimit += 100;
                  librarySignature = "";
                  update();
                }));
        break;
      }
      String label = item.shot.id.substring(item.shot.id.lastIndexOf('/') + 1);
      LinearLayout card = new LinearLayout(this);
      card.setOrientation(LinearLayout.VERTICAL);
      card.setPadding(0, dp(12), 0, dp(12));
      card.addView(text(label, 16, INK));
      String where =
          item.destination.equals("saved")
              ? "Saved to Gallery"
              : item.destination.equals("appOnly") ? "In Frame Control" : "Gallery save pending";
      boolean exists = present.contains(item);
      if (!exists) where = "Download pending";
      card.addView(text(where + " · Game " + item.shot.id.split("/")[1], 13, MUTED));
      if (exists) card.addView(button("Open / share original", () -> share(item)));
      downloads.addView(card);
    }
  }

  private void share(SyncEngine.Item item) {
    Uri uri = FileProvider.getUriForFile(this, getPackageName() + ".files", item.file);
    Intent send =
        new Intent(Intent.ACTION_SEND)
            .setType(item.shot.id.endsWith(".png") ? "image/png" : "image/jpeg")
            .putExtra(Intent.EXTRA_STREAM, uri)
            .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
    startActivity(Intent.createChooser(send, "Screenshot original"));
  }

  private void startSync() {
    if (Build.VERSION.SDK_INT >= 33
        && checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS)
            != PackageManager.PERMISSION_GRANTED) {
      requestPermissions(new String[] {Manifest.permission.POST_NOTIFICATIONS}, 108);
      return;
    }
    startForegroundService(new Intent(this, SyncService.class));
  }

  @Override
  public void onRequestPermissionsResult(int request, String[] permissions, int[] grants) {
    super.onRequestPermissionsResult(request, permissions, grants);
    if (request == 108) {
      if (grants.length > 0 && grants[0] == PackageManager.PERMISSION_GRANTED)
        startForegroundService(new Intent(this, SyncService.class));
      else
        error(
            "Allow notifications in Android Settings to start a visible screenshot sync session.");
    }
  }

  private void probe() {
    final String address = host.getText().toString().trim(),
        username = user.getText().toString().trim();
    final int sshPort;
    try {
      sshPort = Integer.parseInt(port.getText().toString());
    } catch (NumberFormatException e) {
      error("Enter an SSH port from 1 to 65535.");
      return;
    }
    stopService(new Intent(this, SyncService.class));
    busy = true;
    pair.setEnabled(false);
    status.setText("Checking headset identity…");
    network.execute(
        () -> {
          try {
            String pin = FrameConnection.probe(address, sshPort, username);
            String fingerprint = FrameConnection.fingerprint(pin);
            runOnUiThread(
                () -> {
                  if (isFinishing() || isDestroyed()) return;
                  busy = false;
                  new AlertDialog.Builder(this)
                      .setTitle("Trust this headset?")
                      .setMessage(
                          address
                              + ":"
                              + sshPort
                              + "\n\n"
                              + fingerprint
                              + "\n\n"
                              + "Compare this SSH fingerprint with your headset before entering its"
                              + " Developer Mode password.")
                      .setNegativeButton("Cancel", null)
                      .setPositiveButton(
                          "Trust and pair", (d, w) -> password(address, sshPort, username, pin))
                      .show();
                });
          } catch (Exception e) {
            runOnUiThread(
                () -> {
                  busy = false;
                  error(SyncService.message(e));
                });
          }
        });
  }

  private void password(String address, int sshPort, String username, String pin) {
    EditText password = new EditText(this);
    password.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_PASSWORD);
    password.setHint("Developer Mode password");
    password.setSaveEnabled(false);
    new AlertDialog.Builder(this)
        .setTitle("Pair with " + address)
        .setMessage(
            "Used once to authorize this phone’s protected SSH key. The password is not saved.")
        .setView(password)
        .setNegativeButton("Cancel", (d, w) -> password.setText(""))
        .setPositiveButton(
            "Pair",
            (d, w) -> {
              String secret = password.getText().toString();
              password.setText("");
              busy = true;
              status.setText("Pairing this phone…");
              network.execute(
                  () -> {
                    try {
                      FrameConnection.pair(
                          address, sshPort, username, pin, secret, SyncService.install(this));
                      if (!SyncService.prefs(this)
                          .edit()
                          .putString("host", address)
                          .putInt("port", sshPort)
                          .putString("user", username)
                          .putString("pin", pin)
                          .commit()) throw new java.io.IOException("Could not save pairing.");
                      runOnUiThread(
                          () -> {
                            busy = false;
                            status.setText("Paired. Start syncing when you’re ready.");
                            update();
                          });
                    } catch (Exception e) {
                      runOnUiThread(
                          () -> {
                            busy = false;
                            error(SyncService.message(e));
                          });
                    }
                  });
            })
        .show();
  }

  private void error(String message) {
    if (isFinishing() || isDestroyed()) return;
    new AlertDialog.Builder(this)
        .setTitle("Frame Control")
        .setMessage(message)
        .setPositiveButton("OK", null)
        .show();
  }

  @Override
  protected void onResume() {
    super.onResume();
    visible = true;
    if (web != null) web.onResume();
    handler.post(refresh);
  }

  @Override
  protected void onPause() {
    visible = false;
    handler.removeCallbacks(refresh);
    if (web != null) web.onPause();
    super.onPause();
  }

  @Override
  protected void onDestroy() {
    network.shutdownNow();
    library.shutdownNow();
    if (fileSelection != null) fileSelection.onReceiveValue(null);
    if (web != null) {
      web.destroy();
      web = null;
    }
    super.onDestroy();
  }
}
