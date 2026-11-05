#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Run outside a sandbox that denies Apptainer/MPI sockets.
# This 25 ns screen is diagnostic; it cannot qualify the approved 12--70 ns window.
set -euo pipefail

repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$repo"
output=build/modern_25mhz/v5_turn6_short_klu_external
mkdir -p "$output"

if ! apptainer exec --userns --writable-tmpfs --cleanenv \
    --pwd /work/OpenPLL --bind "$repo:/work/OpenPLL" \
    build/apptainer/openpll-release-modern.sif /bin/bash -lc '
        export OMP_NUM_THREADS=1
        python3 scripts/spice_dco_postlayout.py \
          --simulator xyce --xyce "/opt/xyce/bin/Xyce -linsolv KLU" \
          --xyce-mpi-procs 1 \
          --pdk-root /opt/pdk/ciel/sky130/versions/1689ac3f2dc763876eaf967227c7dfe831b031ae \
          --rcx-netlist build/modern_25mhz/v5_turn6_all_net_rc/IntegerPLL_DCO_EINVP_COARSE_V5_TURN6.reduced.spice \
          --subckt-name IntegerPLL_DCO_EINVP_COARSE_V5_TURN6 \
          --corner ss --vdd 1.62 --temperature-c 125 \
          --coarse-codes 0 --codes 247 \
          --sim-time-ns 25 --meas-start-ns 12 --timeout-s 900 \
          --build-dir build/modern_25mhz/v5_turn6_short_klu_external
    ' > "$output/campaign.log" 2>&1; then
    cat "$output/campaign.log" >&2
    exit 1
fi

PYTHONPATH="$repo/scripts" python3 - "$output" <<'PY'
import json
import sys
from pathlib import Path
from dco_calibration import measure

root = Path(sys.argv[1])
waveform = root / "dco_postlayout_ss_coarse_00_code_247.prn"
result = measure(waveform, 12, 25, 1.62, min_periods=3)
(root / "window_12_25_diagnostic.json").write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps(result, indent=2))
PY
