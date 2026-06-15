#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

ENGINE="${APPTAINER:-}"
if [[ -z "$ENGINE" ]]; then
    if command -v apptainer >/dev/null 2>&1; then
        ENGINE="apptainer"
    elif command -v singularity >/dev/null 2>&1; then
        ENGINE="singularity"
    else
        echo "ERROR: neither apptainer nor singularity is installed" >&2
        exit 1
    fi
fi

IMAGE="${OPENPLL_APPTAINER_IMAGE:-$ROOT_DIR/build/apptainer/openpll-release.sif}"
DEF="${OPENPLL_APPTAINER_DEF:-$ROOT_DIR/apptainer/openpll-release.def}"
ACTION="${1:-audit}"
if (($#)); then
    shift
fi

usage() {
    cat <<'EOF'
Usage: scripts/apptainer_reproduce_latest_release.sh ACTION [reproduce-options]

Actions:
  build            Build build/apptainer/openpll-release.sif.
  audit            Run the v8 release audit inside the container.
  rebuild          Regenerate v8 release artifacts inside the container, then audit.
  clean-rebuild    Same as rebuild, but remove generated v8 artifacts first.
  shell            Open an interactive shell in the container at /work/OpenPLL.

Common environment:
  APPTAINER or singularity              Container engine override.
  OPENPLL_APPTAINER_IMAGE               SIF path override.
  OPENPLL_APPTAINER_BUILD_FLAGS         Extra flags for apptainer build.
  OPENPLL_APPTAINER_RUN_FLAGS           Extra exec flags, default --userns.
  LIBRELANE_ROOT                        Host LibreLane checkout; default auto-detected.
  CIEL_SKY130_ROOT                      Host Ciel Sky130 root; default $HOME/.volare/ciel/sky130.
  XYCE_MPI_ROOT                         Host MPI Xyce prefix; default $HOME/.local/xyce-mpi.

Any extra arguments after audit/rebuild/clean-rebuild are forwarded to
scripts/reproduce_latest_release.sh inside the container.
EOF
}

resolve_dir() {
    local path="$1"
    [[ -n "$path" ]] || return 1
    if [[ -d "$path" ]]; then
        cd "$path" && pwd
    else
        return 1
    fi
}

if [[ "$ACTION" == "-h" || "$ACTION" == "--help" ]]; then
    usage
    exit 0
fi

if [[ "$ACTION" == "build" ]]; then
    mkdir -p "$(dirname "$IMAGE")"
    # shellcheck disable=SC2206
    build_flags=(--force ${OPENPLL_APPTAINER_BUILD_FLAGS:-})
    exec "$ENGINE" build "${build_flags[@]}" "$IMAGE" "$DEF"
fi

[[ -f "$IMAGE" ]] || {
    echo "ERROR: missing Apptainer image: $IMAGE" >&2
    echo "Build it with: scripts/apptainer_reproduce_latest_release.sh build" >&2
    exit 1
}

if [[ -z "${LIBRELANE_ROOT:-}" ]]; then
    for candidate in ../librelane ../../librelane "$HOME/sources/librelane"; do
        if resolved="$(resolve_dir "$candidate")"; then
            LIBRELANE_ROOT="$resolved"
            break
        fi
    done
fi
CIEL_SKY130_ROOT="${CIEL_SKY130_ROOT:-$HOME/.volare/ciel/sky130}"
XYCE_MPI_ROOT="${XYCE_MPI_ROOT:-$HOME/.local/xyce-mpi}"

binds=("$ROOT_DIR:/work/OpenPLL")
envs=(
    "OPENPLL_RELEASE_TAG=${OPENPLL_RELEASE_TAG:-v8}"
    "OPENPLL_EXPECTED_LIBRELANE_COMMIT=${OPENPLL_EXPECTED_LIBRELANE_COMMIT:-0f39aab99009d4a81ee3f863f0da9ca2f0b43a99}"
    "OPENPLL_EXPECTED_CIEL_SKY130_VERSION=${OPENPLL_EXPECTED_CIEL_SKY130_VERSION:-7519dfb04400f224f140749cda44ee7de6f5e095}"
    "CIEL_SKY130_ROOT=$CIEL_SKY130_ROOT"
    "XYCE_MPI_ROOT=$XYCE_MPI_ROOT"
)

if [[ -n "${LIBRELANE_ROOT:-}" && -d "$LIBRELANE_ROOT" ]]; then
    binds+=("$LIBRELANE_ROOT:/work/librelane")
    envs+=("LIBRELANE_ROOT=/work/librelane")
else
    echo "WARNING: LIBRELANE_ROOT was not found; set it before running rebuild/audit" >&2
fi

[[ -d "$CIEL_SKY130_ROOT" ]] && binds+=("$CIEL_SKY130_ROOT:$CIEL_SKY130_ROOT")
[[ -d "$XYCE_MPI_ROOT" ]] && binds+=("$XYCE_MPI_ROOT:$XYCE_MPI_ROOT")
[[ -d /nix ]] && binds+=("/nix:/nix")
[[ -d /etc/nix ]] && binds+=("/etc/nix:/etc/nix")
[[ -d /usr/local ]] && binds+=("/usr/local:/usr/local")

# --userns is the safest default for unprivileged SingularityCE/Apptainer
# installs; set OPENPLL_APPTAINER_RUN_FLAGS="" if your site requires setuid mode.
# shellcheck disable=SC2206
run_flags=(${OPENPLL_APPTAINER_RUN_FLAGS:---userns})
exec_args=(exec "${run_flags[@]}" --cleanenv --pwd /work/OpenPLL)
for bind in "${binds[@]}"; do
    exec_args+=(--bind "$bind")
done
for env in "${envs[@]}"; do
    exec_args+=(--env "$env")
done

case "$ACTION" in
    audit)
        exec "$ENGINE" "${exec_args[@]}" "$IMAGE" /work/OpenPLL/scripts/reproduce_latest_release.sh audit "$@"
        ;;
    rebuild)
        exec "$ENGINE" "${exec_args[@]}" "$IMAGE" /work/OpenPLL/scripts/reproduce_latest_release.sh rebuild "$@"
        ;;
    clean-rebuild)
        exec "$ENGINE" "${exec_args[@]}" "$IMAGE" /work/OpenPLL/scripts/reproduce_latest_release.sh rebuild --clean-generated "$@"
        ;;
    shell)
        exec "$ENGINE" "${exec_args[@]}" "$IMAGE" /bin/bash
        ;;
    *)
        usage >&2
        exit 1
        ;;
esac
