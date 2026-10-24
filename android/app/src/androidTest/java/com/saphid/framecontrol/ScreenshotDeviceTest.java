package com.saphid.framecontrol;

import static org.junit.Assert.*;

import android.app.Activity;
import android.app.Instrumentation;
import android.content.*;
import android.database.Cursor;
import android.graphics.*;
import android.net.Uri;
import android.provider.MediaStore;
import android.view.View;
import android.view.ViewGroup;
import android.widget.Button;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.*;
import java.util.concurrent.atomic.AtomicReference;
import org.junit.*;
import org.junit.runner.RunWith;

@RunWith(AndroidJUnit4.class)
public class ScreenshotDeviceTest {
  private Context context;
  private final Set<Uri> cleanup = new LinkedHashSet<>();

  @Before
  public void setup() {
    context = InstrumentationRegistry.getInstrumentation().getTargetContext();
  }

  @After
  public void cleanup() {
    for (Uri uri : cleanup) context.getContentResolver().delete(uri, null, null);
  }

  private String name(String headset, SyncEngine.Shot shot) throws Exception {
    String file = shot.id.substring(shot.id.lastIndexOf('/') + 1);
    int dot = file.lastIndexOf('.');
    return file.substring(0, dot)
        + "_"
        + FrameConnection.hash(headset + "/" + shot.id).substring(0, 20)
        + file.substring(dot);
  }

  private Uri row(String headset, SyncEngine.Shot shot) throws Exception {
    Uri collection = MediaStore.Images.Media.getContentUri(MediaStore.VOLUME_EXTERNAL_PRIMARY);
    @SuppressWarnings("deprecation")
    Uri includingPending = MediaStore.setIncludePending(collection);
    try (Cursor c =
        context
            .getContentResolver()
            .query(
                includingPending,
                new String[] {"_id"},
                MediaStore.Images.Media.DISPLAY_NAME
                    + "=? AND "
                    + MediaStore.Images.Media.RELATIVE_PATH
                    + "=?",
                new String[] {name(headset, shot), "Pictures/Frame Control/"},
                null)) {
      if (c != null && c.moveToFirst()) {
        Uri uri = ContentUris.withAppendedId(collection, c.getLong(0));
        cleanup.add(uri);
        assertFalse("Duplicate Gallery row", c.moveToNext());
        return uri;
      }
      return null;
    }
  }

  @Test
  public void actualGalleryOriginalAndAppOnlySurviveRelaunch() throws Exception {
    String headset = "instrumented-" + UUID.randomUUID();
    File root = new File(context.getFilesDir(), "instrumented/" + headset);
    Object gate = new Object();
    Bitmap bitmap = Bitmap.createBitmap(48, 32, Bitmap.Config.ARGB_8888);
    bitmap.eraseColor(Color.rgb(25, 184, 143));
    ByteArrayOutputStream bytes = new ByteArrayOutputStream();
    bitmap.compress(Bitmap.CompressFormat.PNG, 100, bytes);
    bitmap.recycle();
    byte[] png = bytes.toByteArray();
    SyncEngine.Transport transport =
        new SyncEngine.Transport() {
          public void download(SyncEngine.Shot shot, File target) throws Exception {
            Files.write(target.toPath(), png);
          }

          public boolean validImage(File f) {
            Bitmap b = BitmapFactory.decodeFile(f.getPath());
            if (b == null) return false;
            b.recycle();
            return true;
          }
        };
    GalleryExporter exporter = new GalleryExporter(context, headset, gate);
    SyncEngine engine = new SyncEngine(root, true);
    engine.reconcile(Collections.emptyList(), transport, exporter);
    SyncEngine.Shot shot =
        new SyncEngine.Shot("999999999991/108/20261024000000_1.png", png.length, 1792800000);
    engine.reconcile(List.of(shot), transport, exporter);
    assertNull(row(headset, shot));
    engine.reconcile(List.of(shot), transport, exporter);
    Uri saved = row(headset, shot);
    assertNotNull(saved);
    try (InputStream in = context.getContentResolver().openInputStream(saved)) {
      assertArrayEquals(png, read(in));
    }
    assertEquals("saved", engine.items().get(0).destination);
    engine = new SyncEngine(root, true);
    engine.reconcile(List.of(shot), transport, exporter);
    assertEquals(saved, row(headset, shot));
    engine.setGallery(false);
    SyncEngine.Shot second =
        new SyncEngine.Shot("999999999991/108/20261024000001_1.png", png.length, 1792800001);
    engine.reconcile(List.of(shot, second), transport, exporter);
    engine.reconcile(List.of(shot, second), transport, exporter);
    engine.setGallery(true);
    engine = new SyncEngine(root, true);
    engine.reconcile(List.of(shot, second), transport, exporter);
    assertNull(row(headset, second));
    assertTrue(
        engine.items().stream()
            .anyMatch(
                i ->
                    i.shot.id.equals(second.id)
                        && i.destination.equals("appOnly")
                        && i.file.exists()));
  }

  @Test
  public void interruptedMediaStoreRowIsRewrittenWithoutDuplicate() throws Exception {
    String headset = "pending-" + UUID.randomUUID();
    SyncEngine.Shot shot =
        new SyncEngine.Shot("999999999992/108/20261024000002_1.png", 4, 1792800002);
    ContentValues values = new ContentValues();
    values.put(MediaStore.Images.Media.DISPLAY_NAME, name(headset, shot));
    values.put(MediaStore.Images.Media.RELATIVE_PATH, "Pictures/Frame Control/");
    values.put(MediaStore.Images.Media.MIME_TYPE, "image/png");
    values.put(MediaStore.Images.Media.IS_PENDING, 1);
    Uri pending =
        context
            .getContentResolver()
            .insert(
                MediaStore.Images.Media.getContentUri(MediaStore.VOLUME_EXTERNAL_PRIMARY), values);
    assertNotNull(pending);
    cleanup.add(pending);
    File file = File.createTempFile("gallery-proof", ".png", context.getCacheDir());
    byte[] original = {1, 2, 3, 4};
    Files.write(file.toPath(), original);
    GalleryExporter exporter = new GalleryExporter(context, headset, new Object());
    assertTrue(exporter.export(shot, file, () -> true));
    assertEquals(pending, row(headset, shot));
    assertTrue(exporter.export(shot, file, () -> true));
    assertEquals(pending, row(headset, shot));
    try (InputStream in = context.getContentResolver().openInputStream(pending)) {
      assertArrayEquals(original, read(in));
    }
    file.delete();
  }

  @Test
  public void galleryOptOutLatchesPreviouslyPairedLibraries() throws Exception {
    assertFalse("Instrumentation must own a stopped product", SyncService.running());
    File files = Files.createTempDirectory(context.getCacheDir().toPath(), "libraries-").toFile();
    String preferences = "library-test-" + UUID.randomUUID();
    Context isolated =
        new ContextWrapper(context) {
          @Override
          public File getFilesDir() {
            return files;
          }

          @Override
          public SharedPreferences getSharedPreferences(String name, int mode) {
            return context.getSharedPreferences(preferences, mode);
          }
        };
    try {
      SyncEngine.Transport transfer =
          new SyncEngine.Transport() {
            public void download(SyncEngine.Shot shot, File target) throws Exception {
              Files.write(target.toPath(), new byte[] {1, 2, 3, 4});
            }

            public boolean validImage(File file) {
              return true;
            }
          };
      SyncEngine.Exporter unavailable = (shot, file, eligible) -> false;
      SyncEngine.Shot shot = new SyncEngine.Shot("123/108/20261024120000_1.png", 4, 100);
      File a = SyncService.library(isolated, "headset-a");
      File b = SyncService.library(isolated, "headset-b");
      for (File root : List.of(a, b)) {
        SyncEngine engine = new SyncEngine(root, true);
        engine.reconcile(Collections.emptyList(), transfer, unavailable);
        engine.reconcile(List.of(shot), transfer, unavailable);
        engine.reconcile(List.of(shot), transfer, unavailable);
        assertEquals("pending", engine.items().get(0).destination);
      }
      assertTrue(
          SyncService.prefs(isolated)
              .edit()
              .putString("pin", "headset-b")
              .putBoolean("gallery", true)
              .commit());
      SyncService.gallery(isolated, false);
      SyncService.gallery(isolated, true);
      for (File root : List.of(a, b)) {
        SyncEngine engine = new SyncEngine(root, true);
        assertEquals("appOnly", engine.items().get(0).destination);
        engine.reconcile(
            List.of(shot),
            transfer,
            (s, f, eligible) -> {
              fail("Opted-out items must never be exported after re-pairing");
              return false;
            });
      }
    } finally {
      SyncService.prefs(isolated).edit().clear().commit();
      try (java.util.stream.Stream<java.nio.file.Path> paths = Files.walk(files.toPath())) {
        for (java.nio.file.Path path :
            paths.sorted(Comparator.reverseOrder()).collect(java.util.stream.Collectors.toList()))
          Files.delete(path);
      }
    }
  }

  @Test
  public void changingHeadsetsRebindsShareToTheSelectedOriginal() throws Exception {
    assertFalse(SyncService.running());
    String aPin = "switch-a-" + UUID.randomUUID(), bPin = "switch-b-" + UUID.randomUUID();
    File a = SyncService.library(context, aPin), b = SyncService.library(context, bPin);
    SharedPreferences prefs = SyncService.prefs(context);
    String previousPin = prefs.getString("pin", null);
    boolean previousGallery = prefs.getBoolean("gallery", true);
    Instrumentation instrumentation = InstrumentationRegistry.getInstrumentation();
    AtomicReference<Intent> shared = new AtomicReference<>();
    Instrumentation.ActivityMonitor monitor =
        new Instrumentation.ActivityMonitor() {
          @Override
          public Instrumentation.ActivityResult onStartActivity(Intent intent) {
            if (!Intent.ACTION_CHOOSER.equals(intent.getAction())) return null;
            shared.set(intent.getParcelableExtra(Intent.EXTRA_INTENT));
            return new Instrumentation.ActivityResult(Activity.RESULT_CANCELED, null);
          }
        };
    Activity activity = null;
    try {
      SyncEngine.Shot shot = new SyncEngine.Shot("123/108/20261024120000_1.png", 4, 100);
      for (File root : List.of(a, b)) {
        byte[] original = root.equals(a) ? new byte[] {1, 2, 3, 4} : new byte[] {5, 6, 7, 8};
        SyncEngine.Transport transfer =
            new SyncEngine.Transport() {
              public void download(SyncEngine.Shot s, File file) throws Exception {
                Files.write(file.toPath(), original);
              }

              public boolean validImage(File file) {
                return true;
              }
            };
        SyncEngine engine = new SyncEngine(root, false);
        engine.reconcile(Collections.emptyList(), transfer, (s, f, e) -> false);
        engine.reconcile(List.of(shot), transfer, (s, f, e) -> false);
        engine.reconcile(List.of(shot), transfer, (s, f, e) -> false);
      }
      assertTrue(prefs.edit().putString("pin", aPin).putBoolean("gallery", false).commit());
      activity =
          instrumentation.startActivitySync(
              new Intent(context, MainActivity.class)
                  .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TASK));
      instrumentation.addMonitor(monitor);
      instrumentation.waitForIdleSync();
      Activity screen = activity;
      Runnable share =
          () -> {
            Button button = shareButton(screen.findViewById(android.R.id.content));
            assertNotNull("The downloaded original must be reachable", button);
            assertTrue(button.performClick());
          };
      instrumentation.runOnMainSync(share);
      assertNotNull(shared.get());
      Uri first = shared.get().getParcelableExtra(Intent.EXTRA_STREAM);
      try (InputStream in = context.getContentResolver().openInputStream(first)) {
        assertArrayEquals(new byte[] {1, 2, 3, 4}, read(in));
      }
      assertTrue(prefs.edit().putString("pin", bPin).commit());
      long deadline = System.nanoTime() + java.util.concurrent.TimeUnit.SECONDS.toNanos(5);
      Uri selected;
      do {
        instrumentation.runOnMainSync(share);
        selected = shared.get().getParcelableExtra(Intent.EXTRA_STREAM);
        if (!first.equals(selected)) break;
        Thread.sleep(100);
      } while (System.nanoTime() < deadline);
      assertNotEquals("Share must no longer target the previous headset", first, selected);
      try (InputStream in = context.getContentResolver().openInputStream(selected)) {
        assertArrayEquals(new byte[] {5, 6, 7, 8}, read(in));
      }
    } finally {
      instrumentation.removeMonitor(monitor);
      Activity screen = activity;
      if (screen != null) instrumentation.runOnMainSync(screen::finish);
      SharedPreferences.Editor restore = prefs.edit().putBoolean("gallery", previousGallery);
      if (previousPin == null) restore.remove("pin");
      else restore.putString("pin", previousPin);
      assertTrue(restore.commit());
      for (File root : List.of(a, b)) {
        if (!root.exists()) continue;
        try (java.util.stream.Stream<java.nio.file.Path> paths = Files.walk(root.toPath())) {
          for (java.nio.file.Path path :
              paths.sorted(Comparator.reverseOrder()).collect(java.util.stream.Collectors.toList()))
            Files.delete(path);
        }
      }
    }
  }

  private static Button shareButton(View view) {
    if (view instanceof Button && "Open / share original".contentEquals(((Button) view).getText()))
      return (Button) view;
    if (view instanceof ViewGroup) {
      ViewGroup group = (ViewGroup) view;
      for (int i = 0; i < group.getChildCount(); i++) {
        Button found = shareButton(group.getChildAt(i));
        if (found != null) return found;
      }
    }
    return null;
  }

  /** Optional real-headset provisioning. Only this test APK exposes the hook. */
  @Test
  public void provisionRealHeadsetIfRequested() throws Exception {
    android.os.Bundle args = InstrumentationRegistry.getArguments();
    Assume.assumeTrue("Optional real-headset provisioning", "true".equals(args.getString("live")));
    String host = args.getString("host"), pin = args.getString("pin");
    assertNotNull(host);
    assertNotNull(pin);
    assertEquals(
        "Probe must return the expected host key before authentication",
        pin,
        FrameConnection.probe(host, 22, "steamos"));
    String publicKey = new PhoneIdentity().authorizedKey(SyncService.install(context));
    Files.write(
        new File(context.getFilesDir(), "live-test-public.pub").toPath(),
        (publicKey + "\n").getBytes(StandardCharsets.US_ASCII));
    assertTrue(
        SyncService.prefs(context)
            .edit()
            .putString("host", host)
            .putString("user", "steamos")
            .putInt("port", 22)
            .putString("pin", pin)
            .commit());
  }

  @Test
  public void verifyRealHeadsetIfRequested() throws Exception {
    android.os.Bundle args = InstrumentationRegistry.getArguments();
    String id = args.getString("verifyId");
    Assume.assumeNotNull(id);
    String pin = SyncService.prefs(context).getString("pin", null);
    assertNotNull(pin);
    SyncEngine engine =
        new SyncEngine(
            SyncService.library(context, pin),
            SyncService.prefs(context).getBoolean("gallery", true));
    SyncEngine.Item item =
        engine.items().stream().filter(i -> i.shot.id.equals(id)).findFirst().orElseThrow();
    assertTrue(item.file.exists());
    String expected = args.getString("sha256");
    assertNotNull(expected);
    assertEquals(expected, sha(Files.readAllBytes(item.file.toPath())));
    boolean gallery = "true".equals(args.getString("gallery"));
    Uri saved = row(pin, item.shot);
    cleanup.clear();
    if (gallery) {
      assertEquals("saved", item.destination);
      assertNotNull(saved);
      try (InputStream in = context.getContentResolver().openInputStream(saved)) {
        assertEquals(expected, sha(read(in)));
      }
    } else {
      assertEquals("appOnly", item.destination);
      assertNull(saved);
    }
  }

  private static String sha(byte[] bytes) throws Exception {
    StringBuilder out = new StringBuilder();
    for (byte b : java.security.MessageDigest.getInstance("SHA-256").digest(bytes))
      out.append(String.format(java.util.Locale.ROOT, "%02x", b & 255));
    return out.toString();
  }

  private static byte[] read(InputStream input) throws IOException {
    ByteArrayOutputStream out = new ByteArrayOutputStream();
    byte[] b = new byte[4096];
    int n;
    while ((n = input.read(b)) != -1) out.write(b, 0, n);
    return out.toByteArray();
  }
}
