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

IMAGE="${OPENPLL_APPTAINER_IMAGE:-$ROOT_DIR/build/apptainer/openpll-release-modern.sif}"
DEF="${OPENPLL_APPTAINER_DEF:-$ROOT_DIR/apptainer/openpll-release-modern.def}"
ACTION="${1:-audit}"
if (($#)); then
    shift
fi

usage() {
    cat <<'EOF'
Usage: scripts/apptainer_reproduce_latest_release.sh ACTION [reproduce-options]

Actions:
  build            Build build/apptainer/openpll-release-modern.sif.
  audit            Run the v8 release audit inside the container.
  physical-audit   Audit rebuilt physical artifacts using the current PDK.
  modern-audit     Audit the separate modern-Ciel five-mode TT release evidence.
  modern-rebuild   Rebuild and audit the separate modern-Ciel five-mode release.
  rebuild          Regenerate v8 release artifacts inside the container, then audit.
  clean-rebuild    Same as rebuild, but remove generated v8 artifacts first.
  shell            Open an interactive shell in the container at /work/OpenPLL.

Common environment:
  APPTAINER or singularity              Container engine override.
  OPENPLL_APPTAINER_IMAGE               SIF path override.
  OPENPLL_APPTAINER_BUILD_FLAGS         Extra flags for apptainer build.
  OPENPLL_APPTAINER_RUN_FLAGS           Extra exec flags, default --userns --writable-tmpfs.
  The image contains LibreLane, Sky130, Nix tools, and upstream MPI Xyce.
  Only this OpenPLL checkout is mounted from the host.

Any extra arguments after audit/physical-audit/rebuild/clean-rebuild are forwarded to
scripts/reproduce_latest_release.sh inside the container.
EOF
}

if [[ "$ACTION" == "-h" || "$ACTION" == "--help" ]]; then
    usage
    exit 0
fi

if [[ "$ACTION" == "build" ]]; then
    mkdir -p "$(dirname "$IMAGE")"
    # shellcheck disable=SC2206
    build_flags=(--force ${OPENPLL_APPTAINER_BUILD_FLAGS:-})
    base_image="$ROOT_DIR/build/apptainer/openpll-release-base.sif"
    base_def="$ROOT_DIR/apptainer/openpll-release-base.def"
    if [[ ! -f "$base_image" || "$base_def" -nt "$base_image" ]]; then
        "$ENGINE" build "${build_flags[@]}" "$base_image" "$base_def"
    fi
    xyce_base_image="$ROOT_DIR/build/apptainer/openpll-xyce-base.sif"
    xyce_base_def="$ROOT_DIR/apptainer/openpll-xyce-base.def"
    if [[ ! -f "$xyce_base_image" || "$xyce_base_def" -nt "$xyce_base_image" || "$base_image" -nt "$xyce_base_image" ]]; then
        "$ENGINE" build "${build_flags[@]}" "$xyce_base_image" "$xyce_base_def"
    fi
    upstream_image="$ROOT_DIR/build/apptainer/openpll-release.sif"
    upstream_def="$ROOT_DIR/apptainer/openpll-release.def"
    if [[ ! -f "$upstream_image" || "$upstream_def" -nt "$upstream_image" || "$xyce_base_image" -nt "$upstream_image" ]]; then
        "$ENGINE" build "${build_flags[@]}" "$upstream_image" "$upstream_def"
    fi
    exec "$ENGINE" build "${build_flags[@]}" "$IMAGE" "$DEF"
fi

[[ -f "$IMAGE" ]] || {
    echo "ERROR: missing Apptainer image: $IMAGE" >&2
    echo "Build it with: scripts/apptainer_reproduce_latest_release.sh build" >&2
    exit 1
}

binds=("$ROOT_DIR:/work/OpenPLL")
envs=(
    "OPENPLL_RELEASE_TAG=${OPENPLL_RELEASE_TAG:-v8}"
    "OPENPLL_EXPECTED_LIBRELANE_COMMIT=${OPENPLL_EXPECTED_LIBRELANE_COMMIT:-0f39aab99009d4a81ee3f863f0da9ca2f0b43a99}"
    "OPENPLL_EXPECTED_CIEL_SKY130_VERSION=${OPENPLL_EXPECTED_CIEL_SKY130_VERSION:-1689ac3f2dc763876eaf967227c7dfe831b031ae}"
    "LIBRELANE_ROOT=/opt/librelane"
    "CIEL_SKY130_ROOT=/opt/pdk/ciel/sky130"
    "XYCE_MPI_ROOT=/opt/xyce"
    "XYCE_MIXED_BUILD_DIR=/opt/xyce-build"
    "NIX_REMOTE=local"
    "PATH=/opt/xyce/bin:/nix/var/nix/profiles/default/bin:/usr/local/bin:/usr/bin:/bin:/opt/ciel-venv/bin"
)

# Nix needs to update profile metadata even when all tools are in the SIF.
# --writable-tmpfs gives it an ephemeral overlay without host store binds.
# shellcheck disable=SC2206
run_flags=(${OPENPLL_APPTAINER_RUN_FLAGS:---userns --writable-tmpfs})
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
    physical-audit)
        exec "$ENGINE" "${exec_args[@]}" "$IMAGE" /work/OpenPLL/scripts/reproduce_latest_release.sh physical-audit "$@"
        ;;
    modern-audit)
        exec "$ENGINE" "${exec_args[@]}" "$IMAGE" /bin/bash /work/OpenPLL/scripts/reproduce_modern_25mhz_release.sh audit
        ;;
    modern-rebuild)
        exec "$ENGINE" "${exec_args[@]}" "$IMAGE" /bin/bash /work/OpenPLL/scripts/reproduce_modern_25mhz_release.sh rebuild
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
