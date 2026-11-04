#!/usr/bin/env bash
# Run a command, keep its output in the log, and also publish it as ONE notice annotation
# (annotations are readable through the public API without signing in).
# Usage: notice.sh <title> <command...>
title="$1"; shift
set -o pipefail
"$@" 2>&1 | tee /tmp/notice.txt
code=$?
body=$(tail -c 3500 /tmp/notice.txt | sed -e 's/%/%25/g' | sed -e ':a;N;$!ba;s/\r//g;s/\n/%0A/g')
echo "::notice title=${title} (exit ${code})::${body}"
exit $code
