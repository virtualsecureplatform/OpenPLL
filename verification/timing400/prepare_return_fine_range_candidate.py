#!/usr/bin/env python3
"""Prepare one unadopted return-stage fine-load extension for range-gap testing.

Add80 existing einvp_1 load cells to mirror_pass_n[0]. Choose controls outside
those used by the coarse1 bank to avoid stacking new transitions on the same
fine bits. All original cells, ports and fine/coarse encodings are retained.
The return node is logically constant at coarse0; analog coupling, range,
resolution, timing, power and jitter remain unqualified at every PVT point.
"""
from datetime import datetime,timezone
import json
from pathlib import Path
import shutil
from run_dco_qualification import ROOT,sha,save

BASE_TOP='IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_BOOST8_OSC8_LOAD36_C1FINE160'
TOP='IntegerPLL_DCO_EINVP_C1FINE160_RETURNFINE80'


def main():
    base=ROOT/'build/timing400/release_001';gate=base/'tt100_endpoint_collection_001/assessment.json'
    g=json.loads(gate.read_text());assert g['both_native_endpoints_collected'] and not g['intrinsic_tt100_ordered_range_brackets_target']
    source=ROOT/'sky130/IntegerPLL_DCO_einvp_coarse_v5_turn10_boost8_osc8_load36_c1fine160_sky130.v'
    assert sha(source)=='48b1c6cc7b749b6961bd91155b560deaa46297f787a27b150b8cd1feb85520c9'
    parent=ROOT/'openlane'/BASE_TOP;config=json.loads((parent/'config.json').read_text())
    c1={255*i//160 for i in range(160)};free=sorted(set(range(255))-c1);assert len(c1)==160 and len(free)==95
    indices=[free[95*i//80] for i in range(80)];assert len(set(indices))==80 and set(indices).isdisjoint(c1)
    function='    function integer return_fine_index;\n        input integer unit_index;\n        begin\n            case (unit_index)\n'
    function+=''.join(f'                {i}: return_fine_index = {control};\n' for i,control in enumerate(indices))
    function+='                default: return_fine_index = 0;\n            endcase\n        end\n    endfunction\n'
    bank='''
    // Experimental fine-range extension on the weakest common return stage.
    // New load outputs are independent floating dummies; no new ring driver.
    wire [79:0] return_fine_dummy;
'''+function+'''
    genvar return_fine;
    generate
        for (return_fine = 0; return_fine < 80; return_fine = return_fine + 1) begin : gen_return_fine_load
            (* keep = "true", dont_touch = "true" *)
            sky130_fd_sc_hd__einvp_1 load (
                `INTEGERPLL_SKY130_CELL_PG
                .A(mirror_pass_n[0]),
                .TE(DCO_THERM[return_fine_index(return_fine)]),
                .Z(return_fine_dummy[return_fine])
            );
        end
    endgenerate
'''
    text=source.read_text();assert text.count('\nendmodule')==1
    proposed=text.replace(BASE_TOP,TOP).replace('\nendmodule','\n'+bank+'\nendmodule')
    target=ROOT/'sky130/IntegerPLL_DCO_einvp_c1fine160_returnfine80_sky130.v';directory=ROOT/'openlane'/TOP
    out=base/'return_fine_range_candidate_001';assert not any(p.exists() for p in [target,directory,out])
    target.write_text(proposed);directory.mkdir();out.mkdir()
    config.update(DESIGN_NAME=TOP,VERILOG_FILES=['dir::../../sky130/'+target.name],PL_TARGET_DENSITY_PCT=68)
    save(directory/'config.json',config)
    for auxiliary in ['pin_order.cfg','no_clock.sdc']:shutil.copyfile(parent/auxiliary,directory/auxiliary)
    control_records=[]
    for coarse in range(48):
        coarse_bits=[int(i<coarse) for i in range(47)]
        for fine in range(256):
            fine_bits=[int(i>=fine) for i in range(255)]
            count=sum(fine_bits[i] for i in indices)
            assert count==sum(i>=fine for i in indices)
            for ret1 in [0,1]:
                return0=not ((not ret1) and coarse_bits[0])
                assert return0==(True if coarse==0 else bool(ret1))
            if coarse==0:control_records.append(dict(fine=fine,enabled_return_loads=count))
    assert control_records[0]['enabled_return_loads']==80 and control_records[-1]['enabled_return_loads']==0
    assert all(a['enabled_return_loads']>=b['enabled_return_loads'] for a,b in zip(control_records,control_records[1:]))
    # Preserve the original transistor/cell topology after removing only the
    # deliberately appended bank and undoing the new module name.
    reconstructed=proposed.replace('\n'+bank+'\nendmodule','\nendmodule').replace(TOP,BASE_TOP)
    assert reconstructed==text
    inputs=[Path(__file__).resolve(),source,parent/'config.json',parent/'pin_order.cfg',parent/'no_clock.sdc',gate,
        ROOT/'sky130/sky130_fd_sc_hd_pll_blackbox.v',ROOT/'verification/release_requirements_400mhz.json',ROOT/'verification/release_plan_400mhz.json']
    save(out/'plan.json',dict(created_utc=datetime.now(timezone.utc).isoformat(),input_sha256={str(p):sha(p) for p in inputs},
        candidate_top=TOP,candidate_source=str(target),candidate_source_sha256=sha(target),candidate_config=str(directory/'config.json'),
        candidate_config_sha256=sha(directory/'config.json'),original_candidate_unmodified=True,
        return_load_cells=80,cell_master='sky130_fd_sc_hd__einvp_1',load_input='mirror_pass_n[0]',control_indices=indices,
        controls_disjoint_from_coarse1_load_controls=True,original_cell_statements_preserved=True,
        all_public_port_and_encoding_changes=False,coarse_fine_encoding_states_checked=48*256,
        coarse0_return_input_logically_constant=True,coarse1_return_drive_includes_existing_parallel_stages=True,
        illustrative_enabled_loads=control_records,physical_layout_started=False,native_analog_started=False,
        range_qualified=False,full_nominal15pvt_qualification_required=True,physical_timing_qualified=False,release_qualified=False,adopted=False,
        next='Elaborate and verify added-cell connectivity before any physical implementation. Await adjacent-band evidence before adoption decisions.',scope=__doc__))
    print('Prepared isolated80-load return-bank candidate; original source and release criteria unchanged; physical/analog validation not started.')

if __name__=='__main__':main()
