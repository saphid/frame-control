package com.saphid.framecontrol;

import static org.junit.Assert.*;

import android.app.Activity;
import android.app.Instrumentation;
import android.content.*;
import android.database.Cursor;
import android.graphics.*;
import android.net.Uri;
import android.provider.MediaStore;
import android.system.ErrnoException;
import android.system.Os;
import android.system.OsConstants;
import android.view.View;
import android.view.ViewGroup;
import android.widget.Button;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.*;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;
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

  /** Fixture Steam accounts exist on the simulated headset from the first poll. */
  private static SyncEngine.Listing listing(SyncEngine.Shot... shots) {
    return new SyncEngine.Listing(Set.of("123", "999999999991"), List.of(shots));
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
    engine.reconcile(listing(), transport, exporter);
    SyncEngine.Shot shot =
        new SyncEngine.Shot("999999999991/108/20261024000000_1.png", png.length, 1792800000);
    engine.reconcile(listing(shot), transport, exporter);
    assertNull(row(headset, shot));
    engine.reconcile(listing(shot), transport, exporter);
    Uri saved = row(headset, shot);
    assertNotNull(saved);
    try (InputStream in = context.getContentResolver().openInputStream(saved)) {
      assertArrayEquals(png, read(in));
    }
    assertEquals("saved", engine.items().get(0).destination);
    engine = new SyncEngine(root, true);
    engine.reconcile(listing(shot), transport, exporter);
    assertEquals(saved, row(headset, shot));
    engine.setGallery(false);
    SyncEngine.Shot second =
        new SyncEngine.Shot("999999999991/108/20261024000001_1.png", png.length, 1792800001);
    engine.reconcile(listing(shot, second), transport, exporter);
    engine.reconcile(listing(shot, second), transport, exporter);
    engine.setGallery(true);
    engine = new SyncEngine(root, true);
    engine.reconcile(listing(shot, second), transport, exporter);
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

  /**
   * Stop/restart overlap: a stopped session's exporter is still writing its pending row when the
   * next session exports the same screenshot. The old writer reads its original from a FIFO, so
   * it stays mid-write, with the row open, until the test supplies the bytes. Without the
   * process-wide export lock the next session publishes that row first and the old session's
   * cancellation then deletes it, leaving a "saved" receipt with no Gallery image.
   */
  @Test
  public void stoppedSessionExportCannotDeleteNextSessionsGalleryImage() throws Exception {
    String headset = "handoff-" + UUID.randomUUID();
    Bitmap bitmap = Bitmap.createBitmap(16, 16, Bitmap.Config.ARGB_8888);
    bitmap.eraseColor(Color.rgb(184, 25, 143));
    ByteArrayOutputStream bytes = new ByteArrayOutputStream();
    bitmap.compress(Bitmap.CompressFormat.PNG, 100, bytes);
    bitmap.recycle();
    byte[] png = bytes.toByteArray();
    SyncEngine.Shot shot =
        new SyncEngine.Shot("999999999993/108/20261026000000_1.png", png.length, 1792900000);
    File original = File.createTempFile("handoff", ".png", context.getCacheDir());
    Files.write(original.toPath(), png);
    File fifo = new File(context.getCacheDir(), "handoff-" + UUID.randomUUID() + ".fifo");
    Os.mkfifo(fifo.getPath(), 0600);
    // Both sessions share one settings lock, as both use SyncService.SETTINGS_LOCK.
    Object settings = new Object();
    GalleryExporter stopped = new GalleryExporter(context, headset, settings);
    GalleryExporter next = new GalleryExporter(context, headset, settings);
    AtomicBoolean stoppedSessionCurrent = new AtomicBoolean(true);
    AtomicReference<Object> stoppedResult = new AtomicReference<>();
    AtomicReference<Object> nextResult = new AtomicReference<>();
    Thread old =
        exporting(stoppedResult, () -> stopped.export(shot, fifo, stoppedSessionCurrent::get));
    Thread successor = null;
    FileDescriptor writer = null;
    try {
      old.start();
      writer = openWriter(fifo, old);
      // The old export has inserted its pending row and waits for the original's bytes.
      stoppedSessionCurrent.set(false); // Stop closed the old engine.
      successor = exporting(nextResult, () -> next.export(shot, original, () -> true));
      successor.start();
      Thread waiting = successor;
      // Fixed: the successor queues behind the old export. Former code: it publishes and ends.
      long deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(20);
      while (waiting.isAlive() && !GalleryExporter.EXPORTS.hasQueuedThread(waiting)) {
        assertTrue("The next session neither waited nor finished", System.nanoTime() < deadline);
        Thread.sleep(10);
      }
      int written = Os.write(writer, png, 0, png.length);
      assertEquals(png.length, written);
    } finally {
      // An exporter blocked opening the FIFO is not interruptible; a writer's EOF releases it.
      if (writer == null) {
        try {
          writer = Os.open(fifo.getPath(), OsConstants.O_WRONLY | OsConstants.O_NONBLOCK, 0);
        } catch (ErrnoException ignored) {
          // No reader is waiting.
        }
      }
      if (writer != null) Os.close(writer);
      join(old);
      if (successor != null) join(successor);
      fifo.delete();
      original.delete();
      try {
        row(headset, shot); // Registers whatever row a failed run left for cleanup.
      } catch (Throwable ignored) {
        // Cleanup only; the assertions below report the outcome.
      }
    }
    assertEquals("The stopped session must not save", Boolean.FALSE, result(stoppedResult));
    assertEquals("The next session must save", Boolean.TRUE, result(nextResult));
    Uri saved = row(headset, shot);
    assertNotNull("The next session's Gallery image must survive the old callback", saved);
    @SuppressWarnings("deprecation")
    Uri includingPending = MediaStore.setIncludePending(saved);
    try (Cursor c =
        context
            .getContentResolver()
            .query(
                includingPending,
                new String[] {MediaStore.Images.Media.IS_PENDING},
                null,
                null,
                null)) {
      assertTrue(c != null && c.moveToFirst());
      assertEquals("The Gallery image must be published", 0, c.getInt(0));
    }
    try (InputStream in = context.getContentResolver().openInputStream(saved)) {
      assertArrayEquals(png, read(in));
    }
  }

  private interface Export {
    boolean run() throws Exception;
  }

  private static Thread exporting(AtomicReference<Object> result, Export export) {
    return new Thread(
        () -> {
          try {
            result.set(export.run());
          } catch (Throwable e) {
            result.set(e);
          }
        },
        "handoff-export");
  }

  /** Opens the FIFO's write end once the exporter has opened its read end; bounded. */
  private static FileDescriptor openWriter(File fifo, Thread reader) throws Exception {
    long deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(20);
    while (true) {
      try {
        return Os.open(fifo.getPath(), OsConstants.O_WRONLY | OsConstants.O_NONBLOCK, 0);
      } catch (ErrnoException e) {
        if (e.errno != OsConstants.ENXIO) throw e; // ENXIO: no reader yet.
      }
      assertTrue("The old export ended before reading its original", reader.isAlive());
      assertTrue("The old export never started reading", System.nanoTime() < deadline);
      Thread.sleep(10);
    }
  }

  private static void join(Thread thread) throws InterruptedException {
    thread.join(TimeUnit.SECONDS.toMillis(60));
    if (thread.isAlive()) thread.interrupt();
    assertFalse("Export thread did not finish", thread.isAlive());
  }

  private static Object result(AtomicReference<Object> result) {
    Object value = result.get();
    if (value instanceof Throwable) throw new AssertionError("Export failed", (Throwable) value);
    return value;
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
      // A retained library still in the version 1 format (no account set), never polled since.
      File legacy = SyncService.library(isolated, "headset-legacy");
      assertTrue(legacy.mkdirs());
      Files.write(
          new File(legacy, "receipts.json").toPath(),
          ("{\"version\":1,\"initialized\":true,\"gallery\":true,\"records\":{\""
                  + shot.id
                  + "\":{\"shot\":{\"id\":\""
                  + shot.id
                  + "\",\"size\":4,\"time\":100},\"state\":\"queued\",\"observations\":2,"
                  + "\"destination\":\"pending\"}}}")
              .getBytes(StandardCharsets.UTF_8));
      for (File root : List.of(a, b)) {
        SyncEngine engine = new SyncEngine(root, true);
        engine.reconcile(listing(), transfer, unavailable);
        engine.reconcile(listing(shot), transfer, unavailable);
        engine.reconcile(listing(shot), transfer, unavailable);
        assertEquals("pending", engine.items().get(0).destination);
      }
      assertTrue(
          SyncService.prefs(isolated)
              .edit()
              .putString("pin", "headset-b")
              .putBoolean("gallery", true)
              .commit());
      SyncService.gallery(isolated, false);
      // The latched legacy journal must stay readable immediately, by the screen and an engine.
      assertEquals("appOnly", SyncEngine.snapshot(legacy).get(0).destination);
      assertEquals("appOnly", new SyncEngine(legacy, false).items().get(0).destination);
      SyncService.gallery(isolated, true);
      for (File root : List.of(a, b, legacy)) {
        SyncEngine engine = new SyncEngine(root, true);
        assertEquals("appOnly", engine.items().get(0).destination);
        engine.reconcile(
            listing(shot),
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
        engine.reconcile(listing(), transfer, (s, f, e) -> false);
        engine.reconcile(listing(shot), transfer, (s, f, e) -> false);
        engine.reconcile(listing(shot), transfer, (s, f, e) -> false);
      }
      assertTrue(prefs.edit().putString("pin", aPin).putBoolean("gallery", false).commit());
      activity =
          instrumentation.startActivitySync(
              new Intent(context, MainActivity.class)
                  .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TASK));
      instrumentation.addMonitor(monitor);
      Activity screen = activity;
      // The library loads on a background executor, so wait for it to render, not for idle.
      Uri first = shareWhenRendered(instrumentation, screen, shared, null);
      try (InputStream in = context.getContentResolver().openInputStream(first)) {
        assertArrayEquals(new byte[] {1, 2, 3, 4}, read(in));
      }
      assertTrue(prefs.edit().putString("pin", bPin).commit());
      // Until the screen notices the new pin it may still share A; it then clears A's list
      // (no button while B loads) and shows only B's original.
      Uri selected = shareWhenRendered(instrumentation, screen, shared, first);
      try (InputStream in = context.getContentResolver().openInputStream(selected)) {
        assertArrayEquals(new byte[] {5, 6, 7, 8}, read(in));
      }
      // Once B is shown, A's list is gone: one button, and sharing again still targets B.
      AtomicReference<Integer> buttons = new AtomicReference<>();
      shared.set(null);
      instrumentation.runOnMainSync(
          () -> {
            View content = screen.findViewById(android.R.id.content);
            buttons.set(shareButtons(content));
            Button button = shareButton(content);
            if (button != null) assertTrue(button.performClick());
          });
      assertEquals("The previous headset's original must be gone", Integer.valueOf(1), buttons.get());
      assertNotNull(shared.get());
      assertEquals(selected, shared.get().getParcelableExtra(Intent.EXTRA_STREAM));
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

  /**
   * Clicks the share button once the asynchronously loaded library shows one and the chosen
   * original differs from {@code previous}. A missing button is the expected loading state.
   */
  private static Uri shareWhenRendered(
      Instrumentation instrumentation,
      Activity screen,
      AtomicReference<Intent> shared,
      Uri previous)
      throws InterruptedException {
    long deadline = System.nanoTime() + java.util.concurrent.TimeUnit.SECONDS.toNanos(15);
    do {
      shared.set(null);
      instrumentation.runOnMainSync(
          () -> {
            Button button = shareButton(screen.findViewById(android.R.id.content));
            if (button != null) assertTrue(button.performClick());
          });
      Intent sent = shared.get();
      if (sent != null) {
        Uri uri = sent.getParcelableExtra(Intent.EXTRA_STREAM);
        assertNotNull(uri);
        if (!uri.equals(previous)) return uri;
      }
      // Re-check after the screen's next refresh or library load; bounded by the deadline.
      Thread.sleep(50);
    } while (System.nanoTime() < deadline);
    fail("The selected headset's original never became shareable");
    return null;
  }

  private static int shareButtons(View view) {
    if (view instanceof Button && "Open / share original".contentEquals(((Button) view).getText()))
      return 1;
    int count = 0;
    if (view instanceof ViewGroup) {
      ViewGroup group = (ViewGroup) view;
      for (int i = 0; i < group.getChildCount(); i++) count += shareButtons(group.getChildAt(i));
    }
    return count;
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

  private Uri insert(String name, boolean pending, byte[] bytes) throws Exception {
    ContentResolver resolver = context.getContentResolver();
    ContentValues values = new ContentValues();
    values.put(MediaStore.Images.Media.DISPLAY_NAME, name);
    values.put(MediaStore.Images.Media.RELATIVE_PATH, GalleryExporter.FOLDER);
    values.put(MediaStore.Images.Media.MIME_TYPE, "image/png");
    values.put(MediaStore.Images.Media.IS_PENDING, 1);
    Uri uri =
        resolver.insert(
            MediaStore.Images.Media.getContentUri(MediaStore.VOLUME_EXTERNAL_PRIMARY), values);
    assertNotNull(uri);
    cleanup.add(uri);
    try (OutputStream out = resolver.openOutputStream(uri, "wt")) {
      out.write(bytes);
    }
    if (!pending) {
      ContentValues done = new ContentValues();
      done.put(MediaStore.Images.Media.IS_PENDING, 0);
      assertEquals(1, resolver.update(uri, done, null, null));
    }
    return uri;
  }

  private boolean exists(Uri uri) {
    @SuppressWarnings("deprecation")
    Uri includingPending = MediaStore.setIncludePending(uri);
    try (Cursor c =
        context.getContentResolver().query(includingPending, new String[] {"_id"}, null, null, null)) {
      return c != null && c.moveToFirst();
    }
  }

  @Test
  public void optOutDiscardsInterruptedPendingRowsButKeepsPublishedImages() throws Exception {
    assertFalse(SyncService.running());
    File files = Files.createTempDirectory(context.getCacheDir().toPath(), "pending-").toFile();
    String preferences = "pending-test-" + UUID.randomUUID();
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
      Bitmap bitmap = Bitmap.createBitmap(8, 8, Bitmap.Config.ARGB_8888);
      ByteArrayOutputStream bytes = new ByteArrayOutputStream();
      bitmap.compress(Bitmap.CompressFormat.PNG, 100, bytes);
      bitmap.recycle();
      // A pending row with app-only receipts, from a retained (not currently paired) library.
      SyncEngine.Shot shot = new SyncEngine.Shot("123/108/20261024120003_1.png", 4, 100);
      SyncEngine engine = new SyncEngine(SyncService.library(isolated, "retained"), true);
      engine.reconcile(listing(), null, null);
      Uri interrupted = insert(name("retained", shot), true, bytes.toByteArray());
      Uri published = insert("published-" + UUID.randomUUID() + ".png", false, bytes.toByteArray());
      assertTrue(SyncService.prefs(isolated).edit().putBoolean("gallery", true).commit());
      SyncService.gallery(isolated, false);
      assertFalse("Hidden pending row must not outlive the opt-out", exists(interrupted));
      // Proven deleted by the product; deleting it again throws SecurityException on API 30+.
      cleanup.remove(interrupted);
      assertTrue("A published Gallery image must stay", exists(published));
      SyncService.gallery(isolated, true);
      assertTrue(exists(published));
      assertFalse(exists(interrupted));
    } finally {
      SyncService.prefs(isolated).edit().clear().commit();
      try (java.util.stream.Stream<java.nio.file.Path> paths = Files.walk(files.toPath())) {
        for (java.nio.file.Path path :
            paths.sorted(Comparator.reverseOrder()).collect(java.util.stream.Collectors.toList()))
          Files.delete(path);
      }
    }
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
    // Read-only: verification must not rewrite the product's journal.
    SyncEngine.Item item =
        SyncEngine.snapshot(SyncService.library(context, pin)).stream().filter(i -> i.shot.id.equals(id)).findFirst().orElseThrow();
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
