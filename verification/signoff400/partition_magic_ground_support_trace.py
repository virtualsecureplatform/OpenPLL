"""Partition completed observer records without hiding native event adjacency."""
from contextlib import ExitStack
from collections import Counter
import json

NUMERIC={'ground_update','ground_output','node_name','overlap','sidewall','sideoverlap_halo','sideoverlap_legacy'}
OVERLAP={'overlap_support_begin','overlap_shield_leaf','overlap_support_end'}
FRINGE={'fringe_rule_begin','fringe_rule_end','fringe_shield_leaf'}
HALO={'ground_halo_begin','ground_halo_end','ground_halo_subtract'}
ADJACENT={'ground_support':'ground_support','ground_overlap_subtraction':'ground_overlap','ground_halo_subtract':'ground_halo','ground_halo_tail':'ground_tail'}
STREAMS=['numeric','overlap','fringe','ground_support','ground_overlap','ground_halo','ground_tail']


def partition(source,output):
    pending=None;events=Counter();counts=Counter();total=0
    with ExitStack() as stack:
        targets={name:stack.enter_context((output/(name+'.jsonl')).open('x')) for name in STREAMS}
        stream=stack.enter_context(source.open())
        for line in stream:
            r=json.loads(line);kind=r['kind'];total+=1;events[kind]+=1;selected=set()
            if pending is not None:
                if kind!='ground_update':raise ValueError('native support record not immediately followed by ground update')
                selected.add(pending);pending=None
            if kind in NUMERIC:selected.add('numeric')
            elif kind in OVERLAP:
                selected.add('overlap')
                if kind=='overlap_support_end':selected.add('ground_overlap')
            elif kind in FRINGE:
                selected.add('fringe')
                if kind=='fringe_rule_end':selected.add('ground_halo')
            elif kind in HALO:selected.add('ground_halo')
            elif kind in ADJACENT:selected.add(ADJACENT[kind])
            else:raise ValueError('unknown native observer event: '+kind)
            if kind in ADJACENT:pending=ADJACENT[kind];selected.add(pending)
            for name in selected:targets[name].write(line);counts[name]+=1
    if pending is not None:raise ValueError('truncated native support/update pair')
    if not total:raise ValueError('nonempty completed native trace required')
    return dict(source_events=total,event_kinds=dict(events),stream_events=dict(counts),native_support_update_adjacency_preserved=True,unknown_events_ignored=False)
