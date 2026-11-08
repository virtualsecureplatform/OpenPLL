"""Cross-check observed ground geometry records against every pinned native mutation site."""
from collections import Counter
import json


def support_counts(trace):
    counts=Counter()
    with trace.open() as stream:
        for line in stream:
            r=json.loads(line)
            if r['kind']=='ground_support':counts[r['site']]+=1
    return dict(counts)


def coverage(inventory,ground,geometry,overlap,halo,tail):
    sites={r['file']+':'+str(r['line']):r for r in inventory}
    if len(sites)!=len(inventory) or len(sites)!=18:raise ValueError('unique pinned eighteen-site ground inventory required')
    observed=ground['mutation_sites_observed']
    if set(observed)-set(sites):raise ValueError('observed ground mutation outside pinned inventory')
    additions={k:r for k,r in sites.items() if r['file']=='ExtBasic.c' and not r['reset']}
    if len(additions)!=6 or set(geometry)-set(additions):raise ValueError('six native area/perimeter sites required')
    differences={k:dict(native=observed.get(k,0),geometry=geometry.get(k,0)) for k in additions if observed.get(k,0)!=geometry.get(k,0)}
    checks=[('ExtCouple.c:522',overlap['ground_overlap_subtractions']),('ExtCouple.c:1521',halo['ground_halo_subtractions']),('ExtCouple.c:1254',tail['halo_tail_events'])]
    for site,count in checks:
        if observed.get(site,0)!=count:differences[site]=dict(native=observed.get(site,0),geometry=count)
    if differences:raise ValueError('native/geometry event coverage mismatch: '+str(differences))
    legacy=observed.get('ExtCouple.c:1703',0)
    return dict(area_perimeter_site_counts={k:observed.get(k,0) for k in additions},shielding_subtraction_site_counts={k:observed.get(k,0) for k,_ in checks},all_nine_supported_site_counts_match=True,legacy_ground_subtractions=legacy,legacy_ground_path_observed=bool(legacy),substrate_relocation_updates={k:observed.get(k,0) for k in ['ExtCouple.c:234','ExtCouple.c:239']},reset_site_counts={k:observed.get(k,0) for k,r in sites.items() if r['reset']},substrate_relocation_spatially_qualified=False,legacy_ground_support_qualified=False,pointwise_placement_qualified=False,distributed_wire_R_qualified=False,release_ready=False)
