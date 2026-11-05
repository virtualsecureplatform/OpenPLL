"""Fit an explicitly unqualified detector model to native level-sampling observations."""
import argparse
import json
from pathlib import Path
from common_v3 import PROFILE,save,sha,verify,source_pins
from review_prototype_BBPD_loaded_bias_v2 import decision


def predict(phase_ps,lookback_ps):
    first=10.1+phase_ps/1000;result=[]
    for ref in (10.1,50.1):
        sample=ref-lookback_ps/1000
        high=sample>=first and (sample-first)%40<20
        result.append('DN' if high else 'UP')
    return result


def fit(wide,bias):
    interval=bias['observed_transition_bracket_ps']
    if interval is None or not interval[0]<interval[1]<=0:raise ValueError('ordered observed loaded transition interval required')
    lookback=-(interval[0]+interval[1])/2;rise={r:[] for r in ('DN','UP')};fall={r:[] for r in ('DN','UP')};unresolved=[]
    for row in wide:
        actual=[r['decision'] for r in row['reference_decisions']]
        if actual!=predict(row['phase_ps'],lookback):raise ValueError('level-sampling model contradicts broad-phase native decisions')
    for row in bias['observations']:
        role=decision(row['outputs'],row['first_synchronizers'])
        if role is None:unresolved.append(row['phase_ps']);continue
        if predict(row['phase_ps'],lookback)!=[role,role]:raise ValueError('level-sampling model contradicts resolved loaded bias observations')
    for row in [*wide,*bias['observations']]:
        for role,values in row['outputs'].items():
            for key,base,dest in (('detector_rising_edges_ns',10.1,rise),('detector_falling_edges_ns',30.1,fall)):
                for t in values[key]:
                    anchor=base+40*int((t-base)//40);delay=t-anchor
                    if not 0<delay<20:raise ValueError('native detector latency outside reference half-cycle')
                    dest[role].append(delay)
    params=dict(lookback_ps=lookback,observed_transition_bracket_ps=interval,unresolved_bias_points_ps=unresolved,
        native_clock_latency_ns={},receiver_latency_included_in_detector_output=False,
        independent_model_holdouts_complete=False,qualified_uncertainty_bound=False)
    for role in ('DN','UP'):
        if not rise[role] or not fall[role]:raise ValueError('both polarities need native rise/fall observations')
        params['native_clock_latency_ns'][role]={}
        for edge,values in (('rise',rise[role]),('fall',fall[role])):
            params['native_clock_latency_ns'][role][edge]=dict(observed_interval=[min(values),max(values)],nominal=(min(values)+max(values))/2)
    return params


def render(p):
    latency=p['native_clock_latency_ns']
    return f'''`timescale 1ns/1ps
// Native measurement fit. Unqualified: receiver paths, unresolved aperture,
// numerical/model uncertainty and independent holdouts remain open.
module Prototype400DetectorModel #(
    parameter real LOOKBACK_NS={p['lookback_ps']/1000:.15g},
    parameter real DN_RISE_NS={latency['DN']['rise']['nominal']:.15g},
    parameter real DN_FALL_NS={latency['DN']['fall']['nominal']:.15g},
    parameter real UP_RISE_NS={latency['UP']['rise']['nominal']:.15g},
    parameter real UP_FALL_NS={latency['UP']['fall']['nominal']:.15g}
)(input wire REFCLK,FEEDBACKCLK,RESET_N,output reg [1:0] BBPD);
    wire feedback_delayed;
    assign #(LOOKBACK_NS) feedback_delayed=FEEDBACKCLK;
    integer epoch=0;
    initial BBPD=0;
    task automatic raise_output(input integer ticket,input reg sampled);
        begin
            if(sampled) begin
                #(DN_RISE_NS);
                if(RESET_N && epoch==ticket) BBPD<=2'b01;
            end else begin
                #(UP_RISE_NS);
                if(RESET_N && epoch==ticket) BBPD<=2'b10;
            end
        end
    endtask
    task automatic lower_output(input integer ticket,input integer index,input real delay_ns);
        begin
            #(delay_ns);
            if(RESET_N && epoch==ticket) BBPD[index]<=0;
        end
    endtask
    always @(posedge REFCLK or negedge RESET_N) begin
        if(!RESET_N) begin epoch=epoch+1;BBPD<=0;end
        else begin
            if($isunknown(feedback_delayed)) $fatal(1,"unresolved detector feedback input");
            fork raise_output(epoch,feedback_delayed);join_none
        end
    end
    always @(negedge REFCLK) if(RESET_N) begin
        fork
            lower_output(epoch,0,DN_FALL_NS);
            lower_output(epoch,1,UP_FALL_NS);
        join_none
    end
endmodule
'''


def run(wide_review,bias_review,campaign,output):
    paths=[]
    for folder,name in ((wide_review,'observations.json'),(bias_review,'corners.json')):
        rp=folder/'assessment.json';r=json.loads(rp.read_text());verify(r['input_sha256']);verify(r['artifacts'])
        file=folder/name
        if r['artifacts'].get(str(file))!=sha(file):raise ValueError('unbound detector fit observations')
        paths.extend([rp,file])
    wide=json.loads(paths[1].read_text());bias=json.loads(paths[3].read_text());candidate=json.loads(campaign.read_text())['candidate']
    verify(candidate['source_sha256']);verify(candidate['physical_sha256'])
    if candidate['source_sha256']!=source_pins():raise ValueError('current frozen candidate source required')
    if {r['corner'] for r in wide}!={'tt','ff','ss','sf','fs'} or len(bias)!=5 or {r['corner'] for r in bias}!={'tt','ff','ss','sf','fs'}:raise ValueError('complete five-corner native fit inputs required')
    pins={str(p):sha(p) for p in [*paths,campaign,PROFILE,Path(__file__).resolve(),Path(__file__).with_name('review_prototype_BBPD_loaded_bias_v2.py')]};artifacts={};results=[]
    output.mkdir(parents=True,exist_ok=False)
    for b in bias:
        corner=b['corner'];rows=[r for r in wide if r['corner']==corner]
        if len(rows)!=4 or {r['phase_ps'] for r in rows}!={0,10000,20000,30000}:raise ValueError('complete broad-phase fit grid required')
        p=fit(rows,b);folder=output/corner;folder.mkdir();model=folder/'detector.v';model.write_text(render(p));config=folder/'parameters.json';save(config,dict(corner=corner,**p))
        artifacts.update({str(f):sha(f) for f in (model,config)});results.append(dict(corner=corner,model=str(model),parameters=str(config)))
    verify(pins);detail=output/'models.json';save(detail,results);artifacts[str(detail)]=sha(detail)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts=artifacts,candidate=candidate,
        all_resolved_native_fit_decisions_match=True,fit_corners=5,
        digital_model_replay_complete=False,independent_model_holdouts_complete=False,
        diagnostic=True,synthetic=True,native_interface_qualified=False,validated_for_prototype=False,release_ready=False,
        synthetic_flag_reason='Unqualified fitted behavioral model; cannot enter qualifying closed-loop runs.'))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--wide-review',type=Path,required=True);p.add_argument('--bias-review',type=Path,required=True);p.add_argument('--campaign',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();run(a.wide_review.resolve(),a.bias_review.resolve(),a.campaign.resolve(),a.output.resolve())
