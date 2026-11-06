"""Build a diagnostic detector/publication composition in the PLLOUT clock frame."""
import argparse,json,math,re,statistics
from pathlib import Path
from common_v3 import save,sha,verify


def build(detector,publication,frame,output):
    if output.exists():raise FileExistsError(output)
    m=json.loads((publication/'assessment.json').read_text());verify(m['input_sha256']);verify(m['artifacts'])
    params=json.loads((publication/'parameters.json').read_text());f=json.loads(frame.read_text());verify(f['input_sha256'])
    # A sampled TT timing conversion, not a corner-wide uncertainty envelope.
    if params['operating_point']!={'corner':'tt','temperature_c':27,'supply_v':1.8}:raise ValueError('recorded TT clock frame required')
    transport=statistics.median(x['transport_ps'] for x in f['clock_pairs']['first'])/1000
    delays={}
    for role in ['up','dn']:
        delays[role]={}
        for direction in ['rise','fall']:
            delay=params['publication_delays'][role][direction]['nominal_ns']-transport
            if not math.isfinite(delay) or not 0<delay<1:raise ValueError('positive sub-ns effective root publication delay required')
            delays[role][direction]=delay
    source=detector.read_text()
    if len(re.findall(r'\bmodule Prototype400DetectorModel\b',source))!=1:raise ValueError('unique raw detector module required')
    source=source.replace('module Prototype400DetectorModel','module Prototype400RawDetectorModel',1)
    source+='''
module Prototype400PublicationChannel #(
    parameter real RISE_Q_NS=0.2, FALL_Q_NS=0.2
)(input wire RAW,RESET_N,output reg OUT=0);
    integer epoch=0,ordinal=0;
    real active_delay=0;
    task automatic deliver(input integer ticket,input reg value,input real latency);
        begin #(latency); if(RESET_N && epoch==ticket) OUT<=value; end
    endtask
    always @(RAW or negedge RESET_N) begin
        if(!RESET_N) begin epoch=epoch+1;ordinal=0;active_delay=0;OUT<=0;end
        else begin
            if($isunknown(RAW)) $fatal(1,"unresolved publication input");
            if(RAW) begin active_delay=(ordinal%2==0)?RISE_Q_NS:FALL_Q_NS;ordinal=ordinal+1;end
            fork deliver(epoch,RAW,active_delay);join_none
        end
    end
endmodule
module Prototype400DetectorModel(input wire REFCLK,FEEDBACKCLK,RESET_N,output wire [1:0] BBPD);
    wire [1:0] raw;
    Prototype400RawDetectorModel detector(.REFCLK(REFCLK),.FEEDBACKCLK(FEEDBACKCLK),.RESET_N(RESET_N),.BBPD(raw));
'''
    for role,index in [('up',1),('dn',0)]:
        source+=f'    Prototype400PublicationChannel #(.RISE_Q_NS({delays[role]["rise"]:.17g}),.FALL_Q_NS({delays[role]["fall"]:.17g})) {role}(.RAW(raw[{index}]),.RESET_N(RESET_N),.OUT(BBPD[{index}]));\n'
    source+='endmodule\n';output.mkdir(parents=True);artifact=output/'detector.v';artifact.write_text(source)
    inputs=[detector,publication/'assessment.json',publication/'parameters.json',frame,Path(__file__).resolve()]
    save(output/'assessment.json',dict(input_sha256={str(p):sha(p) for p in inputs},artifacts={str(artifact):sha(artifact)},effective_publication_delay_ns=delays,subtracted_clock_transport_ns=transport,operating_point=params['operating_point'],scope='nominal diagnostic composition; physical receiver Q direction alternates at each same-channel detector rise',pulse_widths_preserved=True,reset_cancels_pending_publications=True,complete_controller_timing_qualified=False,uniform_uncertainty_bound_qualified=False,release_ready=False))
    print(json.dumps(delays))

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['detector','publication','frame','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();build(*(getattr(a,n).resolve() for n in ['detector','publication','frame','output']))
