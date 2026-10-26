package com.saphid.framecontrol;

import java.util.function.Consumer;

/**
 * Owns the visible sync status. Each service instance gets one session token; once a session
 * ends, its late worker can no longer change the status, page or notification, even after a
 * newer session has started.
 */
final class SessionGate {
  static final String DISCONNECTED = "Disconnected";
  private long issued;
  private long current;
  private String state = DISCONNECTED;
  private String page;

  synchronized long begin() {
    current = ++issued;
    page = null;
    return current;
  }

  synchronized boolean active(long session) {
    return session != 0 && session == current;
  }

  synchronized boolean running() {
    return current != 0;
  }

  synchronized String state() {
    return state;
  }

  synchronized String page() {
    return page;
  }

  /** Publishes a status and runs {@code show} (the notification update) only while current. */
  synchronized boolean status(long session, String text, Consumer<String> show) {
    if (!active(session)) return false;
    state = text;
    if (show != null) show.accept(text);
    return true;
  }

  synchronized boolean page(long session, String value) {
    if (!active(session)) return false;
    page = value;
    return true;
  }

  /** Runs {@code action} only while the session is current, serialized against {@link #end}. */
  synchronized boolean ifActive(long session, Runnable action) {
    if (!active(session)) return false;
    action.run();
    return true;
  }

  /** Ends only the named session. Progress text becomes Disconnected; a final error stays. */
  synchronized boolean end(long session) {
    if (!active(session)) return false;
    current = 0;
    page = null;
    if (state.startsWith("Syncing")
        || state.startsWith("Waiting")
        || state.startsWith("Connecting")
        || state.startsWith("Screenshot pending")) state = DISCONNECTED;
    return true;
  }
}
