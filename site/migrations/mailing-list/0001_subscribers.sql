-- One current choice per random app capability, never a history of addresses.
-- Keep a tombstone on withdrawal so an older retry cannot add the address back.
CREATE TABLE IF NOT EXISTS mailing_list (
  subscriber_id TEXT PRIMARY KEY,
  rev INTEGER NOT NULL CHECK (rev > 0),
  email TEXT,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
