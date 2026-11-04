#!/usr/bin/env bash
# CI: start the Worker locally, run the API tests, then the full end-to-end round.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export ADMIN_KEY=ci-admin ACTION_KEY=ci-action BASE=http://127.0.0.1:8787
cd "$ROOT/worker"
npm ci --no-audit --no-fund --loglevel=error
printf 'ADMIN_KEY=%s\nACTION_KEY=%s\n' "$ADMIN_KEY" "$ACTION_KEY" > .dev.vars
npx wrangler d1 execute private-delphi --local --file=schema.sql > /dev/null
(npx wrangler dev --local --port 8787 > /tmp/wrangler.log 2>&1 &)
for i in $(seq 1 90); do curl -sf "$BASE/index.html" > /dev/null && break; sleep 1; done
curl -sf "$BASE/index.html" > /dev/null || { echo "wrangler dev did not start"; tail -30 /tmp/wrangler.log; exit 1; }
node --test test/api.test.js 2>&1 | grep -E "^(ok|not ok)|# (pass|fail)|rror" || true
node --test test/api.test.js > /dev/null
cd "$ROOT"
node tests/e2e.js || { echo "--- wrangler log"; tail -40 /tmp/wrangler.log; exit 1; }
