#!/usr/bin/env bash
# ── Test the PyInstaller-built clash binary ───────────────────
#
# Verifies:
#   1. Binary is executable and has a sane size
#   2. System library dependencies are minimal (glibc 2.17 core only)
#   3. --help and --version work
#   4. clash --json status outputs valid JSON (running: false)
#   5. clash profile list works (empty, no crash)
#   6. mihomo is bundled: find_mihomo() resolves from sys._MEIPASS
#      even when mihomo is absent from PATH and CLASH_MIHOMO_PATH
#
# Usage:  bash scripts/test_build.sh <path-to-clash-binary>
#
# Exit:   0 if all checks pass, 1 otherwise.

set -euo pipefail

BIN="${1:?Usage: $0 <clash_binary>}"
PASS=0
FAIL=0
TOTAL=0

pass()  { PASS=$((PASS+1));  TOTAL=$((TOTAL+1)); echo "  ✓ $1"; }
fail()  { FAIL=$((FAIL+1));  TOTAL=$((TOTAL+1)); echo "  ✗ $1"; echo "    $2"; }
info()  { echo "  ℹ $1"; }

echo "═══════════════════════════════════════════════════════════"
echo "  clash binary verification"
echo "  Binary : ${BIN}"
echo "═══════════════════════════════════════════════════════════"

# ── Isolated HOME so tests don't touch the real ~/.clash_cli ──
WORK_DIR=$(mktemp -d)
export CLASH_CLI_HOME="${WORK_DIR}/.clash_cli"
# Remove mihomo from PATH so bundled binary is the only option
export PATH=$(echo "$PATH" | tr ':' '\n' | grep -v "mihomo" | tr '\n' ':')
unset CLASH_MIHOMO_PATH 2>/dev/null || true

cleanup() { rm -rf "${WORK_DIR}"; }
trap cleanup EXIT


# ══ 1. Binary basics ══════════════════════════════════════════
echo ""
echo "── Binary basics ──"

if [ -x "${BIN}" ]; then
    pass "Binary is executable"
else
    fail "Binary is executable" "File is not executable or does not exist"
fi

SIZE_MB=$(du -m "${BIN}" 2>/dev/null | cut -f1)
info "Binary size: ${SIZE_MB} MB"
if [ "${SIZE_MB}" -gt 5 ]; then
    pass "Binary size > 5 MB (mihomo bundled)"
else
    fail "Binary size > 5 MB" "Got ${SIZE_MB} MB — mihomo may not be bundled"
fi


# ══ 2. System dependency check ════════════════════════════════
echo ""
echo "── System dependencies (ldd) ──"

if command -v ldd >/dev/null 2>&1; then
    LDD_OUT=$(ldd "${BIN}" 2>&1 || true)
    LIB_COUNT=$(echo "${LDD_OUT}" | grep -c "=>" || true)
    info "Linked libraries: ${LIB_COUNT}"

    DISALLOWED=$(echo "${LDD_OUT}" \
        | grep "=>" \
        | grep -v "linux-vdso" \
        | grep -v "ld-linux" \
        | grep -v "libc\.so" \
        | grep -v "libm\.so" \
        | grep -v "libpthread" \
        | grep -v "libdl" \
        | grep -v "librt\.so" \
        | grep -v "libz\.so" \
        | grep -v "libutil" \
        | grep -v "libresolv" \
        | grep -v "libnsl" \
        | grep -v "libcrypt" \
        | grep -v "libgcc_s" \
        | grep -v "libstdc++" \
        || true)

    if [ -z "${DISALLOWED}" ]; then
        pass "Only core system libraries required"
    else
        fail "Only core system libraries required" "Unexpected: ${DISALLOWED}"
    fi

    NOT_FOUND=$(echo "${LDD_OUT}" | grep "not found" || true)
    if [ -z "${NOT_FOUND}" ]; then
        pass "No missing libraries"
    else
        fail "No missing libraries" "${NOT_FOUND}"
    fi

    echo "${LDD_OUT}" | sed 's/^/    /'
else
    info "ldd not available, skipping dependency check"
fi


# ══ 3. Basic CLI ══════════════════════════════════════════════
echo ""
echo "── CLI basics ──"

if "${BIN}" --help >/dev/null 2>&1; then
    pass "--help exits 0"
else
    fail "--help exits 0" "Returned non-zero"
fi

VERSION_OUT=$("${BIN}" --version 2>&1 || true)
if echo "${VERSION_OUT}" | grep -qE "clash [0-9]+\.[0-9]+|0\.[0-9]+"; then
    pass "--version prints version string"
else
    fail "--version prints version string" "Output: ${VERSION_OUT}"
fi

# Check that all top-level subcommands are listed in --help
for CMD in start stop restart status profile mode proxy rule conn log dns; do
    if "${BIN}" --help 2>&1 | grep -q "${CMD}"; then
        pass "--help lists '${CMD}'"
    else
        fail "--help lists '${CMD}'" "Subcommand missing from help output"
    fi
done


# ══ 4. clash status (not running) ════════════════════════════
echo ""
echo "── clash status ──"

STATUS_OUT=$("${BIN}" --json status 2>&1 || true)
if echo "${STATUS_OUT}" | python3 -c "
import sys, json
d = json.load(sys.stdin)
assert d['status'] == 'ok'
assert d['data']['running'] == False
" 2>/dev/null; then
    pass "clash --json status → running:false"
else
    fail "clash --json status → running:false" "Output: ${STATUS_OUT}"
fi

HUMAN_OUT=$("${BIN}" status 2>&1 || true)
if echo "${HUMAN_OUT}" | grep -qi "not running\|○"; then
    pass "clash status (human) shows not-running message"
else
    fail "clash status (human) shows not-running message" "Output: ${HUMAN_OUT}"
fi


# ══ 5. clash profile list (empty) ════════════════════════════
echo ""
echo "── clash profile list ──"

LIST_OUT=$("${BIN}" --json profile list 2>&1 || true)
if echo "${LIST_OUT}" | python3 -c "
import sys, json
d = json.load(sys.stdin)
assert d['status'] == 'ok'
assert isinstance(d['data'], list)
" 2>/dev/null; then
    pass "clash --json profile list → ok, list"
else
    fail "clash --json profile list → ok, list" "Output: ${LIST_OUT}"
fi


# ══ 6. mihomo is bundled ══════════════════════════════════════
echo ""
echo "── mihomo bundled check ──"

# clash start with a nonexistent profile.
# - If mihomo IS bundled: error is PROFILE_NOT_FOUND
# - If mihomo is NOT bundled: error is MIHOMO_NOT_FOUND
BUNDLED_OUT=$("${BIN}" --json start --profile __nonexistent_profile__ 2>&1 || true)

if echo "${BUNDLED_OUT}" | python3 -c "
import sys, json
d = json.load(sys.stdin)
assert d['status'] == 'error'
assert d['error']['code'] == 'PROFILE_NOT_FOUND', f\"Got: {d['error']['code']}\"
" 2>/dev/null; then
    pass "mihomo binary is bundled (find_mihomo via sys._MEIPASS)"
else
    # Check if it's at least getting past find_mihomo
    if echo "${BUNDLED_OUT}" | grep -q "MIHOMO_NOT_FOUND"; then
        fail "mihomo binary is bundled" "Got MIHOMO_NOT_FOUND — mihomo not in bundle"
    else
        fail "mihomo bundled check" "Unexpected output: ${BUNDLED_OUT}"
    fi
fi


# ══ Summary ═══════════════════════════════════════════════════
echo ""
echo "═══════════════════════════════════════════════════════════"
echo "  Results: ${PASS} passed, ${FAIL} failed, ${TOTAL} total"
echo "═══════════════════════════════════════════════════════════"

[ "${FAIL}" -eq 0 ]
