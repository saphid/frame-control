package com.saphid.framecontrol;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import com.google.gson.Strictness;
import com.google.gson.TypeAdapter;
import com.google.gson.stream.JsonReader;
import com.google.gson.stream.JsonToken;
import com.google.gson.stream.JsonWriter;

import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStreamReader;
import java.io.OutputStreamWriter;
import java.io.Writer;
import java.nio.channels.FileChannel;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.LinkOption;
import java.nio.file.NoSuchFileException;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.nio.file.StandardOpenOption;
import java.nio.file.attribute.BasicFileAttributes;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.TreeSet;
import java.util.function.BooleanSupplier;
import java.util.regex.Pattern;

/** One reusable engine per root. The caller supplies an account/headset-specific root. */
public final class SyncEngine {
    private static final long MAX_SIZE = 30L * 1024 * 1024;
    private static final Pattern ID = Pattern.compile(
            "^[0-9]{1,12}/[0-9]{1,20}/[0-9]{14}_[0-9]{1,4}\\.(jpg|png)$");
    private static final Pattern ACCOUNT = Pattern.compile("^[0-9]{1,12}$");
    private static final Gson GSON = new GsonBuilder().registerTypeAdapter(Shot.class,
            new TypeAdapter<Shot>() {
                @Override public void write(JsonWriter writer, Shot shot) throws IOException {
                    writer.beginObject();
                    writer.name("id").value(shot.id);
                    writer.name("size").value(shot.size);
                    writer.name("time").value(shot.time);
                    writer.endObject();
                }

                @Override public Shot read(JsonReader reader) throws IOException {
                    String id = null;
                    Long size = null;
                    Double time = null;
                    Set<String> fields = new HashSet<>();
                    reader.beginObject();
                    while (reader.hasNext()) {
                        String field = reader.nextName();
                        if (!fields.add(field)) throw new IOException("Duplicate screenshot field");
                        switch (field) {
                            case "id":
                                if (reader.peek() != JsonToken.STRING) throw new IOException("Invalid id");
                                id = reader.nextString();
                                break;
                            case "size":
                                if (reader.peek() != JsonToken.NUMBER) throw new IOException("Invalid size");
                                size = reader.nextLong();
                                break;
                            case "time":
                                if (reader.peek() != JsonToken.NUMBER) throw new IOException("Invalid time");
                                time = reader.nextDouble();
                                break;
                            default: throw new IOException("Unknown screenshot field");
                        }
                    }
                    reader.endObject();
                    if (id == null || size == null || time == null) throw new IOException("Incomplete shot");
                    return new Shot(id, size, time);
                }
            }).create();

    public static final class Shot {
        public final String id;
        public final long size;
        public final double time;

        public Shot(String id, long size, double time) {
            this.id = id;
            this.size = size;
            this.time = time;
        }
    }

    /**
     * One headset poll. {@code accounts} names every Steam account directory present on the
     * headset, including accounts with no screenshots yet. An absent userdata root is an empty set.
     */
    public static final class Listing {
        public final Set<String> accounts;
        public final List<Shot> shots;

        public Listing(Set<String> accounts, List<Shot> shots) {
            this.accounts = accounts;
            this.shots = shots;
        }
    }

    public interface Transport {
        void download(Shot shot, File destination) throws Exception;
        boolean validImage(File f) throws Exception;
    }

    public interface Exporter {
        boolean export(Shot shot, File original, BooleanSupplier eligible) throws Exception;
    }

    public static final class Item {
        public final Shot shot;
        /** Future original path; may not exist while the shot is observing or queued. */
        public final File file;
        public final String destination;

        private Item(Shot shot, File file, String destination) {
            this.shot = shot;
            this.file = file;
            this.destination = destination;
        }
    }

    // Boxed fields make missing journal fields distinguishable from legitimate zero values.
    private static final class Ledger {
        Integer version;
        Boolean initialized;
        Boolean gallery;
        /** Accounts already baselined. Absent only in version 1 journals. */
        Set<String> accounts;
        Map<String, Receipt> records;
    }

    private static final class Poll {
        final Map<String, Shot> eligible = new LinkedHashMap<>();
        final Set<String> accounts = new TreeSet<>();
        int skipped;
    }

    private static final class Receipt {
        Shot shot;
        String state;
        Integer observations;
        String destination;

        Receipt(Shot shot, String state, int observations, String destination) {
            this.shot = shot;
            this.state = state;
            this.observations = observations;
            this.destination = destination;
        }
    }

    /** Only external callbacks and rejected transfer contents are safe to retry per item. */
    private static final class ItemFailure extends IOException {
        private static final long serialVersionUID = 1L;

        ItemFailure(String message, Exception cause) {
            super(message, cause);
        }
    }

    private final Object lock = new Object();
    private final Path root;
    private final Path originals;
    private final Path journal;
    private Ledger ledger;
    private long generation;
    private long active;
    private boolean closed;
    private volatile int skipped;

    public SyncEngine(File root, boolean gallery) throws Exception {
        this(root, Boolean.valueOf(gallery));
    }

    /** A null gallery opens a read-only view that never creates, upgrades or rewrites anything. */
    private SyncEngine(File root, Boolean gallery) throws Exception {
        if (root == null || Files.isSymbolicLink(root.toPath())) {
            throw new IOException("Unsafe sync root");
        }
        this.root = root.getCanonicalFile().toPath();
        if (gallery == null) {
            closed = true;
        } else {
            List<Path> missingDirectories = new ArrayList<>();
            for (Path path = this.root; path != null && !Files.exists(path); path = path.getParent()) {
                missingDirectories.add(path);
            }
            Files.createDirectories(this.root);
            for (Path directory : missingDirectories) syncDirectory(directory.getParent());
        }
        originals = this.root.resolve("originals");
        journal = this.root.resolve("receipts.json");
        checkPath(originals);
        checkPath(journal);
        if (Files.exists(originals, LinkOption.NOFOLLOW_LINKS)
                && !Files.isDirectory(originals, LinkOption.NOFOLLOW_LINKS)) {
            throw new IOException("Invalid originals directory");
        }
        if (Files.exists(journal, LinkOption.NOFOLLOW_LINKS)) {
            if (!Files.isRegularFile(journal, LinkOption.NOFOLLOW_LINKS)) {
                throw new IOException("Invalid sync journal");
            }
            // Never recover a damaged or incomplete journal by establishing another baseline.
            try (JsonReader reader = new JsonReader(new InputStreamReader(
                    Files.newInputStream(journal), StandardCharsets.UTF_8))) {
                reader.setStrictness(Strictness.STRICT);
                ledger = GSON.fromJson(reader, Ledger.class);
                if (reader.peek() != JsonToken.END_DOCUMENT) {
                    throw new IOException("Trailing sync journal data");
                }
            } catch (RuntimeException e) {
                throw new IOException("Corrupt sync journal", e);
            }
            validateLedger();
            if (gallery != null) setGallery(gallery);
        } else {
            if (Files.exists(originals, LinkOption.NOFOLLOW_LINKS)) {
                try (java.util.stream.Stream<Path> paths = Files.walk(originals)) {
                    if (paths.anyMatch(p -> !Files.isDirectory(p, LinkOption.NOFOLLOW_LINKS))) {
                        throw new IOException("Originals exist without a sync journal");
                    }
                }
            }
            ledger = emptyLedger();
            if (gallery == null) {
                ledger.gallery = false;
            } else {
                ledger.gallery = gallery;
                persist(ledger);
            }
        }
    }

    /** Post-baseline receipts read without locks, directory creation or journal writes. */
    public static List<Item> snapshot(File root) throws Exception {
        return new SyncEngine(root, (Boolean) null).items();
    }

    /** Returns false, without writing, once this engine is closed. */
    public boolean setGallery(boolean enabled) throws Exception {
        synchronized (lock) {
            if (closed) return false;
            if (ledger.gallery == enabled) return true;
            Ledger next = copy();
            next.gallery = enabled;
            if (!enabled) {
                for (Receipt receipt : next.records.values()) {
                    if ("pending".equals(receipt.destination)) receipt.destination = "appOnly";
                }
            }
            commit(next);
            return true;
        }
    }

    /**
     * A second live reconcile is rejected. stop() cancels its generation and permits a new run;
     * close() cancels it permanently. The journal is rewritten only when a receipt changes.
     */
    public void reconcile(Listing listing, Transport transport, Exporter exporter) throws Exception {
        final long run;
        synchronized (lock) {
            if (closed) throw new IllegalStateException("Sync stopped");
            if (active != 0) throw new IllegalStateException("Sync already in progress");
            run = ++generation;
            active = run;
        }
        try {
            Poll poll = poll(listing);
            synchronized (lock) {
                if (active != run) return;
                skipped = poll.skipped;
                Ledger next = copy();
                if (!next.initialized) {
                    for (Shot shot : poll.eligible.values()) {
                        next.records.put(shot.id, new Receipt(shot, "baseline", 0, null));
                    }
                    next.initialized = true;
                    next.version = 2;
                    next.accounts = poll.accounts;
                    commit(next);
                    return;
                }
                boolean changed = false;
                Set<String> known = next.accounts;
                if (known == null) {
                    // Version 1 journals did not record accounts. Trust only accounts that already
                    // have receipts; any other account present now is history and is baselined.
                    known = new TreeSet<>();
                    for (String id : next.records.keySet()) known.add(account(id));
                    // The account comparison below always records the set with this version.
                    next.version = 2;
                    changed = true;
                }
                // Missing observations break consecutiveness, including across restarts.
                for (Receipt receipt : next.records.values()) {
                    if (!poll.eligible.containsKey(receipt.shot.id) && receipt.observations != 0
                            && ("observing".equals(receipt.state) || "queued".equals(receipt.state))) {
                        receipt.observations = 0;
                        changed = true;
                    }
                }
                for (Shot shot : poll.eligible.values()) {
                    Receipt receipt = next.records.get(shot.id);
                    if (receipt == null && !known.contains(account(shot.id))) {
                        // A newly appearing account (or a returning one) starts with its own
                        // baseline, so its existing screenshots are never imported.
                        next.records.put(shot.id, new Receipt(shot, "baseline", 0, null));
                        changed = true;
                    } else if (receipt == null) {
                        // Latch eligibility at discovery, before waiting for a stable second sample.
                        next.records.put(shot.id, new Receipt(shot, "observing", 1,
                                next.gallery ? "pending" : "appOnly"));
                        changed = true;
                    } else if ("observing".equals(receipt.state) || "queued".equals(receipt.state)) {
                        boolean stable = same(receipt.shot, shot);
                        int observations = stable ? Math.min(2, receipt.observations + 1) : 1;
                        if (!stable || observations != receipt.observations) changed = true;
                        receipt.observations = observations;
                        receipt.shot = shot;
                        if (receipt.observations == 2 && "observing".equals(receipt.state)) {
                            receipt.state = "queued";
                        }
                    }
                }
                // Accounts absent now are forgotten; if one returns it is baselined again.
                if (!poll.accounts.equals(next.accounts)) {
                    next.accounts = poll.accounts;
                    changed = true;
                }
                // Queue and its disposition reach disk before any download.
                if (changed) commit(next);
            }

            List<String> ids;
            synchronized (lock) {
                if (active != run) return;
                ids = new ArrayList<>(ledger.records.keySet());
            }
            ItemFailure failure = null;
            for (String id : ids) {
                Shot download = null;
                synchronized (lock) {
                    if (active != run) return;
                    Receipt receipt = ledger.records.get(id);
                    if ("queued".equals(receipt.state) && receipt.observations == 2) {
                        download = receipt.shot;
                    }
                }
                try {
                    if (download != null) download(run, download, transport);
                    export(run, id, exporter);
                } catch (ItemFailure e) {
                    if (failure == null) failure = e;
                    else failure.addSuppressed(e);
                }
            }
            // Surface retryable errors to the service after independent items have progressed.
            // Untagged local I/O/journal failures escape immediately and halt the run.
            if (failure != null) throw failure;
        } catch (Exception e) {
            synchronized (lock) {
                if (active != run) return; // A late failed callback belongs to a cancelled run.
            }
            throw e;
        } finally {
            synchronized (lock) {
                if (active == run) active = 0;
            }
        }
    }

    /** Snapshot of all post-baseline receipts, including downloads still pending. */
    public List<Item> items() {
        synchronized (lock) {
            List<Item> result = new ArrayList<>();
            for (Receipt receipt : ledger.records.values()) {
                if (!"baseline".equals(receipt.state)) {
                    result.add(new Item(receipt.shot, originals.resolve(receipt.shot.id).toFile(),
                            receipt.destination));
                }
            }
            result.sort(Comparator.comparingDouble((Item item) -> item.shot.time).reversed()
                    .thenComparing(item -> item.shot.id));
            return Collections.unmodifiableList(result);
        }
    }

    /** Listed files left out of the last poll because they were empty or over 30 MiB. */
    public int skipped() {
        return skipped;
    }

    public void stop() {
        synchronized (lock) {
            ++generation;
            active = 0;
        }
    }

    /**
     * Permanently cancels this engine. Once it returns, no in-flight or later call can write the
     * journal, so another engine may safely take over the same root.
     */
    public void close() {
        synchronized (lock) {
            closed = true;
            ++generation;
            active = 0;
        }
    }

    public boolean isClosed() {
        synchronized (lock) {
            return closed;
        }
    }

    private void download(long run, Shot shot, Transport transport) throws Exception {
        Path temporary;
        synchronized (lock) {
            if (active != run) return;
            temporary = Files.createTempFile(root, ".download-", ".part");
        }
        try {
            try {
                transport.download(shot, temporary.toFile());
            } catch (InterruptedException e) {
                throw e;
            } catch (Exception e) {
                throw new ItemFailure("Download failed: " + shot.id + ": " + e.getMessage(), e);
            }
            synchronized (lock) {
                if (active != run) return;
            }
            checkTransfer(temporary, shot);
            boolean valid;
            try {
                valid = transport.validImage(temporary.toFile());
            } catch (InterruptedException e) {
                throw e;
            } catch (Exception e) {
                throw new ItemFailure("Image validation failed: " + shot.id + ": " + e.getMessage(), e);
            }
            if (!valid) throw new ItemFailure("Invalid image: " + shot.id, null);
            checkTransfer(temporary, shot);
            try (FileChannel channel = FileChannel.open(temporary, StandardOpenOption.WRITE)) {
                channel.force(true);
            }
            synchronized (lock) {
                if (active != run) return;
                Path target = originals.resolve(shot.id);
                createParents(target.getParent());
                checkPath(target);
                Files.move(temporary, target, StandardCopyOption.ATOMIC_MOVE,
                        StandardCopyOption.REPLACE_EXISTING);
                syncDirectory(target.getParent());
                Ledger next = copy();
                // Read the current destination: setGallery may have changed it during the transfer.
                next.records.get(shot.id).state = "downloaded";
                commit(next);
            }
        } finally {
            Files.deleteIfExists(temporary);
        }
    }

    private void export(long run, String id, Exporter exporter) throws Exception {
        Shot shot;
        File original;
        synchronized (lock) {
            if (!eligible(run, id)) return;
            Receipt receipt = ledger.records.get(id);
            shot = receipt.shot;
            Path path = originals.resolve(id);
            checkDownload(path, shot);
            original = path.toFile();
        }
        boolean saved;
        try {
            saved = exporter.export(shot, original, () -> {
                synchronized (lock) {
                    return eligible(run, id);
                }
            });
        } catch (InterruptedException e) {
            throw e;
        } catch (Exception e) {
            throw new ItemFailure("Gallery export failed: " + shot.id + ": " + e.getMessage(), e);
        }
        synchronized (lock) {
            if (active != run || !saved) return;
            Ledger next = copy();
            // A true result means the exporter actually saved (or recovered) the MediaStore item.
            next.records.get(id).destination = "saved";
            commit(next);
        }
    }

    private boolean eligible(long run, String id) {
        Receipt receipt = ledger.records.get(id);
        return active == run && ledger.gallery && receipt != null
                && "downloaded".equals(receipt.state) && "pending".equals(receipt.destination);
    }

    private static Poll poll(Listing listing) throws IOException {
        if (listing == null || listing.shots == null || listing.accounts == null) {
            throw new IOException("Missing screenshot listing");
        }
        Poll result = new Poll();
        for (String account : listing.accounts) {
            if (account == null || !ACCOUNT.matcher(account).matches()) {
                throw new IOException("Invalid Steam account");
            }
            result.accounts.add(account);
        }
        Map<String, Shot> seen = new LinkedHashMap<>();
        for (Shot shot : listing.shots) {
            // Unsafe ids, non-finite times and conflicting duplicates reject the whole listing.
            validateIdentity(shot);
            Shot previous = seen.put(shot.id, shot);
            if (previous != null && !same(previous, shot)) {
                throw new IOException("Conflicting screenshot identity: " + shot.id);
            }
            // The account directory may appear between the account and screenshot queries.
            result.accounts.add(account(shot.id));
        }
        for (Shot shot : seen.values()) {
            // An empty, still-writing or oversized file is only this item's problem: treat it
            // as absent from this poll so it never blocks other screenshots or the baseline.
            if (eligibleSize(shot)) result.eligible.put(shot.id, shot);
            else result.skipped++;
        }
        return result;
    }

    private static String account(String id) {
        return id.substring(0, id.indexOf('/'));
    }

    private static void validateIdentity(Shot shot) throws IOException {
        if (shot == null || shot.id == null || !ID.matcher(shot.id).matches()
                || !Double.isFinite(shot.time)) {
            throw new IOException("Invalid screenshot metadata");
        }
    }

    private static boolean eligibleSize(Shot shot) {
        return shot.size > 0 && shot.size <= MAX_SIZE;
    }

    private static void validateShot(Shot shot) throws IOException {
        validateIdentity(shot);
        if (!eligibleSize(shot)) throw new IOException("Invalid screenshot metadata");
    }

    private static boolean same(Shot a, Shot b) {
        return a.size == b.size && Double.compare(a.time, b.time) == 0;
    }

    private void validateLedger() throws IOException {
        if (ledger == null || ledger.version == null || ledger.initialized == null
                || ledger.gallery == null || ledger.records == null
                || (ledger.version == 1 && ledger.accounts != null)
                || (ledger.version == 2 && ledger.accounts == null)
                || (ledger.version != 1 && ledger.version != 2)
                || (!ledger.initialized && !ledger.records.isEmpty())
                || (!ledger.initialized && ledger.accounts != null && !ledger.accounts.isEmpty())) {
            throw new IOException("Invalid sync journal header");
        }
        if (ledger.accounts != null) {
            for (String account : ledger.accounts) {
                if (account == null || !ACCOUNT.matcher(account).matches()) {
                    throw new IOException("Invalid sync journal header");
                }
            }
            ledger.accounts = new TreeSet<>(ledger.accounts);
        }
        for (Map.Entry<String, Receipt> entry : ledger.records.entrySet()) {
            Receipt receipt = entry.getValue();
            if (receipt == null) throw new IOException("Invalid sync receipt");
            validateShot(receipt.shot);
            if (!entry.getKey().equals(receipt.shot.id) || receipt.observations == null
                    || receipt.observations < 0 || receipt.observations > 2) {
                throw new IOException("Invalid sync receipt identity");
            }
            boolean baseline = "baseline".equals(receipt.state);
            boolean observing = "observing".equals(receipt.state);
            boolean queued = "queued".equals(receipt.state);
            boolean downloaded = "downloaded".equals(receipt.state);
            if ((!baseline && !observing && !queued && !downloaded)
                    || (baseline && receipt.destination != null)
                    || (baseline && receipt.observations != 0)
                    || (observing && receipt.observations > 1)
                    || (downloaded && receipt.observations != 2)
                    || ((observing || queued || downloaded) && !"pending".equals(receipt.destination)
                        && !"appOnly".equals(receipt.destination) && !"saved".equals(receipt.destination))
                    || ((observing || queued) && "saved".equals(receipt.destination))
                    || (!ledger.gallery && "pending".equals(receipt.destination))) {
                throw new IOException("Invalid sync receipt state");
            }
            Path path = originals.resolve(receipt.shot.id);
            checkPath(path);
            if (downloaded) checkDownload(path, receipt.shot);
        }
    }

    private void checkDownload(Path path, Shot shot) throws IOException {
        checkPath(path);
        if (!Files.isRegularFile(path, LinkOption.NOFOLLOW_LINKS) || Files.size(path) != shot.size) {
            throw new IOException("Incomplete original: " + shot.id);
        }
    }

    private void checkTransfer(Path path, Shot shot) throws IOException {
        checkPath(path); // Unsafe paths and local filesystem errors remain fatal.
        BasicFileAttributes attributes;
        try {
            attributes = Files.readAttributes(path, BasicFileAttributes.class, LinkOption.NOFOLLOW_LINKS);
        } catch (NoSuchFileException e) {
            throw new ItemFailure("Missing downloaded image: " + shot.id, e);
        }
        if (!attributes.isRegularFile() || attributes.size() != shot.size) {
            throw new ItemFailure("Incomplete downloaded image: " + shot.id, null);
        }
    }

    private void checkPath(Path path) throws IOException {
        if (!path.normalize().startsWith(root)) throw new IOException("Path escaped sync root");
        Path current = root;
        if (Files.isSymbolicLink(current)) throw new IOException("Symlink in sync root");
        for (Path component : root.relativize(path)) {
            current = current.resolve(component);
            if (Files.isSymbolicLink(current)) throw new IOException("Symlink in sync path");
        }
    }

    private void createParents(Path directory) throws IOException {
        checkPath(directory);
        Path current = root;
        for (Path component : root.relativize(directory)) {
            Path parent = current;
            current = current.resolve(component);
            if (!Files.exists(current, LinkOption.NOFOLLOW_LINKS)) {
                Files.createDirectory(current);
                syncDirectory(parent);
            } else if (!Files.isDirectory(current, LinkOption.NOFOLLOW_LINKS)) {
                throw new IOException("Invalid originals directory");
            }
        }
    }

    /**
     * Keeps the version: a version 1 journal (no account set) stays version 1 through setting
     * changes, and only reconcile upgrades it, recording the version and accounts together.
     */
    private Ledger copy() {
        Ledger next = emptyLedger();
        next.version = ledger.version;
        next.initialized = ledger.initialized;
        next.gallery = ledger.gallery;
        next.accounts = ledger.accounts == null ? null : new TreeSet<>(ledger.accounts);
        for (Map.Entry<String, Receipt> entry : ledger.records.entrySet()) {
            Receipt receipt = entry.getValue();
            next.records.put(entry.getKey(), new Receipt(receipt.shot, receipt.state,
                    receipt.observations, receipt.destination));
        }
        return next;
    }

    private static Ledger emptyLedger() {
        Ledger result = new Ledger();
        result.version = 2;
        result.initialized = false;
        result.accounts = new TreeSet<>();
        result.records = new LinkedHashMap<>();
        return result;
    }

    private void commit(Ledger next) throws IOException {
        if (closed) throw new IOException("Sync journal is read-only");
        persist(next);
        ledger = next;
    }

    private void persist(Ledger next) throws IOException {
        checkPath(journal);
        Path temporary = Files.createTempFile(root, ".receipts-", ".tmp");
        try {
            try (FileOutputStream output = new FileOutputStream(temporary.toFile());
                 Writer writer = new OutputStreamWriter(output, StandardCharsets.UTF_8)) {
                GSON.toJson(next, writer);
                writer.flush();
                output.getFD().sync();
            }
            Files.move(temporary, journal, StandardCopyOption.ATOMIC_MOVE,
                    StandardCopyOption.REPLACE_EXISTING);
            syncDirectory(root);
        } finally {
            Files.deleteIfExists(temporary);
        }
    }

    private static void syncDirectory(Path directory) {
        // Some Android filesystems reject directory channels. File contents were already fsynced;
        // the rename is atomic either way. Do not report rollback after a committed rename.
        try (FileChannel channel = FileChannel.open(directory, StandardOpenOption.READ)) {
            channel.force(true);
        } catch (IOException | UnsupportedOperationException ignored) {
            // Best available portable Java directory durability.
        }
    }
}
