#!/usr/bin/env bash
# Build openfhe-wasm with the fdfhe extra bindings.
# Needs: emsdk activated, OpenFHE (wasm) installed at $OFHE_PREFIX.
# Output: $OUT/lib/openfhe_pke.{js,wasm} and openfhe_pke_es6.{js,wasm}
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
OWASM_REF="${OWASM_REF:-main}"
WORK="${WORK:-$HOME/owasm-src}"
OUT="${OUT:-$HOME/owasm-out}"

rm -rf "$WORK"
git clone -q https://github.com/openfheorg/openfhe-wasm.git "$WORK"
git -C "$WORK" checkout -q "$OWASM_REF"
cat "$HERE/fdfhe_extra_em.inc" >> "$WORK/src/pke/CryptoContext_em.cpp"
mkdir -p "$WORK/build" && cd "$WORK/build"
emcmake cmake .. -DOpenFHE_DIR="$OFHE_PREFIX/lib/OpenFHE"
emmake make -j4
rm -rf "$OUT" && mkdir -p "$OUT"
cp -r "$WORK/lib" "$OUT/"
ls -la "$OUT/lib"
