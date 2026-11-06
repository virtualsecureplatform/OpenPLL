"""Record the actual source/layout discrepancy without relabeling old receipts."""
import argparse,json
from pathlib import Path
from common_v3 import ROOT,save,sha,verify,source_pins as legacy_pins
from selected_physical_rtl import source_pins as physical_pins


def run(output):
    if output.exists():raise FileExistsError(output)
    physical=physical_pins();legacy=legacy_pins();different=[]
    previous={Path(p).name:(p,d) for p,d in legacy.items() if p.endswith('.v')}
    for p,d in physical.items():
        if p.endswith('.v'):
            old,old_digest=previous[Path(p).name]
            if old_digest!=d:different.append(dict(name=Path(p).name,physical_source=p,physical_sha256=d,legacy_source=old,legacy_sha256=old_digest))
    if {r['name'] for r in different}!={'IntegerPLL_DigitalCore.v','IntegerPLL_ProgrammedCore.v'}:raise ValueError('unexpected source discrepancy; review before reuse')
    old=(ROOT/'rtl/prototype400/IntegerPLL_DigitalCore.v').read_text();new=(ROOT/'rtl/selected400/IntegerPLL_DigitalCore.v').read_text()
    if old.replace('reg [1:0] decision_q;\n            always @(posedge dlf_clk or negedge dlf_reset_n)','reg [1:0] decision_q;\n            always @(negedge dlf_clk or negedge dlf_reset_n)',1)!=new:raise ValueError('receiver code changed beyond the decision register edge')
    # This proves the receiver code is unchanged, not that the complete
    # controllers are equivalent or that any legacy loop result qualifies.
    pins=dict(physical,**legacy);pins[str(Path(__file__).resolve())]=sha(Path(__file__).resolve());verify(pins)
    save(output,dict(input_sha256=pins,different_sources=different,
        physical_configuration=dict(registered_decision_edge='negedge',MMD_REGISTER_CONFIG=0,MMD_CONFIG_PIPELINE=0,divider_source='FEEDBACK_DIVIDER'),
        legacy_configuration=dict(registered_decision_edge='posedge',MMD_REGISTER_CONFIG=1,MMD_CONFIG_PIPELINE=1,divider_source='local_divider'),
        DigitalCore_code_identical_except_decision_register_edge=True,
        receiver_only_observations_require_existing_local_scope=True,
        legacy_full_controller_results_qualify_physical_candidate=False,
        full_controller_native_correlation_complete=False,release_ready=False))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();run(a.output.resolve())
