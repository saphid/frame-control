package com.saphid.framecontrol;

import org.junit.Test;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.List;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;

import static org.junit.Assert.*;

public class SessionGateTest {
    @Test public void endedSessionCannotPublishPageOrStop() {
        SessionGate gate = new SessionGate();
        List<String> shown = new ArrayList<>();
        long session = gate.begin();
        assertTrue(gate.status(session, "Syncing new screenshots", shown::add));
        assertTrue(gate.page(session, "http://127.0.0.1:1/?key=a"));
        assertTrue(gate.end(session));
        assertFalse(gate.running());
        assertNull(gate.page());
        // The worker finishes its download after Stop and reports the closed tunnel.
        assertFalse(gate.status(session, "Screenshot pending · Connection reset", shown::add));
        assertFalse(gate.status(session, "Syncing new screenshots", shown::add));
        assertFalse(gate.page(session, "http://127.0.0.1:1/?key=a"));
        AtomicBoolean stopped = new AtomicBoolean();
        assertFalse(gate.ifActive(session, () -> stopped.set(true)));
        assertFalse(stopped.get());
        assertEquals(Collections.singletonList("Syncing new screenshots"), shown);
        assertEquals(SessionGate.DISCONNECTED, gate.state());
    }

    @Test public void lateWorkerCannotChangeANewerSession() {
        SessionGate gate = new SessionGate();
        List<String> shown = new ArrayList<>();
        long first = gate.begin();
        gate.end(first);
        long second = gate.begin();
        assertTrue(gate.status(second, "Connecting to headset", shown::add));
        assertTrue(gate.page(second, "page-2"));
        assertFalse(gate.status(first, "Syncing new screenshots", shown::add));
        assertFalse(gate.page(first, null));
        assertFalse(gate.end(first));
        assertFalse(gate.ifActive(first, () -> fail("Stale session stopped the new one")));
        assertEquals("Connecting to headset", gate.state());
        assertEquals("page-2", gate.page());
        assertTrue(gate.running());
        assertEquals(Collections.singletonList("Connecting to headset"), shown);
        long third = gate.begin(); // Even without an end, a newer session supersedes.
        assertFalse(gate.status(second, "Syncing new screenshots", null));
        assertTrue(gate.active(third));
        assertNull(gate.page());
    }

    @Test public void endClearsProgressButKeepsFinalError() {
        for (String progress : Arrays.asList("Syncing new screenshots",
                "Syncing new screenshots · 1 file skipped (empty or over 30 MB)",
                "Waiting for headset · Connection refused", "Waiting for a Steam account on the headset",
                "Connecting to headset", "Screenshot pending · Download failed")) {
            SessionGate gate = new SessionGate();
            long session = gate.begin();
            gate.status(session, progress, null);
            gate.end(session);
            assertEquals(progress, SessionGate.DISCONNECTED, gate.state());
        }
        SessionGate gate = new SessionGate();
        long session = gate.begin();
        gate.status(session, "Pair with your headset first.", null);
        gate.end(session);
        assertEquals("Pair with your headset first.", gate.state());
    }

    @Test public void endWaitsForAnInFlightNotificationAndNothingPostsAfterIt() throws Exception {
        SessionGate gate = new SessionGate();
        long session = gate.begin();
        List<String> events = Collections.synchronizedList(new ArrayList<>());
        CountDownLatch entered = new CountDownLatch(1), release = new CountDownLatch(1);
        Thread worker = new Thread(() -> gate.status(session, "Syncing new screenshots", text -> {
            events.add("posting");
            entered.countDown();
            try { release.await(5, TimeUnit.SECONDS); } catch (InterruptedException e) { return; }
            events.add("posted");
        }));
        worker.start();
        assertTrue(entered.await(5, TimeUnit.SECONDS));
        Thread stop = new Thread(() -> { gate.end(session); events.add("ended"); });
        stop.start();
        stop.join(200);
        assertTrue("Stop must wait for the notification in flight", stop.isAlive());
        release.countDown();
        worker.join(5000);
        stop.join(5000);
        assertFalse(gate.status(session, "Syncing new screenshots", text -> events.add("late")));
        assertEquals(Arrays.asList("posting", "posted", "ended"), events);
    }
}
