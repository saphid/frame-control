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
  private static volatile SyncService instance;
  private static volatile String state = "Disconnected";
  private static volatile String page;
  private final ExecutorService worker = Executors.newSingleThreadExecutor();
  private volatile boolean stopping;
  private volatile FrameConnection connection;
  private volatile SyncEngine engine;

  static SharedPreferences prefs(Context c) {
    return c.getSharedPreferences("frame", MODE_PRIVATE);
  }

  static String state() {
    return state;
  }

  static String page() {
    return page;
  }

  static boolean running() {
    SyncService service = instance;
    return service != null && !service.stopping;
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
      if (live != null) live.setGallery(value);
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
    }
  }

  static List<SyncEngine.Item> items(Context c) throws Exception {
    SyncService service = instance;
    if (service != null && service.engine != null) return service.engine.items();
    String pin = prefs(c).getString("pin", null);
    if (pin == null) return Collections.emptyList();
    synchronized (SETTINGS_LOCK) {
      return new SyncEngine(library(c, pin), prefs(c).getBoolean("gallery", true)).items();
    }
  }

  @Override
  public void onCreate() {
    super.onCreate();
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

  private void status(String text) {
    state = text;
    getSystemService(NotificationManager.class).notify(108, notification(text));
  }

  @Override
  public int onStartCommand(Intent intent, int flags, int startId) {
    if (intent != null && "STOP".equals(intent.getAction())) {
      stopSelf();
      return START_NOT_STICKY;
    }
    if (connection != null || stopping) return START_NOT_STICKY;
    state = "Connecting to headset";
    if (Build.VERSION.SDK_INT >= 34)
      startForeground(
          108, notification(state), ServiceInfo.FOREGROUND_SERVICE_TYPE_CONNECTED_DEVICE);
    else startForeground(108, notification(state));
    connection = new FrameConnection(this);
    worker.execute(this::runSession);
    return START_NOT_STICKY;
  }

  private void runSession() {
    try {
      SharedPreferences p = prefs(this);
      String pin = p.getString("pin", null);
      if (pin == null) throw new java.io.IOException("Pair with your headset first.");
      synchronized (SETTINGS_LOCK) {
        engine = new SyncEngine(library(this, pin), p.getBoolean("gallery", true));
      }
      while (!stopping) {
        try {
          FrameConnection active = new FrameConnection(this);
          connection = active;
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
          page = active.page();
          status("Syncing new screenshots");
          GalleryExporter exporter = new GalleryExporter(this, pin, SETTINGS_LOCK);
          while (!stopping && active.connected()) {
            try {
              engine.reconcile(active.shots(), active, exporter);
              status("Syncing new screenshots");
            } catch (Exception e) {
              status("Screenshot pending · " + message(e));
            }
            Thread.sleep(4000);
          }
          if (!stopping) throw new java.io.IOException("Connection lost. Reconnecting…");
        } catch (Exception e) {
          page = null;
          if (connection != null) connection.close();
          if (stopping) break;
          status("Waiting for headset · " + message(e));
          Thread.sleep(10000);
        }
      }
    } catch (InterruptedException ignored) {
      Thread.currentThread().interrupt();
    } catch (Exception e) {
      state = message(e);
    } finally {
      page = null;
      if (connection != null) connection.close();
      stopSelf();
    }
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
    page = null;
    if (engine != null) engine.stop();
    if (connection != null) connection.close();
    worker.shutdownNow();
    instance = null;
    if (state.equals("Syncing new screenshots")
        || state.startsWith("Waiting")
        || state.startsWith("Connecting")) state = "Disconnected";
    stopForeground(STOP_FOREGROUND_REMOVE);
    super.onDestroy();
  }

  @Override
  public IBinder onBind(Intent intent) {
    return null;
  }
}
