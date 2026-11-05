"""Bind conventional DCO RCX outputs to the macro GDS selected by the assembly."""
import argparse,json
from pathlib import Path
from common import ROOT,save,sha,verify


def run(output):
 output.mkdir(parents=True,exist_ok=False)
 layout=ROOT/'build/signoff400/startup_timing_filled_layout_002/assessment.json';a=json.loads(layout.read_text())
 candidates=[Path(p) for p in a['input_sha256'] if '/c1fine_range_001/final/gds/' in p]
 if len(candidates)!=1:raise ValueError('unique assembled DCO GDS required')
 selected=candidates[0];run=selected.parents[2]
 rcx_in=run/'47-openroad-rcx/state_in.json';rcx_out=run/'47-openroad-rcx/state_out.json'
 stream_in=run/'48-klayout-streamout/state_in.json';stream_out=run/'48-klayout-streamout/state_out.json'
 ri,ro,si,so=[json.loads(p.read_text()) for p in (rcx_in,rcx_out,stream_in,stream_out)]
 if any(x['odb']!=ri['odb'] or x['def']!=ri['def'] for x in (ro,si,so)):raise ValueError('RCX/stream-out routing lineage differs')
 if ro['spef']!=si['spef'] or ro['spef']!=so['spef']:raise ValueError('stream-out does not carry the same RCX outputs')
 streamed=Path(so['gds'])
 paths=[layout,selected,rcx_in,rcx_out,stream_in,stream_out,Path(ri['odb']),Path(ri['def']),streamed,Path(__file__).resolve()]
 result=[]
 for corner in ('nom','min','max'):
  source=Path(ro['spef'][corner+'_*']);final=run/'final/spef'/corner/source.name;paths.extend((source,final))
  if sha(source)!=sha(final):raise ValueError('final SPEF differs from RCX output')
  header=source.read_text().split('*NAME_MAP',1)[0]
  if '*C_UNIT 1 PF' not in header or '*R_UNIT 1 OHM' not in header:raise ValueError('unreviewed SPEF units')
  result.append(dict(interconnect_corner=corner,source=str(source),final=str(final),sha256=sha(source)))
 pins={str(p):sha(p) for p in paths}
 if pins[str(selected)]!=a['input_sha256'][str(selected)] or pins[str(selected)]!=pins[str(streamed)]:raise ValueError('assembled and RCX stream-out GDS differ')
 verify(pins)
 save(output/'assessment.json',dict(input_sha256=pins,conventional_interconnect_views=result,
  selected_DCO_GDS_matches_RCX_streamout=True,RCX_and_GDS_share_routed_database=True,
  RC_network_pin_binding_complete=False,parent_loading_complete=False,final_fill_effects_validated=False,
  validated_for_prototype=False,release_ready=False,production_qualified=False))

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True,type=Path)
 a=p.parse_args();run(a.output.resolve())
