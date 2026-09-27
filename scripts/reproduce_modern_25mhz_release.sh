#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
PDK_ROOT="${PDK_ROOT:-/opt/pdk/ciel/sky130/versions/1689ac3f2dc763876eaf967227c7dfe831b031ae}"
LIBRELANE_ROOT="${LIBRELANE_ROOT:-/opt/librelane}"
XYCE="${XYCE:-/opt/xyce/bin/Xyce}"
RCX="openlane/IntegerPLL_DCO_EINVP_COARSE/runs/modern_k016/rcx-magic/IntegerPLL_DCO_EINVP_COARSE.rcx.spice"
DRIVER_DIR="build/xyce_cinterface_smoke_mpi"
MODE="${1:-audit}"

run_flow() {
    local config="$1" tag="$2"
    nix-shell "$LIBRELANE_ROOT/shell.nix" --run \
        "librelane --manual-pdk --pdk-root '$PDK_ROOT' -p sky130A -s sky130_fd_sc_hd --condensed --hide-progress-bar --run-tag '$tag' --overwrite '$config'"
}

audit() {
    make check-sky130-modern-25mhz-release
}

rebuild() {
    [[ -d "$PDK_ROOT/sky130A" ]] || { echo "Missing modern Ciel PDK: $PDK_ROOT" >&2; exit 1; }
    [[ -x "$XYCE" ]] || { echo "Missing upstream Xyce: $XYCE" >&2; exit 1; }
    if [[ ! -f openlane/IntegerPLL_BBPD/runs/librelane_signoff/final/gds/IntegerPLL_BBPD.gds ]]; then
        make bbpd-librelane-signoff
    fi
    if [[ ! -f openlane/IntegerPLL_BBPD/runs/librelane_signoff/rcx-magic/IntegerPLL_BBPD.rcx.spice ]]; then
        make bbpd-magic-rcx
    fi
    if [[ ! -f openlane/IntegerPLL_DigitalCore/runs/librelane_signoff_force127_s4a2/final/gds/IntegerPLL_DigitalCore.gds ]]; then
        make librelane-signoff-force127-s4a2
    fi
    make check-librelane-signoff-force127-s4a2
    run_flow openlane/IntegerPLL_DCO_EINVP_COARSE/config_modern.json modern_k016
    DESIGN_DIR=openlane/IntegerPLL_DCO_EINVP_COARSE RUN_TAG=modern_k016 \
        LIBRELANE_ROOT="$LIBRELANE_ROOT" PDK_ROOT="$PDK_ROOT" ./scripts/dco_magic_rcx.sh

    local -a csv_args=()
    local target coarse code low high out
    for setting in 100:16:58 250:4:206 300:2:12 400:1:215 500:0:163; do
        IFS=: read -r target coarse code <<< "$setting"
        low=$((code - 8))
        high=$((code + 8))
        out="build/modern_25mhz/dco_${target}"
        python3 scripts/spice_dco_postlayout.py --simulator xyce --xyce "$XYCE" \
            --xyce-mpi-procs 4 --jobs 2 --timeout-s 1800 \
            --subckt-name IntegerPLL_DCO_EINVP_COARSE --rcx-netlist "$RCX" \
            --coarse-codes "$coarse" --codes "0,$low,$code,$high,255" \
            --sim-time-ns 70 --meas-start-ns 12 --step-ps 10 --resume --build-dir "$out"
        csv_args+=(--csv "$out/dco_postlayout_results.csv")
    done
    python3 scripts/calibrate_modern_25mhz.py --strong-load-count 16 \
        "${csv_args[@]}" \
        --setting 100:16:58 --setting 250:4:206 --setting 300:2:12 \
        --setting 400:1:215 --setting 500:0:163
    python3 scripts/generate_modern_25mhz.py
    make check-pll-25mhz-modern-rtl

    run_flow openlane/IntegerPLL_HardMacroTop_EINVP/config_modern.json modern_signoff
    python3 scripts/check_hard_macro_top_einvp.py --modern --require-signoff \
        --out-dir build/modern_25mhz/hardtop
    python3 scripts/check_hard_macro_top_spice.py --xyce "$XYCE" \
        --top IntegerPLL_HardMacroTop_EINVP --dco-subckt IntegerPLL_DCO_EINVP_COARSE \
        --spice openlane/IntegerPLL_HardMacroTop_EINVP/runs/modern_signoff/final/spice/IntegerPLL_HardMacroTop_EINVP.spice \
        --spef openlane/IntegerPLL_HardMacroTop_EINVP/runs/modern_signoff/final/spef/nom/IntegerPLL_HardMacroTop_EINVP.nom.spef \
        --metrics openlane/IntegerPLL_HardMacroTop_EINVP/runs/modern_signoff/final/metrics.json \
        --out-dir build/modern_25mhz/hardtop_spice
    run_flow openlane/IntegerPLL_HardMacroTop_EINVP_25MHzConfigured/config_modern.json modern_signoff
    python3 scripts/check_configured_hard_macro_top_einvp.py --modern --require-signoff \
        --out-dir build/modern_25mhz/configured

    make xyce-cinterface-static
    cmake -S tools/xyce_cinterface_smoke -B "$DRIVER_DIR" \
        -DCMAKE_CXX_COMPILER=/usr/bin/mpicxx -DXYCE_INSTALL_DIR=/opt/xyce \
        -DXYCE_BUILD_DIR=/opt/xyce-build -DXYCE_SOURCE_DIR=/opt/Xyce \
        -DTrilinos_DIR=/opt/trilinos/lib/cmake/Trilinos
    cmake --build "$DRIVER_DIR" -j 4
    for target in 100 250 300 400 500; do
        local -a hold_window=(--cycles 1 --measure-cycles 1 --sim-time-ns 92)
        if [[ "$target" == 100 || "$target" == 250 || "$target" == 500 ]]; then
            hold_window=(--cycles 1 --measure-cycles 2 --sim-time-ns 132)
        fi
        python3 scripts/xyce_pll_postlayout_dco_25mhz_hold_sweep.py \
            --driver "$DRIVER_DIR/xyce_pll_postlayout_dco_mixed_signal_smoke" \
            --pdk-root "$PDK_ROOT" --dco-rcx-netlist "$RCX" \
            --target-config sky130/modern_25mhz_targets.json --targets-mhz "$target" \
            "${hold_window[@]}" --max-step-ps 200 --cosim-step-ns 0.2 \
            --timeout-s 3600 --resume --build-dir "build/modern_25mhz/hold_$target"
        python3 scripts/xyce_pll_postlayout_dco_25mhz_nearseed_sweep.py \
            --driver "$DRIVER_DIR/xyce_pll_postlayout_dco_mixed_signal_smoke" \
            --pdk-root "$PDK_ROOT" --dco-rcx-netlist "$RCX" \
            --target-config sky130/modern_25mhz_targets.json --targets-mhz "$target" \
            --sides low,high --cycles 1 --measure-cycles 1 --sim-time-ns 92 \
            --max-step-ps 200 --cosim-step-ns 0.2 --timeout-s 3600 --resume \
            --build-dir "build/modern_25mhz/nearseed_$target"
    done
    python3 scripts/xyce_pll_25mhz_target_sweep.py \
        --driver "$DRIVER_DIR/xyce_pll_mixed_signal_smoke" \
        --dco-csv build/modern_25mhz/dco_measurements.csv \
        --target-config sky130/modern_25mhz_targets.json \
        --targets-mhz 100,250,300,400,500 --ki-values 16 --kp-values 4 \
        --init-offsets=-4,4 --cycles 24 --frac 2 --boost-shift 0 --boost-after 1 \
        --tol-code 4 --freq-tol-mhz 2 --late-window-cycles 8 \
        --max-late-code-span 16 --min-expected-decisions 1 --min-motion 1 \
        --require-waveform-quality --resume --timeout-s 1800 \
        --build-dir build/modern_25mhz/tracking
    audit
}

case "$MODE" in
    audit) audit ;;
    rebuild) rebuild ;;
    *) echo "Usage: $0 [audit|rebuild]" >&2; exit 2 ;;
esac
