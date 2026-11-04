-- D1 schema. Everything stored is public or encrypted to a recipient; only writes need auth.
CREATE TABLE IF NOT EXISTS surveys (
  id        TEXT PRIMARY KEY,
  title     TEXT NOT NULL,           -- JSON {en, vi}
  criteria  TEXT NOT NULL,           -- JSON [{en, vi}, ...]
  k         INTEGER NOT NULL,
  round     INTEGER NOT NULL DEFAULT 1,
  status    TEXT NOT NULL DEFAULT 'ceremony',   -- ceremony | open | closed | opening | published
  created   INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS tokens (
  hash      TEXT PRIMARY KEY,        -- SHA-256 hex of the bearer token
  survey    TEXT NOT NULL,
  role      TEXT NOT NULL,           -- organizer | holder | expert
  member    INTEGER                  -- holder number 1..3
);

CREATE TABLE IF NOT EXISTS files (
  survey    TEXT NOT NULL,
  path      TEXT NOT NULL,
  parts     INTEGER NOT NULL,
  size      INTEGER NOT NULL DEFAULT 0,
  done      INTEGER NOT NULL DEFAULT 0,
  created   INTEGER NOT NULL,
  PRIMARY KEY (survey, path)
);

CREATE TABLE IF NOT EXISTS file_parts (
  survey    TEXT NOT NULL,
  path      TEXT NOT NULL,
  idx       INTEGER NOT NULL,
  size      INTEGER NOT NULL,
  PRIMARY KEY (survey, path, idx)    -- write-once: a second upload of the same part fails
);

CREATE TABLE IF NOT EXISTS ballots (
  survey    TEXT NOT NULL,
  round     INTEGER NOT NULL,
  token     TEXT NOT NULL,           -- invite token hash: one ballot per invite per round
  receipt   TEXT NOT NULL,
  created   INTEGER NOT NULL,
  PRIMARY KEY (survey, round, token)
);
CREATE INDEX IF NOT EXISTS ballots_by_round ON ballots (survey, round, created);
