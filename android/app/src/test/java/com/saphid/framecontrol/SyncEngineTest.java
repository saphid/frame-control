package com.saphid.framecontrol;

import org.junit.Rule;
import org.junit.Test;
import org.junit.rules.TemporaryFolder;

import java.io.File;
import java.io.IOException;
import java.io.RandomAccessFile;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.List;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicReference;

import static org.junit.Assert.*;

public class SyncEngineTest {
    @Rule public TemporaryFolder temporary = new TemporaryFolder();

    private static final String FIRST = "123/456/20261024120000_1.jpg";
    private static final String SECOND = "123/456/20261024120001_2.png";
    private static final SyncEngine.Shot A = shot(FIRST);
    private static final SyncEngine.Shot B = shot(SECOND);

    private static SyncEngine.Shot shot(String id) { return new SyncEngine.Shot(id, 4, 100.5); }

    private static class Transfer implements SyncEngine.Transport {
        final List<String> downloads = new ArrayList<>();
        boolean valid = true;
        boolean truncated;

        @Override public void download(SyncEngine.Shot shot, File destination) throws Exception {
            downloads.add(shot.id);
            try (RandomAccessFile file = new RandomAccessFile(destination, "rw")) {
                file.setLength(truncated ? shot.size - 1 : shot.size);
            }
        }

        @Override public boolean validImage(File file) throws Exception { return valid; }
    }

    private static class Gallery implements SyncEngine.Exporter {
        int attempts;
        int saves;
        boolean deny;
        boolean fail;

        @Override public boolean export(SyncEngine.Shot shot, File original,
                                        java.util.function.BooleanSupplier eligible) throws Exception {
            attempts++;
            assertTrue(original.isFile());
            if (fail) throw new IOException("Gallery unavailable");
            if (deny || !eligible.getAsBoolean()) return false;
            saves++;
            return true;
        }
    }

    private interface Checked { void run() throws Exception; }

    private static IOException fails(Checked operation) throws Exception {
        try {
            operation.run();
        } catch (IOException expected) {
            return expected;
        }
        throw new AssertionError("Expected operation to reject invalid or unavailable state");
    }

    private static void reconcile(SyncEngine engine, Transfer transfer, Gallery gallery,
                                  SyncEngine.Shot... shots) throws Exception {
        engine.reconcile(Arrays.asList(shots), transfer, gallery);
    }

    private static void observed(SyncEngine engine, Transfer transfer, Gallery gallery,
                                 SyncEngine.Shot shot) throws Exception {
        reconcile(engine, transfer, gallery);
        reconcile(engine, transfer, gallery, shot);
    }

    private static void assertDownloadPending(SyncEngine engine, String destination) {
        assertEquals(1, engine.items().size());
        assertEquals(destination, engine.items().get(0).destination);
        assertFalse(engine.items().get(0).file.exists());
    }

    private static SyncEngine.Item item(SyncEngine engine, String id) {
        return engine.items().stream().filter(i -> i.shot.id.equals(id)).findFirst().get();
    }

    private static void await(CountDownLatch latch) throws InterruptedException {
        assertTrue("Timed out waiting for callback", latch.await(5, TimeUnit.SECONDS));
    }

    private static final class Async implements AutoCloseable {
        private final AtomicReference<Throwable> failure = new AtomicReference<>();
        private final Thread thread;

        Async(Checked operation) {
            thread = new Thread(() -> {
                try { operation.run(); } catch (Throwable e) { failure.set(e); }
            }, "sync-core-test");
            thread.start();
        }

        void finish() throws Exception {
            thread.join(5000);
            assertFalse("Reconcile did not finish", thread.isAlive());
            if (failure.get() != null) throw new AssertionError("Background reconcile failed", failure.get());
        }

        @Override public void close() throws Exception {
            if (thread.isAlive()) thread.interrupt();
            thread.join(5000);
            assertFalse("Leaked reconcile thread", thread.isAlive());
        }
    }

    @Test public void firstListingIsDurableBaselineAndNeverDownloadsHistory() throws Exception {
        File root = temporary.newFolder();
        Transfer transfer = new Transfer(); Gallery gallery = new Gallery();
        SyncEngine engine = new SyncEngine(root, true);
        reconcile(engine, transfer, gallery, A);
        assertTrue(new File(root, "receipts.json").isFile());
        engine = new SyncEngine(root, true);
        reconcile(engine, transfer, gallery, A);
        reconcile(engine, transfer, gallery, new SyncEngine.Shot(FIRST, 7, 999));
        assertTrue(transfer.downloads.isEmpty());
        assertTrue(engine.items().isEmpty());
    }

    @Test public void emptyBaselineRequiresTwoIdenticalNewObservations() throws Exception {
        SyncEngine engine = new SyncEngine(temporary.newFolder(), true);
        Transfer transfer = new Transfer(); Gallery gallery = new Gallery();
        observed(engine, transfer, gallery, A);
        assertTrue(transfer.downloads.isEmpty());
        assertDownloadPending(engine, "pending");
        reconcile(engine, transfer, gallery, A);
        assertEquals(Collections.singletonList(FIRST), transfer.downloads);
        assertEquals(1, gallery.saves);
        assertEquals("saved", engine.items().get(0).destination);
        assertEquals(4, engine.items().get(0).file.length());
    }

    @Test public void sizeAndMtimeChangesResetStabilityAndMissingPollBreaksIt() throws Exception {
        SyncEngine engine = new SyncEngine(temporary.newFolder(), false);
        Transfer transfer = new Transfer(); Gallery gallery = new Gallery();
        observed(engine, transfer, gallery, A);
        SyncEngine.Shot size = new SyncEngine.Shot(FIRST, 5, A.time);
        SyncEngine.Shot time = new SyncEngine.Shot(FIRST, 5, A.time + 1);
        reconcile(engine, transfer, gallery, size);
        reconcile(engine, transfer, gallery, time);
        reconcile(engine, transfer, gallery);
        reconcile(engine, transfer, gallery, time);
        assertTrue(transfer.downloads.isEmpty());
        reconcile(engine, transfer, gallery, time);
        assertEquals(1, transfer.downloads.size());
        assertEquals(5, engine.items().get(0).file.length());
    }

    @Test public void identityIncludesAccountAndAppAndDuplicateRowsAreOnlyOneObservation() throws Exception {
        SyncEngine engine = new SyncEngine(temporary.newFolder(), false);
        Transfer transfer = new Transfer(); Gallery gallery = new Gallery();
        reconcile(engine, transfer, gallery, A);
        SyncEngine.Shot otherAccount = shot("124/456/20261024120000_1.jpg");
        SyncEngine.Shot otherApp = shot("123/457/20261024120000_1.jpg");
        reconcile(engine, transfer, gallery, A, otherAccount, otherAccount, otherApp);
        assertTrue(transfer.downloads.isEmpty());
        reconcile(engine, transfer, gallery, otherAccount, otherApp);
        assertEquals(2, transfer.downloads.size());
        assertEquals(2, engine.items().size());
        reconcile(engine, transfer, gallery, otherAccount, otherApp);
        assertEquals(2, transfer.downloads.size());
    }

    @Test public void truncatedAndInvalidImagesStayQueuedUntilValidRetry() throws Exception {
        File root = temporary.newFolder();
        SyncEngine engine = new SyncEngine(root, true);
        Transfer transfer = new Transfer(); Gallery gallery = new Gallery();
        observed(engine, transfer, gallery, A);
        transfer.truncated = true;
        fails(() -> reconcile(engine, transfer, gallery, A));
        assertDownloadPending(engine, "pending");
        assertFalse(new File(root, "originals/" + FIRST).exists());
        transfer.truncated = false; transfer.valid = false;
        fails(() -> reconcile(engine, transfer, gallery, A));
        assertDownloadPending(engine, "pending");
        assertEquals(0, gallery.attempts);
        transfer.valid = true;
        reconcile(engine, transfer, gallery, A);
        assertEquals(3, transfer.downloads.size());
        assertEquals("saved", engine.items().get(0).destination);
        assertEquals(0, root.listFiles((dir, name) -> name.startsWith(".download-")).length);
    }

    @Test public void deniedExportRetriesWithoutDownloadingAndSavedReceiptDeduplicates() throws Exception {
        File root = temporary.newFolder();
        SyncEngine engine = new SyncEngine(root, true);
        Transfer transfer = new Transfer(); Gallery gallery = new Gallery();
        observed(engine, transfer, gallery, A);
        gallery.deny = true;
        reconcile(engine, transfer, gallery, A);
        assertEquals("pending", engine.items().get(0).destination);
        engine = new SyncEngine(root, true);
        gallery.deny = false;
        reconcile(engine, transfer, gallery); // Export retry does not need the remote file still listed.
        assertEquals(1, transfer.downloads.size());
        assertEquals(1, gallery.saves);
        reconcile(new SyncEngine(root, true), transfer, gallery, A);
        assertEquals(2, gallery.attempts);
    }

    @Test public void thrownExportRetainsPendingReceiptAcrossRelaunch() throws Exception {
        File root = temporary.newFolder();
        SyncEngine engine = new SyncEngine(root, true);
        Transfer transfer = new Transfer(); Gallery gallery = new Gallery();
        observed(engine, transfer, gallery, A);
        gallery.fail = true;
        fails(() -> reconcile(engine, transfer, gallery, A));
        assertEquals("pending", engine.items().get(0).destination);
        gallery.fail = false;
        reconcile(new SyncEngine(root, true), transfer, gallery);
        assertEquals(1, gallery.saves);
        assertEquals(1, transfer.downloads.size());
    }

    @Test public void queuedShotAndStabilitySurviveRelaunch() throws Exception {
        File root = temporary.newFolder();
        SyncEngine engine = new SyncEngine(root, false);
        Transfer transfer = new Transfer(); Gallery gallery = new Gallery();
        observed(engine, transfer, gallery, A);
        transfer.truncated = true;
        fails(() -> reconcile(engine, transfer, gallery, A));
        SyncEngine relaunched = new SyncEngine(root, true);
        transfer.truncated = false;
        reconcile(relaunched, transfer, gallery, A);
        assertEquals("appOnly", relaunched.items().get(0).destination);
        assertEquals(0, gallery.attempts);
    }

    @Test public void firstObservationSurvivesRelaunch() throws Exception {
        File root = temporary.newFolder();
        Transfer transfer = new Transfer(); Gallery gallery = new Gallery();
        observed(new SyncEngine(root, false), transfer, gallery, A);
        SyncEngine engine = new SyncEngine(root, false);
        reconcile(engine, transfer, gallery, A);
        assertEquals(1, engine.items().size());
    }

    @Test public void offThenOnNeverRetroExportsDownloadedOrQueuedItems() throws Exception {
        SyncEngine engine = new SyncEngine(temporary.newFolder(), true);
        Transfer transfer = new Transfer(); Gallery gallery = new Gallery();
        observed(engine, transfer, gallery, A);
        gallery.deny = true;
        reconcile(engine, transfer, gallery, A);
        engine.setGallery(false);
        engine.setGallery(true);
        gallery.deny = false;
        reconcile(engine, transfer, gallery, A, B);
        assertEquals("appOnly", engine.items().get(0).destination);
        reconcile(engine, transfer, gallery, A, B);
        assertEquals(1, gallery.saves); // Only the later B item.
        assertEquals("appOnly", engine.items().stream().filter(i -> i.shot.id.equals(FIRST))
                .findFirst().get().destination);
    }

    @Test public void switchingOffWhileDownloadBlockedChangesItsDisposition() throws Exception {
        SyncEngine engine = new SyncEngine(temporary.newFolder(), true);
        CountDownLatch entered = new CountDownLatch(1), release = new CountDownLatch(1);
        Transfer transfer = new Transfer() {
            @Override public void download(SyncEngine.Shot shot, File file) throws Exception {
                entered.countDown(); await(release); super.download(shot, file);
            }
        };
        Gallery gallery = new Gallery();
        observed(engine, transfer, gallery, A);
        try (Async async = new Async(() -> reconcile(engine, transfer, gallery, A))) {
            try {
                await(entered);
                engine.setGallery(false); // Must finish while network is blocked.
                engine.setGallery(true);
            } finally { release.countDown(); }
            async.finish();
        }
        assertEquals("appOnly", engine.items().get(0).destination);
        assertEquals(0, gallery.attempts);
    }

    @Test public void switchingOffWhileExporterBlockedInvalidatesEligibility() throws Exception {
        SyncEngine engine = new SyncEngine(temporary.newFolder(), true);
        CountDownLatch entered = new CountDownLatch(1), release = new CountDownLatch(1);
        Gallery gallery = new Gallery() {
            @Override public boolean export(SyncEngine.Shot shot, File original,
                                            java.util.function.BooleanSupplier eligible) throws Exception {
                assertTrue(eligible.getAsBoolean());
                entered.countDown(); await(release);
                assertFalse(eligible.getAsBoolean());
                return false;
            }
        };
        Transfer transfer = new Transfer();
        observed(engine, transfer, gallery, A);
        try (Async async = new Async(() -> reconcile(engine, transfer, gallery, A))) {
            try { await(entered); engine.setGallery(false); engine.setGallery(true); }
            finally { release.countDown(); }
            async.finish();
        }
        assertEquals("appOnly", engine.items().get(0).destination);
    }

    @Test public void lateDownloadAfterStopCannotOverwriteFreshRunOrJournal() throws Exception {
        File root = temporary.newFolder();
        SyncEngine engine = new SyncEngine(root, true);
        CountDownLatch entered = new CountDownLatch(1), release = new CountDownLatch(1);
        Transfer slow = new Transfer() {
            @Override public void download(SyncEngine.Shot shot, File file) throws Exception {
                entered.countDown(); await(release);
                Files.write(file.toPath(), new byte[]{9, 9, 9, 9});
            }
        };
        Transfer fresh = new Transfer(); Gallery gallery = new Gallery();
        observed(engine, fresh, gallery, A);
        try (Async async = new Async(() -> reconcile(engine, slow, gallery, A))) {
            byte[] journal;
            try {
                await(entered); engine.stop(); engine.setGallery(false);
                reconcile(engine, fresh, gallery, A);
                journal = Files.readAllBytes(new File(root, "receipts.json").toPath());
            } finally { release.countDown(); }
            async.finish();
            assertArrayEquals(journal, Files.readAllBytes(new File(root, "receipts.json").toPath()));
        }
        assertArrayEquals(new byte[4], Files.readAllBytes(engine.items().get(0).file.toPath()));
        assertEquals("appOnly", new SyncEngine(root, true).items().get(0).destination);
    }

    @Test public void lateExportAfterStopDoesNotMarkFreshAppOnlyReceiptSaved() throws Exception {
        File root = temporary.newFolder();
        SyncEngine engine = new SyncEngine(root, true);
        Transfer transfer = new Transfer();
        CountDownLatch entered = new CountDownLatch(1), release = new CountDownLatch(1);
        Gallery delayed = new Gallery() {
            @Override public boolean export(SyncEngine.Shot shot, File original,
                                            java.util.function.BooleanSupplier eligible) throws Exception {
                entered.countDown(); await(release);
                assertFalse(eligible.getAsBoolean());
                return true; // Model a pre-stop external save whose callback arrived late.
            }
        };
        observed(engine, transfer, delayed, A);
        try (Async async = new Async(() -> reconcile(engine, transfer, delayed, A))) {
            byte[] journal;
            try {
                await(entered); engine.stop(); engine.setGallery(false);
                reconcile(engine, transfer, new Gallery(), A);
                journal = Files.readAllBytes(new File(root, "receipts.json").toPath());
            } finally { release.countDown(); }
            async.finish();
            assertArrayEquals(journal, Files.readAllBytes(new File(root, "receipts.json").toPath()));
        }
        assertEquals("appOnly", engine.items().get(0).destination);
    }

    @Test public void concurrentReconcileIsRejectedWithoutBlockingOnDownload() throws Exception {
        SyncEngine engine = new SyncEngine(temporary.newFolder(), false);
        CountDownLatch entered = new CountDownLatch(1), release = new CountDownLatch(1);
        Transfer slow = new Transfer() {
            @Override public void download(SyncEngine.Shot shot, File file) throws Exception {
                entered.countDown(); await(release); super.download(shot, file);
            }
        };
        Gallery gallery = new Gallery(); observed(engine, slow, gallery, A);
        try (Async async = new Async(() -> reconcile(engine, slow, gallery, A))) {
            try {
                await(entered);
                try { reconcile(engine, new Transfer(), gallery, A); fail("Concurrent run accepted"); }
                catch (IllegalStateException expected) { assertDownloadPending(engine, "appOnly"); }
            } finally { release.countDown(); }
            async.finish();
        }
    }

    @Test public void corruptedAndIncompleteJournalsFailClosed() throws Exception {
        for (String content : new String[]{"", "{", "null", "{}", "{\"gallery\":true}",
                "{\"version\":2,\"initialized\":true,\"gallery\":true,\"records\":{}}",
                "{\"version\":1,\"initialized\":true,\"gallery\":true,\"records\":{}} trailing"}) {
            File root = temporary.newFolder();
            File journal = new File(root, "receipts.json");
            Files.write(journal.toPath(), content.getBytes(StandardCharsets.UTF_8));
            fails(() -> new SyncEngine(root, true));
            assertEquals(content, new String(Files.readAllBytes(journal.toPath()), StandardCharsets.UTF_8));
        }
    }

    @Test public void damagedReceiptAndMissingOriginalFailClosed() throws Exception {
        File root = temporary.newFolder();
        Transfer transfer = new Transfer(); Gallery gallery = new Gallery();
        SyncEngine engine = new SyncEngine(root, false);
        observed(engine, transfer, gallery, A); reconcile(engine, transfer, gallery, A);
        File journal = new File(root, "receipts.json");
        String json = new String(Files.readAllBytes(journal.toPath()), StandardCharsets.UTF_8);
        for (String damaged : new String[]{json.replace("downloaded", "unknown"),
                json.replace("\"time\":100.5", "\"otherTime\":100.5"),
                json.replace("\"size\":4", "\"size\":0"),
                json.replace("\"time\":100.5", "\"time\":1e999")}) {
            Files.write(journal.toPath(), damaged.getBytes(StandardCharsets.UTF_8));
            fails(() -> new SyncEngine(root, false));
        }
        Files.write(journal.toPath(), json.getBytes(StandardCharsets.UTF_8));
        Files.delete(engine.items().get(0).file.toPath());
        fails(() -> new SyncEngine(root, false));
        Files.delete(journal.toPath());
        Files.write(new File(root, "originals/orphan").toPath(), new byte[]{1});
        fails(() -> new SyncEngine(root, false));
    }

    @Test public void invalidListingCannotEstablishBaselineOrPartiallyAdvanceObservations() throws Exception {
        File root = temporary.newFolder();
        SyncEngine engine = new SyncEngine(root, false);
        Transfer transfer = new Transfer(); Gallery gallery = new Gallery();
        fails(() -> reconcile(engine, transfer, gallery, A, shot("../bad")));
        reconcile(engine, transfer, gallery, A); // A is still baseline, not newly discovered.
        reconcile(engine, transfer, gallery, A, B);
        fails(() -> reconcile(engine, transfer, gallery, B, shot("../bad")));
        assertTrue(transfer.downloads.isEmpty());
        reconcile(engine, transfer, gallery, B);
        assertEquals(Collections.singletonList(SECOND), transfer.downloads);
    }

    @Test public void metadataBoundsAndPathTraversalAreRejected() throws Exception {
        SyncEngine engine = new SyncEngine(temporary.newFolder(), false);
        Transfer transfer = new Transfer(); Gallery gallery = new Gallery();
        for (String id : new String[]{"../" + FIRST, "/" + FIRST, "123/../" + FIRST,
                "123\\456\\20261024120000_1.jpg", "123/456/20261024120000_1.JPG",
                "1234567890123/456/20261024120000_1.jpg", "123/123456789012345678901/20261024120000_1.jpg",
                "123/456/2026102412000_1.jpg", "123/456/20261024120000_12345.jpg",
                FIRST + "\n", FIRST + "/extra", "123/456/20261024120000_1.gif"}) {
            fails(() -> reconcile(engine, transfer, gallery, shot(id)));
        }
        for (long size : new long[]{0, -1, 30L * 1024 * 1024 + 1, Long.MAX_VALUE}) {
            fails(() -> reconcile(engine, transfer, gallery, new SyncEngine.Shot(FIRST, size, 1)));
        }
        for (double time : new double[]{Double.NaN, Double.POSITIVE_INFINITY, Double.NEGATIVE_INFINITY}) {
            fails(() -> reconcile(engine, transfer, gallery, new SyncEngine.Shot(FIRST, 1, time)));
        }
        fails(() -> engine.reconcile(null, transfer, gallery));
        fails(() -> reconcile(engine, transfer, gallery, (SyncEngine.Shot) null));
        fails(() -> reconcile(engine, transfer, gallery, A, new SyncEngine.Shot(FIRST, 5, 1)));
        assertTrue(transfer.downloads.isEmpty());
    }

    @Test public void exactMaximumMetadataAndThirtyMebibyteOriginalAreAccepted() throws Exception {
        SyncEngine engine = new SyncEngine(temporary.newFolder(), false);
        Transfer transfer = new Transfer(); Gallery gallery = new Gallery();
        SyncEngine.Shot maximum = new SyncEngine.Shot(
                "123456789012/12345678901234567890/20261024123456_1234.png", 30L * 1024 * 1024,
                Double.MAX_VALUE);
        observed(engine, transfer, gallery, maximum);
        reconcile(engine, transfer, gallery, maximum);
        assertEquals(maximum.size, engine.items().get(0).file.length());
        assertEquals("appOnly", engine.items().get(0).destination);
    }

    @Test public void symbolicLinksCannotEscapeOriginalsOrReplaceJournal() throws Exception {
        File root = temporary.newFolder(), outside = temporary.newFolder();
        Files.createSymbolicLink(new File(root, "originals").toPath(), outside.toPath());
        fails(() -> new SyncEngine(root, true));
        Files.delete(new File(root, "originals").toPath());
        File target = new File(outside, "receipts"); Files.write(target.toPath(), new byte[]{1});
        Files.createSymbolicLink(new File(root, "receipts.json").toPath(), target.toPath());
        fails(() -> new SyncEngine(root, true));
        assertArrayEquals(new byte[]{1}, Files.readAllBytes(target.toPath()));
    }

    @Test public void nestedSymlinkIntroducedDuringDownloadCannotEscapeRoot() throws Exception {
        File root = temporary.newFolder(), outside = temporary.newFolder();
        SyncEngine engine = new SyncEngine(root, false);
        Transfer transfer = new Transfer() {
            @Override public void download(SyncEngine.Shot shot, File file) throws Exception {
                super.download(shot, file);
                Files.createDirectory(new File(root, "originals").toPath());
                Files.createSymbolicLink(new File(root, "originals/123").toPath(), outside.toPath());
            }
        };
        Gallery gallery = new Gallery(); observed(engine, transfer, gallery, A);
        fails(() -> reconcile(engine, transfer, gallery, A));
        assertDownloadPending(engine, "appOnly");
        assertEquals(0, outside.list().length);
    }

    @Test public void failedPreferenceWriteRollsBackGalleryAndPendingDisposition() throws Exception {
        File root = temporary.newFolder();
        SyncEngine engine = new SyncEngine(root, true);
        Transfer transfer = new Transfer(); Gallery gallery = new Gallery();
        observed(engine, transfer, gallery, A); gallery.deny = true;
        reconcile(engine, transfer, gallery, A);
        File journal = new File(root, "receipts.json"); byte[] saved = Files.readAllBytes(journal.toPath());
        Files.delete(journal.toPath()); Files.createDirectory(journal.toPath());
        fails(() -> engine.setGallery(false));
        assertEquals("pending", engine.items().get(0).destination);
        Files.delete(journal.toPath()); Files.write(journal.toPath(), saved);
        gallery.deny = false; reconcile(engine, transfer, gallery, A);
        assertEquals(1, gallery.saves);
        assertEquals("saved", engine.items().get(0).destination);
    }

    @Test public void failedQueueWriteDoesNotStartDownloadOrChangeMemory() throws Exception {
        File root = temporary.newFolder();
        SyncEngine engine = new SyncEngine(root, false);
        Transfer transfer = new Transfer(); Gallery gallery = new Gallery();
        observed(engine, transfer, gallery, A);
        File journal = new File(root, "receipts.json"); byte[] saved = Files.readAllBytes(journal.toPath());
        Files.delete(journal.toPath()); Files.createDirectory(journal.toPath());
        fails(() -> reconcile(engine, transfer, gallery, A));
        assertTrue(transfer.downloads.isEmpty());
        assertDownloadPending(engine, "appOnly");
        Files.delete(journal.toPath()); Files.write(journal.toPath(), saved);
        reconcile(engine, transfer, gallery, A);
        assertEquals(1, engine.items().size());
    }

    @Test public void exportedImageWithFailedReceiptWriteRecoversThroughIdempotentExporter() throws Exception {
        File root = temporary.newFolder();
        File journal = new File(root, "receipts.json");
        SyncEngine engine = new SyncEngine(root, true);
        Transfer transfer = new Transfer();
        AtomicReference<byte[]> pendingJournal = new AtomicReference<>();
        Gallery gallery = new Gallery() {
            private boolean exists;

            @Override public boolean export(SyncEngine.Shot shot, File file,
                                            java.util.function.BooleanSupplier eligible) throws Exception {
                attempts++;
                if (exists) return true; // Recover the previous external save without another insert.
                assertTrue(eligible.getAsBoolean());
                exists = true; saves++;
                pendingJournal.set(Files.readAllBytes(journal.toPath()));
                Files.delete(journal.toPath()); Files.createDirectory(journal.toPath());
                return true;
            }
        };
        observed(engine, transfer, gallery, A);
        fails(() -> reconcile(engine, transfer, gallery, A));
        assertEquals("pending", engine.items().get(0).destination);
        Files.delete(journal.toPath()); Files.write(journal.toPath(), pendingJournal.get());
        SyncEngine relaunched = new SyncEngine(root, true);
        reconcile(relaunched, transfer, gallery);
        assertEquals("saved", relaunched.items().get(0).destination);
        assertEquals(1, gallery.saves);
        assertEquals(2, gallery.attempts);
        assertEquals(1, transfer.downloads.size());
    }

    @Test public void failedBaselineWriteCannotTurnHistoryIntoNewScreenshots() throws Exception {
        File root = temporary.newFolder();
        File journal = new File(root, "receipts.json");
        SyncEngine engine = new SyncEngine(root, false);
        Transfer transfer = new Transfer(); Gallery gallery = new Gallery();
        byte[] initialJournal = Files.readAllBytes(journal.toPath());
        Files.delete(journal.toPath()); Files.createDirectory(journal.toPath());
        fails(() -> reconcile(engine, transfer, gallery, A));
        Files.delete(journal.toPath()); Files.write(journal.toPath(), initialJournal);
        reconcile(engine, transfer, gallery, A);
        reconcile(engine, transfer, gallery, A);
        assertTrue(engine.items().isEmpty());
        assertTrue(transfer.downloads.isEmpty());
    }

    @Test public void firstObservedOffStaysAppOnlyWhenEnabledBeforeStabilityIncludingRelaunch() throws Exception {
        for (boolean restart : new boolean[]{false, true}) {
            File root = temporary.newFolder();
            SyncEngine engine = new SyncEngine(root, false);
            Transfer transfer = new Transfer(); Gallery gallery = new Gallery();
            observed(engine, transfer, gallery, A);
            assertDownloadPending(engine, "appOnly");
            engine.setGallery(true);
            if (restart) engine = new SyncEngine(root, true);
            reconcile(engine, transfer, gallery, A);
            assertTrue(engine.items().get(0).file.isFile());
            assertEquals("appOnly", engine.items().get(0).destination);
            assertEquals(0, gallery.attempts);
            reconcile(new SyncEngine(root, true), transfer, gallery, A);
            assertEquals(0, gallery.attempts);
        }
    }

    @Test public void observingOnOffOnStaysAppOnlyBeforeStabilityIncludingRelaunch() throws Exception {
        for (boolean restart : new boolean[]{false, true}) {
            File root = temporary.newFolder();
            SyncEngine engine = new SyncEngine(root, true);
            Transfer transfer = new Transfer(); Gallery gallery = new Gallery();
            observed(engine, transfer, gallery, A);
            assertDownloadPending(engine, "pending");
            engine.setGallery(false);
            assertDownloadPending(engine, "appOnly");
            if (restart) engine = new SyncEngine(root, false);
            engine.setGallery(true);
            if (restart) engine = new SyncEngine(root, true);
            // An intervening metadata change must preserve the first observation's disposition.
            SyncEngine.Shot changed = new SyncEngine.Shot(FIRST, 5, A.time + 1);
            reconcile(engine, transfer, gallery, changed);
            assertDownloadPending(engine, "appOnly");
            reconcile(engine, transfer, gallery, changed);
            assertTrue(engine.items().get(0).file.isFile());
            assertEquals("appOnly", engine.items().get(0).destination);
            assertEquals(0, gallery.attempts);
        }
    }

    @Test public void permanentGalleryFailureAllowsLaterOriginalAndExportInSamePoll() throws Exception {
        File root = temporary.newFolder();
        SyncEngine engine = new SyncEngine(root, true);
        Transfer transfer = new Transfer();
        IOException unavailable = new IOException("permanent Gallery failure");
        Gallery gallery = new Gallery() {
            @Override public boolean export(SyncEngine.Shot shot, File file,
                                            java.util.function.BooleanSupplier eligible) throws Exception {
                if (shot.id.equals(FIRST)) throw unavailable;
                return super.export(shot, file, eligible);
            }
        };
        observed(engine, transfer, gallery, A);
        assertSame(unavailable, fails(() -> reconcile(engine, transfer, gallery, A)).getCause());
        fails(() -> reconcile(engine, transfer, gallery, A, B));
        assertFalse(item(engine, SECOND).file.exists()); // B has only one observation.
        assertSame(unavailable, fails(() -> reconcile(engine, transfer, gallery, A, B)).getCause());
        assertEquals(Arrays.asList(FIRST, SECOND), transfer.downloads);
        assertTrue(item(engine, SECOND).file.isFile());
        assertEquals("saved", item(engine, SECOND).destination);
        assertEquals("pending", item(engine, FIRST).destination);
        fails(() -> reconcile(engine, transfer, gallery, A, B));
        assertEquals(2, transfer.downloads.size());
        assertEquals(1, gallery.saves);
        SyncEngine relaunched = new SyncEngine(root, true);
        assertEquals("pending", item(relaunched, FIRST).destination);
        assertEquals("saved", item(relaunched, SECOND).destination);
    }

    @Test public void permanentTransferFailureAllowsLaterOriginalInSamePollAndStaysQueued() throws Exception {
        File root = temporary.newFolder();
        SyncEngine engine = new SyncEngine(root, false);
        IOException unavailable = new IOException("permanent transfer failure");
        Transfer transfer = new Transfer() {
            @Override public void download(SyncEngine.Shot shot, File file) throws Exception {
                if (shot.id.equals(FIRST)) { downloads.add(shot.id); throw unavailable; }
                super.download(shot, file);
            }
        };
        Gallery gallery = new Gallery();
        observed(engine, transfer, gallery, A);
        fails(() -> reconcile(engine, transfer, gallery, A));
        fails(() -> reconcile(engine, transfer, gallery, A, B));
        assertSame(unavailable, fails(() -> reconcile(engine, transfer, gallery, A, B)).getCause());
        assertFalse(item(engine, FIRST).file.exists());
        assertTrue(item(engine, SECOND).file.isFile());
        assertEquals("appOnly", item(engine, SECOND).destination);
        assertEquals(Arrays.asList(FIRST, FIRST, FIRST, SECOND), transfer.downloads);
        SyncEngine relaunched = new SyncEngine(root, false);
        fails(() -> reconcile(relaunched, transfer, gallery, A, B));
        assertEquals(1, Collections.frequency(transfer.downloads, SECOND));
        assertFalse(item(relaunched, FIRST).file.exists());
        assertTrue(item(relaunched, SECOND).file.isFile());
    }

    @Test public void permanentTruncatedInvalidOrUndecodableImageDoesNotStarveLaterOriginal() throws Exception {
        for (String mode : Arrays.asList("truncated", "invalid", "decoder")) {
            SyncEngine engine = new SyncEngine(temporary.newFolder(), false);
            Transfer transfer = new Transfer() {
                private boolean first;

                @Override public void download(SyncEngine.Shot shot, File file) throws Exception {
                    super.download(shot, file);
                    first = shot.id.equals(FIRST);
                    if (first && mode.equals("truncated")) {
                        try (RandomAccessFile contents = new RandomAccessFile(file, "rw")) {
                            contents.setLength(shot.size - 1);
                        }
                    }
                }

                @Override public boolean validImage(File file) throws Exception {
                    if (first && mode.equals("decoder")) throw new IOException("decoder failure");
                    return !first;
                }
            };
            Gallery gallery = new Gallery();
            reconcile(engine, transfer, gallery);
            reconcile(engine, transfer, gallery, A, B);
            IOException error = fails(() -> reconcile(engine, transfer, gallery, A, B));
            assertTrue(error.getMessage().contains(FIRST));
            assertEquals(Arrays.asList(FIRST, SECOND), transfer.downloads);
            assertFalse(item(engine, FIRST).file.exists());
            assertTrue(item(engine, SECOND).file.isFile());
            fails(() -> reconcile(engine, transfer, gallery, A, B));
            assertEquals(1, Collections.frequency(transfer.downloads, SECOND));
            assertEquals(2, Collections.frequency(transfer.downloads, FIRST));
        }
    }

    @Test public void fatalJournalCommitAfterRetryableFailureHaltsLaterDownloadsUntilRecovered() throws Exception {
        File root = temporary.newFolder();
        File journal = new File(root, "receipts.json");
        SyncEngine engine = new SyncEngine(root, true);
        Transfer transfer = new Transfer();
        SyncEngine.Shot third = shot("123/456/20261024120002_3.jpg");
        IOException unavailable = new IOException("permanent Gallery failure");
        AtomicReference<byte[]> pendingJournal = new AtomicReference<>();
        Gallery gallery = new Gallery() {
            @Override public boolean export(SyncEngine.Shot shot, File file,
                                            java.util.function.BooleanSupplier eligible) throws Exception {
                if (shot.id.equals(FIRST)) throw unavailable;
                if (shot.id.equals(SECOND) && pendingJournal.get() == null) {
                    assertTrue(eligible.getAsBoolean());
                    pendingJournal.set(Files.readAllBytes(journal.toPath()));
                    Files.delete(journal.toPath()); Files.createDirectory(journal.toPath());
                }
                return true;
            }
        };
        reconcile(engine, transfer, gallery);
        reconcile(engine, transfer, gallery, A, B, third);
        IOException fatal = fails(() -> reconcile(engine, transfer, gallery, A, B, third));
        assertNotSame(unavailable, fatal.getCause()); // Journal failure supersedes deferred Gallery failure.
        assertTrue(journal.isDirectory());
        assertEquals(Arrays.asList(FIRST, SECOND), transfer.downloads);
        assertEquals("pending", item(engine, SECOND).destination);
        assertFalse(item(engine, third.id).file.exists());
        Files.delete(journal.toPath()); Files.write(journal.toPath(), pendingJournal.get());
        SyncEngine relaunched = new SyncEngine(root, true);
        assertSame(unavailable, fails(() -> reconcile(relaunched, transfer, gallery, A, B, third)).getCause());
        assertEquals(Arrays.asList(FIRST, SECOND, third.id), transfer.downloads);
        assertEquals("saved", item(relaunched, SECOND).destination);
        assertEquals("saved", item(relaunched, third.id).destination);
        assertEquals("pending", item(relaunched, FIRST).destination);
    }

    @Test public void fatalOriginalInstallationFailureHaltsLaterDownloads() throws Exception {
        File root = temporary.newFolder();
        SyncEngine engine = new SyncEngine(root, false);
        Transfer transfer = new Transfer() {
            @Override public void download(SyncEngine.Shot shot, File file) throws Exception {
                super.download(shot, file);
                if (shot.id.equals(FIRST)) Files.write(new File(root, "originals").toPath(), new byte[]{1});
            }
        };
        Gallery gallery = new Gallery();
        reconcile(engine, transfer, gallery);
        reconcile(engine, transfer, gallery, A, B);
        IOException fatal = fails(() -> reconcile(engine, transfer, gallery, A, B));
        assertEquals("Invalid originals directory", fatal.getMessage());
        assertEquals(Collections.singletonList(FIRST), transfer.downloads);
        assertFalse(item(engine, FIRST).file.exists());
        assertFalse(item(engine, SECOND).file.exists());
    }

    @Test public void lateRetryableFailureAfterStopCannotChangeFreshJournalOrSurfaceAnError() throws Exception {
        File root = temporary.newFolder();
        File journal = new File(root, "receipts.json");
        SyncEngine engine = new SyncEngine(root, false);
        Transfer fresh = new Transfer(); Gallery gallery = new Gallery();
        CountDownLatch entered = new CountDownLatch(1), release = new CountDownLatch(1);
        Transfer slow = new Transfer() {
            @Override public void download(SyncEngine.Shot shot, File file) throws Exception {
                entered.countDown(); await(release);
                throw new IOException("late transfer failure");
            }
        };
        reconcile(engine, fresh, gallery);
        reconcile(engine, fresh, gallery, A, B);
        try (Async async = new Async(() -> reconcile(engine, slow, gallery, A, B))) {
            byte[] saved;
            try {
                await(entered); engine.stop();
                reconcile(engine, fresh, gallery, A, B);
                saved = Files.readAllBytes(journal.toPath());
            } finally { release.countDown(); }
            async.finish();
            assertArrayEquals(saved, Files.readAllBytes(journal.toPath()));
        }
        assertEquals(Arrays.asList(FIRST, SECOND), fresh.downloads);
        assertTrue(item(engine, FIRST).file.isFile());
        assertTrue(item(engine, SECOND).file.isFile());
    }
}
