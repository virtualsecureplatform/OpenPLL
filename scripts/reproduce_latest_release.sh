#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

MODE="audit"
CLEAN_GENERATED=0
REQUIRE_RELEASE_TAG=0
SKIP_ENV_CHECK=0

EXPECTED_RELEASE="${OPENPLL_RELEASE_TAG:-v8}"
EXPECTED_LIBRELANE_COMMIT="${OPENPLL_EXPECTED_LIBRELANE_COMMIT:-0f39aab99009d4a81ee3f863f0da9ca2f0b43a99}"
EXPECTED_CIEL_VERSION="${OPENPLL_EXPECTED_CIEL_SKY130_VERSION:-7519dfb04400f224f140749cda44ee7de6f5e095}"

usage() {
    cat <<'EOF'
Usage: scripts/reproduce_latest_release.sh [audit|rebuild] [options]

Modes:
  audit            Check the current generated v8 release artifacts.
  rebuild          Regenerate the v8 release artifacts, then run the release gate.

Options:
  --clean-generated       Remove generated v8 build/runs directories before rebuild.
  --require-release-tag   Fail unless HEAD is exactly OPENPLL_RELEASE_TAG.
  --skip-env-check        Skip PDK/LibreLane/tool version checks.
  -h, --help              Show this help.

Environment:
  OPENPLL_RELEASE_TAG                    Expected OpenPLL release tag, default v8.
  OPENPLL_EXPECTED_LIBRELANE_COMMIT      Expected LibreLane commit.
  OPENPLL_EXPECTED_CIEL_SKY130_VERSION   Expected Ciel Sky130 PDK version.
  OPENPLL_ALLOW_LIBRELANE_MISMATCH=1     Warn instead of failing on LibreLane mismatch.
  OPENPLL_ALLOW_PDK_MISMATCH=1           Warn instead of failing on PDK mismatch.
  LIBRELANE_ROOT                         LibreLane checkout, default auto-detected.
  CIEL_SKY130_ROOT                       Ciel Sky130 root, default $HOME/.volare/ciel/sky130.
EOF
}

log() {
    printf '\n[%s] %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "$*"
}

run() {
    log "RUN: $*"
    "$@"
}

die() {
    echo "ERROR: $*" >&2
    exit 1
}

warn_or_die() {
    local allow="$1"
    shift
    if [[ "$allow" == "1" ]]; then
        echo "WARNING: $*" >&2
    else
        die "$*"
    fi
}

while (($#)); do
    case "$1" in
        audit|rebuild)
            MODE="$1"
            ;;
        --clean-generated)
            CLEAN_GENERATED=1
            ;;
        --require-release-tag)
            REQUIRE_RELEASE_TAG=1
            ;;
        --skip-env-check)
            SKIP_ENV_CHECK=1
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            die "unknown argument: $1"
            ;;
    esac
    shift
done

if [[ "$MODE" == "audit" && "$CLEAN_GENERATED" == "1" ]]; then
    die "--clean-generated is only valid with rebuild"
fi

if [[ -z "${LIBRELANE_ROOT:-}" ]]; then
    for candidate in ../librelane ../../librelane "$HOME/sources/librelane"; do
        if [[ -d "$candidate" ]]; then
            LIBRELANE_ROOT="$(cd "$candidate" && pwd)"
            break
        fi
    done
fi
export LIBRELANE_ROOT="${LIBRELANE_ROOT:-}"
export CIEL_SKY130_ROOT="${CIEL_SKY130_ROOT:-$HOME/.volare/ciel/sky130}"

check_cmd() {
    command -v "$1" >/dev/null 2>&1 || die "missing required command: $1"
}

check_release_checkout() {
    if ! git rev-parse --git-dir >/dev/null 2>&1; then
        echo "WARNING: not a git checkout; release tag check skipped" >&2
        return
    fi
    if ! git rev-parse -q --verify "refs/tags/$EXPECTED_RELEASE" >/dev/null; then
        echo "WARNING: expected release tag $EXPECTED_RELEASE is not present locally" >&2
        return
    fi
    local head release_commit
    head="$(git rev-parse HEAD)"
    release_commit="$(git rev-list -n 1 "$EXPECTED_RELEASE")"
    if [[ "$head" != "$release_commit" ]]; then
        if [[ "$REQUIRE_RELEASE_TAG" == "1" ]]; then
            die "HEAD is $head, but $EXPECTED_RELEASE is $release_commit"
        fi
        echo "WARNING: HEAD is not exactly $EXPECTED_RELEASE; reproducing with current checkout" >&2
    fi
}

check_environment() {
    check_cmd make
    check_cmd python3
    check_cmd git
    check_cmd iverilog
    check_cmd vvp
    check_cmd Xyce
    check_cmd nix-shell

    [[ -n "$LIBRELANE_ROOT" && -d "$LIBRELANE_ROOT" ]] || die "LIBRELANE_ROOT is not set to a directory"
    if git -C "$LIBRELANE_ROOT" rev-parse HEAD >/dev/null 2>&1; then
        local actual_librelane
        actual_librelane="$(git -C "$LIBRELANE_ROOT" rev-parse HEAD)"
        if [[ "$actual_librelane" != "$EXPECTED_LIBRELANE_COMMIT" ]]; then
            warn_or_die "${OPENPLL_ALLOW_LIBRELANE_MISMATCH:-0}" \
                "LibreLane commit is $actual_librelane, expected $EXPECTED_LIBRELANE_COMMIT"
        fi
    else
        echo "WARNING: cannot read LibreLane git commit under $LIBRELANE_ROOT" >&2
    fi

    [[ -d "$CIEL_SKY130_ROOT" ]] || die "CIEL_SKY130_ROOT is not a directory: $CIEL_SKY130_ROOT"
    if [[ -f "$CIEL_SKY130_ROOT/current" ]]; then
        local actual_pdk
        actual_pdk="$(tr -d '[:space:]' < "$CIEL_SKY130_ROOT/current")"
        if [[ "$actual_pdk" != "$EXPECTED_CIEL_VERSION" ]]; then
            warn_or_die "${OPENPLL_ALLOW_PDK_MISMATCH:-0}" \
                "Ciel Sky130 current version is $actual_pdk, expected $EXPECTED_CIEL_VERSION"
        fi
    else
        echo "WARNING: $CIEL_SKY130_ROOT/current is missing; Makefile will select newest versions/*" >&2
    fi

    run make check-pdk-stdcell
}

clean_generated() {
    log "Removing generated v8 release artifacts"
    if [[ -d build ]]; then
        find build -mindepth 1 -maxdepth 1 ! -name apptainer -exec rm -rf {} +
    fi
    rm -rf openlane/IntegerPLL_DCO_EINVP_COARSE/runs
    rm -rf openlane/IntegerPLL_BBPD/runs
    rm -rf openlane/IntegerPLL_DigitalCore/runs/librelane_signoff_force127_s4a2
    rm -rf openlane/IntegerPLL_HardMacroTop_EINVP/runs
    rm -rf openlane/IntegerPLL_HardMacroTop_EINVP_25MHzConfigured/runs
}

rebuild_release() {
    if [[ "$CLEAN_GENERATED" == "1" ]]; then
        clean_generated
    fi

    run make dco-einvp-coarse-librelane-signoff
    run make check-dco-einvp-coarse-librelane-signoff
    run make dco-einvp-coarse-magic-rcx

    run make bbpd-librelane-signoff
    run make bbpd-magic-rcx

    run make librelane-signoff-force127-s4a2
    run make check-librelane-signoff-force127-s4a2

    run make hardtop-einvp-librelane-signoff
    run make check-hard-macro-top-einvp-signoff
    run make check-hard-macro-top-einvp-spice

    run make hardtop-einvp-configured-librelane-signoff
    run make check-configured-hard-macro-top-einvp-signoff

    run make xyce-pll-mixed-signal-25mhz-targets
    run make xyce-pll-postlayout-dco-mixed-25mhz-nearseed-smokes
}

check_release_checkout
if [[ "$SKIP_ENV_CHECK" != "1" ]]; then
    check_environment
fi

case "$MODE" in
    audit)
        run make check-sky130-pll-25mhz-release
        ;;
    rebuild)
        rebuild_release
        run make check-sky130-pll-25mhz-release
        ;;
    *)
        die "unsupported mode: $MODE"
        ;;
esac

log "OpenPLL $EXPECTED_RELEASE reproduction $MODE completed"
