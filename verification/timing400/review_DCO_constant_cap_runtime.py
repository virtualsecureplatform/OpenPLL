#!/usr/bin/env python3
"""Retain source/runtime evidence; infer no unmeasured device timing fraction."""
from datetime import datetime,timezone
import json
import math
import os
from pathlib import Path
import shutil
import time
from compile_local_C_operators_v2 import digest,save
from record_qualification_progress_045 import process
root=Path(__file__).resolve().parents[2];base=root/'build/timing400/release_001'
point=base/'DCO_domain_nom_tt27_c0_f247_80ns_bounded_reuse_gear_001'
launch=json.loads((point/'launch.json').read_text());pid=launch['pid'];identity=process(pid)
assert identity['live'] and identity['argv']==launch['command']
with (point/'native.log').open('rb') as stream:raw=stream.read()
raw=raw[:raw.rfind(b'\n')+1];solves=[]
for line in raw.decode().splitlines():
    if line.startswith('OpenPLL_wire_PC call='):
        fields=dict(token.split('=',1) for token in line.split()[1:])
        assert int(fields['call'])==len(solves)+1 and int(fields['status'])==0
        assert math.isfinite(float(fields['scaled_true_relative_residual'])) and float(fields['scaled_true_relative_residual'])<=1e-12
        solves.append(fields)
assert solves
stat=Path(f'/proc/{pid}/stat').read_text().rsplit(')',1)[1].split();ticks=os.sysconf('SC_CLK_TCK')
now=time.clock_gettime(time.CLOCK_BOOTTIME);elapsed=now-int(stat[19])/ticks
reported=sum(float(s['seconds']) for s in solves)
assert 0<reported<elapsed and process(pid)['argv']==identity['argv']
source=base/'wire_preconditioned_Xyce_001/source/src/DeviceModelPKG/OpenModels'
cap=source/'N_DEV_Capacitor.C';header=source/'N_DEV_Capacitor.h';ext=source/'N_DEV_GeneralExternal.C'
cap_text=cap.read_text();header_text=header.read_text();ext_text=ext.read_text()
assert 'bool Master::updateState' in cap_text and 'bool Master::loadDAEVectors' in cap_text
assert '//staVec[ci.li_QState] = ci.q0;' in cap_text
assert 'virtual bool updateSecondaryState (double * staDerivVec, double * stoVec) { return true; }' in header_text
assert 'dQdXMat_[row][jacStamp_[row][col]]' in ext_text
assert 'if (dQdXMat_[i].size() != QVec_.size())' in ext_text
out=base/'DCO_constant_cap_runtime_review_001';out.mkdir(exist_ok=False)
snapshot=out/'native_log_prefix.log';snapshot.write_bytes(raw)
proof=dict(observed_utc=datetime.now(timezone.utc).isoformat(),native_identity=identity,
    native_elapsed_s=elapsed,reported_completed_solver_wall_s=reported,reported_solves=len(solves),
    reported_solver_wall_fraction_of_elapsed_including_setup=reported/elapsed,
    pending_solver_call_time_not_included=True,remainder_includes_setup_device_integration_IO_and_other_work=True,
    capacitor_time_fraction_measured=False,capacitor_master_already_uses_bulk_loops=True,
    constant_cap_charge_state_write_is_commented_out=True,capacitor_master_secondary_state_is_noop=True,
    generic_external_interface_has_sparse_stamp_but_dense_matrix_payload=True,
    illustrative_dense_double_matrix_bytes_at_native_dimension=174551**2*8,
    illustrative_matrix_dimension_is_not_measured_external_port_count=True,
    perf_event_paranoid=int(Path('/proc/sys/kernel/perf_event_paranoid').read_text()),host_gdb_available=shutil.which('gdb') is not None,
    instruction_level_profile_obtained=False,live_process_started_stopped_or_modified=False,
    optimization_selected=False,release_qualified=False,adopted=False,
    next='Benchmark an opt-in compact constant-capacitor path with literal fixed-parameter eligibility and original contribution order, leaving IC/dependent/probed cases on the stock path; do not adopt without native equivalence controls and measured gain.',
    input_sha256={str(p):digest(p) for p in (Path(__file__).resolve(),point/'launch.json',snapshot,cap,header,ext)})
save(out/'assessment.json',proof)
print(json.dumps({k:proof[k] for k in ['reported_solves','native_elapsed_s','reported_completed_solver_wall_s','reported_solver_wall_fraction_of_elapsed_including_setup','capacitor_time_fraction_measured']}))
