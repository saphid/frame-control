package com.saphid.framecontrol;

import android.app.*;
import android.content.*;
import android.content.pm.ServiceInfo;
import android.os.*;
import java.io.File;
import java.util.*;
import java.util.concurrent.*;

/** Explicit user-started connected-device session, with a visible Stop action. */
public final class SyncService extends Service {
  static final String CHANNEL = "headset-sync";
  static final Object SETTINGS_LOCK = new Object();
  private static final int NOTIFICATION = 108;
  private static final SessionGate GATE = new SessionGate();
  private static volatile SyncService instance;
  private final ExecutorService worker = Executors.newSingleThreadExecutor();
  private long session;
  private volatile boolean stopping;
  private volatile FrameConnection connection;
  private volatile SyncEngine engine;
  private volatile String pin;

  static SharedPreferences prefs(Context c) {
    return c.getSharedPreferences("frame", MODE_PRIVATE);
  }

  static String state() {
    return GATE.state();
  }

  static String page() {
    return GATE.page();
  }

  static boolean running() {
    SyncService service = instance;
    return service != null && !service.stopping && GATE.active(service.session);
  }

  static String install(Context c) {
    SharedPreferences p = prefs(c);
    String id = p.getString("install", null);
    if (id == null) {
      id = UUID.randomUUID().toString();
      if (!p.edit().putString("install", id).commit())
        throw new IllegalStateException("Could not save this phone's identity.");
    }
    return id;
  }

  static File library(Context c, String pin) throws Exception {
    return new File(c.getFilesDir(), "screenshots/" + FrameConnection.hash(pin));
  }

  static void gallery(Context c, boolean value) throws Exception {
    synchronized (SETTINGS_LOCK) {
      SyncService service = instance;
      // Journal first: a failed disk write must not appear as a saved setting.
      String pin = prefs(c).getString("pin", null);
      SyncEngine live = service == null ? null : service.engine;
      // A closed engine belongs to a stopped session; update its library from disk instead.
      if (live != null && !live.setGallery(value)) live = null;
      if (!value) {
        // The setting is global. Latch the opt-out in every retained library,
        // including headsets that are not currently paired or connected.
        File libraries = new File(c.getFilesDir(), "screenshots");
        if (libraries.exists()) {
          File[] roots = libraries.listFiles();
          if (roots == null) throw new java.io.IOException("Could not read screenshot libraries.");
          File activeRoot = live != null && pin != null ? library(c, pin) : null;
          for (File root : roots) {
            if (!root.getName().matches("[0-9a-f]{64}")) continue;
            if (activeRoot != null && root.equals(activeRoot)) continue;
            new SyncEngine(root, false).setGallery(false);
          }
        }
      } else if (live == null && pin != null) {
        new SyncEngine(library(c, pin), true).setGallery(true);
      }
      if (!prefs(c).edit().putBoolean("gallery", value).commit())
        throw new java.io.IOException("Could not save the Gallery setting.");
      // Interrupted exports can leave hidden pending rows; app-only receipts never retry them.
      if (!value) GalleryExporter.discardPending(c);
    }
  }

  /** Read-only, for a background thread. Never creates or rewrites a library. */
  static List<SyncEngine.Item> items(Context c, String pin) throws Exception {
    if (pin == null) return Collections.emptyList();
    SyncService service = instance;
    SyncEngine live = service == null ? null : service.engine;
    if (live != null && !live.isClosed() && pin.equals(service.pin)) return live.items();
    return SyncEngine.snapshot(library(c, pin));
  }

  @Override
  public void onCreate() {
    super.onCreate();
    session = GATE.begin();
    instance = this;
    stopping = false;
    NotificationManager manager = getSystemService(NotificationManager.class);
    manager.createNotificationChannel(
        new NotificationChannel(
            CHANNEL, "Headset screenshot sync", NotificationManager.IMPORTANCE_LOW));
  }

  private Notification notification(String message) {
    PendingIntent open =
        PendingIntent.getActivity(
            this,
            0,
            new Intent(this, MainActivity.class),
            PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);
    PendingIntent stop =
        PendingIntent.getService(
            this,
            1,
            new Intent(this, SyncService.class).setAction("STOP"),
            PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);
    return new Notification.Builder(this, CHANNEL)
        .setSmallIcon(com.saphid.framecontrol.R.drawable.ic_frame)
        .setContentTitle("Frame Control")
        .setContentText(message)
        .setContentIntent(open)
        .setOngoing(true)
        .addAction(new Notification.Action.Builder(null, "Stop syncing", stop).build())
        .build();
  }

  /** A stale worker cannot reach the notification once its session has ended. */
  private void status(String text) {
    GATE.status(
        session,
        text,
        t -> getSystemService(NotificationManager.class).notify(NOTIFICATION, notification(t)));
  }

  @Override
  public int onStartCommand(Intent intent, int flags, int startId) {
    if (intent != null && "STOP".equals(intent.getAction())) {
      stopSelf();
      return START_NOT_STICKY;
    }
    if (connection != null || stopping) return START_NOT_STICKY;
    String text = "Connecting to headset";
    GATE.status(session, text, null);
    if (Build.VERSION.SDK_INT >= 34)
      startForeground(
          NOTIFICATION, notification(text), ServiceInfo.FOREGROUND_SERVICE_TYPE_CONNECTED_DEVICE);
    else startForeground(NOTIFICATION, notification(text));
    connection = new FrameConnection(this);
    worker.execute(this::runSession);
    return START_NOT_STICKY;
  }

  private void runSession() {
    try {
      SharedPreferences p = prefs(this);
      String pin = p.getString("pin", null);
      if (pin == null) throw new java.io.IOException("Pair with your headset first.");
      SyncEngine created;
      synchronized (SETTINGS_LOCK) {
        boolean gallery = p.getBoolean("gallery", true);
        created = new SyncEngine(library(this, pin), gallery);
        // Retry cleanup of hidden rows if an earlier opt-out's cleanup was interrupted.
        if (!gallery) GalleryExporter.discardPending(this);
        this.pin = pin;
        engine = created;
      }
      // Pairs with onDestroy: it sets stopping before reading engine.
      if (stopping) created.close();
      while (!stopping) {
        try {
          FrameConnection active = new FrameConnection(this);
          connection = active;
          if (stopping) break;
          status("Connecting to headset");
          active.connect(
              p.getString("host", ""),
              p.getInt("port", 22),
              p.getString("user", "steamos"),
              pin,
              install(this));
          if (stopping) {
            active.close();
            break;
          }
          GATE.page(session, active.page());
          status("Syncing new screenshots");
          GalleryExporter exporter = new GalleryExporter(this, pin, SETTINGS_LOCK);
          while (!stopping && active.connected()) {
            try {
              SyncEngine.Listing listing = active.listing();
              created.reconcile(listing, active, exporter);
              status(progress(listing, created.skipped()));
            } catch (Exception e) {
              status("Screenshot pending · " + message(e));
            }
            Thread.sleep(4000);
          }
          if (!stopping) throw new java.io.IOException("Connection lost. Reconnecting…");
        } catch (Exception e) {
          GATE.page(session, null);
          FrameConnection c = connection;
          if (c != null) c.close();
          if (stopping) break;
          status("Waiting for headset · " + message(e));
          Thread.sleep(10000);
        }
      }
    } catch (InterruptedException ignored) {
      Thread.currentThread().interrupt();
    } catch (Exception e) {
      GATE.status(session, message(e), null);
    } finally {
      GATE.page(session, null);
      FrameConnection c = connection;
      if (c != null) c.close();
      // Only a still-current session may stop the service; Stop already ended a stale one.
      GATE.ifActive(session, this::stopSelf);
    }
  }

  static String progress(SyncEngine.Listing listing, int skipped) {
    if (listing.accounts.isEmpty()) return "Waiting for a Steam account on the headset";
    String text = "Syncing new screenshots";
    if (skipped == 1) text += " · 1 file skipped (empty or over 30 MB)";
    else if (skipped > 1) text += " · " + skipped + " files skipped (empty or over 30 MB)";
    return text;
  }

  static String message(Exception e) {
    String text = e.getMessage();
    if (text == null || text.trim().isEmpty()) return "Try reconnecting.";
    if (text.contains("HostKey")
        || text.contains("HostKey has been changed")
        || text.contains("reject HostKey")) return "Headset identity changed. Stop and pair again.";
    if (text.contains("Auth fail")) return "Headset login refused. Pair again.";
    return text.length() > 180 ? text.substring(0, 180) : text;
  }

  @Override
  public void onDestroy() {
    stopping = true;
    // After this, the old worker cannot post status, page or notification updates.
    GATE.end(session);
    SyncEngine live = engine;
    if (live != null) live.close();
    FrameConnection c = connection;
    if (c != null) c.close();
    worker.shutdownNow();
    if (instance == this) instance = null;
    stopForeground(STOP_FOREGROUND_REMOVE);
    // Also clear a notification posted just before the gate closed.
    getSystemService(NotificationManager.class).cancel(NOTIFICATION);
    super.onDestroy();
  }

  @Override
  public IBinder onBind(Intent intent) {
    return null;
  }
}
