package com.saphid.framecontrol;

import android.content.*;
import android.database.Cursor;
import android.net.Uri;
import android.provider.MediaStore;
import java.io.*;
import java.util.function.BooleanSupplier;

/** Deterministic, app-owned MediaStore rows make interrupted exports retryable. */
final class GalleryExporter implements SyncEngine.Exporter {
  private final Context context;
  private final String headset;
  private final Object settingsLock;

  GalleryExporter(Context context, String headset, Object settingsLock) {
    this.context = context.getApplicationContext();
    this.headset = headset;
    this.settingsLock = settingsLock;
  }

  @Override
  public boolean export(SyncEngine.Shot shot, File file, BooleanSupplier eligible)
      throws Exception {
    String name = shot.id.substring(shot.id.lastIndexOf('/') + 1);
    int dot = name.lastIndexOf('.');
    name =
        name.substring(0, dot)
            + "_"
            + FrameConnection.hash(headset + "/" + shot.id).substring(0, 20)
            + name.substring(dot);
    String folder = "Pictures/Frame Control/";
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
