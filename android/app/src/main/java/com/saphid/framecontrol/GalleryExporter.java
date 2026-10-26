package com.saphid.framecontrol;

import android.content.*;
import android.database.Cursor;
import android.net.Uri;
import android.provider.MediaStore;
import java.io.*;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.locks.ReentrantLock;
import java.util.function.BooleanSupplier;

/** Deterministic, app-owned MediaStore rows make interrupted exports retryable. */
final class GalleryExporter implements SyncEngine.Exporter {
  static final String FOLDER = "Pictures/Frame Control/";

  /**
   * Serializes every export in the process, across exporter instances and service sessions. A
   * stopped session's exporter may still be writing when a new session starts; without this, the
   * new one could publish the same deterministic row and the old one's cancellation would then
   * delete it. Lock order is EXPORTS, then the settings lock. Never take EXPORTS while holding
   * the settings lock: {@link #discardPending} runs under it and must not wait for exports.
   */
  static final ReentrantLock EXPORTS = new ReentrantLock();

  private static final long EXPORT_WAIT_SECONDS = 30;
  private final Context context;
  private final String headset;
  private final Object settingsLock;

  GalleryExporter(Context context, String headset, Object settingsLock) {
    this.context = context.getApplicationContext();
    this.headset = headset;
    this.settingsLock = settingsLock;
  }

  /**
   * Best-effort removal of this app's hidden pending rows in the Frame Control folder. Only an
   * interrupted export leaves one; published (non-pending) images are never touched. Callers
   * hold the settings lock, so no export can be publishing a row at the same time.
   */
  static int discardPending(Context context) {
    ContentResolver resolver = context.getContentResolver();
    Uri collection = MediaStore.Images.Media.getContentUri(MediaStore.VOLUME_EXTERNAL_PRIMARY);
    @SuppressWarnings("deprecation")
    Uri includingPending = MediaStore.setIncludePending(collection);
    List<Uri> rows = new ArrayList<>();
    int removed = 0;
    try {
      try (Cursor cursor =
          resolver.query(
              includingPending,
              new String[] {"_id"},
              MediaStore.Images.Media.IS_PENDING
                  + "=1 AND "
                  + MediaStore.Images.Media.RELATIVE_PATH
                  + "=? AND "
                  + MediaStore.Images.Media.OWNER_PACKAGE_NAME
                  + "=?",
              new String[] {FOLDER, context.getPackageName()},
              null)) {
        while (cursor != null && cursor.moveToNext())
          rows.add(ContentUris.withAppendedId(collection, cursor.getLong(0)));
      }
      for (Uri row : rows) removed += resolver.delete(row, null, null);
    } catch (RuntimeException ignored) {
      // Android 11+ also expires abandoned pending rows; never fail the setting change here.
    }
    return removed;
  }

  @Override
  public boolean export(SyncEngine.Shot shot, File file, BooleanSupplier eligible)
      throws Exception {
    // Interruptible and bounded: Stop still ends a waiting session, and a stuck earlier write
    // only delays this item to a later poll.
    if (!EXPORTS.tryLock(EXPORT_WAIT_SECONDS, TimeUnit.SECONDS))
      throw new IOException("Gallery is still finishing an earlier save.");
    try {
      return exportLocked(shot, file, eligible);
    } finally {
      EXPORTS.unlock();
    }
  }

  private boolean exportLocked(SyncEngine.Shot shot, File file, BooleanSupplier eligible)
      throws Exception {
    String name = shot.id.substring(shot.id.lastIndexOf('/') + 1);
    int dot = name.lastIndexOf('.');
    name =
        name.substring(0, dot)
            + "_"
            + FrameConnection.hash(headset + "/" + shot.id).substring(0, 20)
            + name.substring(dot);
    String folder = FOLDER;
    ContentResolver resolver = context.getContentResolver();
    Uri collection = MediaStore.Images.Media.getContentUri(MediaStore.VOLUME_EXTERNAL_PRIMARY);
    // API 29 excludes even app-owned pending rows unless explicitly included.
    @SuppressWarnings("deprecation")
    Uri recoveryCollection = MediaStore.setIncludePending(collection);
    Uri row = null;
    boolean pending = true;
    try (Cursor cursor =
        resolver.query(
            recoveryCollection,
            new String[] {"_id", MediaStore.Images.Media.IS_PENDING},
            MediaStore.Images.Media.DISPLAY_NAME
                + "=? AND "
                + MediaStore.Images.Media.RELATIVE_PATH
                + "=? AND "
                + MediaStore.Images.Media.OWNER_PACKAGE_NAME
                + "=?",
            new String[] {name, folder, context.getPackageName()},
            null)) {
      if (cursor != null && cursor.moveToFirst()) {
        row = ContentUris.withAppendedId(collection, cursor.getLong(0));
        pending = cursor.getInt(1) != 0;
      }
    }
    // A completed row is the commit receipt, including a crash before JSON save.
    if (row != null && !pending) return true;
    if (!eligible.getAsBoolean()) return false;
    if (row == null) {
      ContentValues values = new ContentValues();
      values.put(MediaStore.Images.Media.DISPLAY_NAME, name);
      values.put(MediaStore.Images.Media.RELATIVE_PATH, folder);
      values.put(
          MediaStore.Images.Media.MIME_TYPE, shot.id.endsWith(".png") ? "image/png" : "image/jpeg");
      values.put(MediaStore.Images.Media.IS_PENDING, 1);
      values.put(MediaStore.Images.Media.DATE_TAKEN, (long) (shot.time * 1000));
      row = resolver.insert(collection, values);
      if (row == null) throw new IOException("Gallery could not create the screenshot.");
    }
    try {
      try (InputStream in = new FileInputStream(file);
          OutputStream out = resolver.openOutputStream(row, "wt")) {
        if (out == null) throw new IOException("Gallery could not open the screenshot.");
        byte[] b = new byte[65536];
        int n;
        while ((n = in.read(b)) != -1) out.write(b, 0, n);
      }
      synchronized (settingsLock) {
        if (!eligible.getAsBoolean()) {
          // Holding EXPORTS, no other exporter can have published this row since we found it.
          resolver.delete(row, null, null);
          return false;
        }
        ContentValues done = new ContentValues();
        done.put(MediaStore.Images.Media.IS_PENDING, 0);
        if (resolver.update(row, done, null, null) != 1)
          throw new IOException("Gallery could not finish saving the screenshot.");
      }
      return true;
    } catch (Exception e) {
      // A pending row is retained and rewritten on retry. A completed row is
      // discovered before any future insert, even after process death.
      throw e;
    }
  }
}
