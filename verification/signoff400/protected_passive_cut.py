"""Retain protected output resistor networks without prescribing their voltages."""
from collections import defaultdict,deque
from plan_selected_detector_passive_cut import RAILS


def passive_cut(terms,passives,selected,prescribed=(),protected=()):
    if not selected or not selected<=terms.keys():raise ValueError('unknown selected primitive')
    prescribed=set(prescribed);protected=set(protected)
    if protected&(prescribed|RAILS):raise ValueError('protected outputs overlap prescribed inputs or supplies')
    seeds=({n for name in selected for n in terms[name]}-RAILS-prescribed)|protected
    external={n for name in terms.keys()-selected for n in terms[name]}-seeds-RAILS
    adjacency=defaultdict(list)
    for index,(_,a,b) in enumerate(passives):adjacency[a].append(index);adjacency[b].append(index)
    private=set(seeds);boundary=set(prescribed);cards=set();queue=deque(sorted(seeds))
    while queue:
        node=queue.popleft()
        for index in adjacency[node]:
            cards.add(index);_,a,b=passives[index]
            for other in [a,b]:
                if other in RAILS or other in private:continue
                if other in external or other in prescribed:boundary.add(other)
                else:private.add(other);queue.append(other)
    omitted={name:sorted(set(nodes)&private) for name,nodes in terms.items() if name not in selected and set(nodes)&private}
    return private,boundary,cards,omitted
