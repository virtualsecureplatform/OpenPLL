"""Certify an exact edge-graph interpretation; do not assert stored-matrix PSD."""
import argparse
import json
from pathlib import Path
import time
from common import save,sha
from resources import lease
from audit_G_offdiagonal_signs import inspect


def run(output):
    output.mkdir(parents=True,exist_ok=False)
    base=Path('build/signoff400').resolve()
    assembly=base/'startup_timing_known_conductance_001/assessment.json'
    signs=base/'startup_timing_known_G_signs_001/assessment.json'
    coverage=base/'startup_timing_G_parameter_coverage_audit_001/assessment.json'
    a,s,c=[json.loads(p.read_text()) for p in (assembly,signs,coverage)]
    matrix=Path(a['zero_R_constrained_known_G_matrix']);families=a['symbolic_material_families']['material_families']
    unit_paths=[Path(f['zero_R_constrained_unit_square_matrix']) for f in families]
    paths=[assembly,signs,coverage,matrix,*unit_paths,Path(__file__).resolve(),Path(__file__).with_name('audit_G_offdiagonal_signs.py').resolve()]
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+3600
    with lease(2,4,deadline):
        pins={str(p):sha(p) for p in paths}
        if s['input_sha256'][str(assembly)]!=pins[str(assembly)] or c['input_sha256'][str(assembly)]!=pins[str(assembly)]:raise ValueError('graph/coverage namespace lineage differs')
        if not s['every_known_G_offdiagonal_sign_checked'] or not s['all_known_G_offdiagonals_nonpositive']:raise ValueError('all known offdiagonal signs required')
        if not a['numerical_matrix_structure']['charge_conservation_within_limit']:raise ValueError('known matrix gauge check required')
        for path in (matrix,*unit_paths):
            if a['artifacts'][str(path)]!=pins[str(path)]:raise ValueError('conductance artifact changed')
        nodes=c['constrained_voltage_nodes'];unit_results=[]
        for path,family in zip(unit_paths,families):
            result=inspect(path,nodes,deadline)
            if result['positive_offdiagonal_records']:raise ValueError('symbolic family requires a general Gram certificate')
            unit_results.append(dict(matrix=str(path),results=result))
        # Definition: retain each serialized offdiagonal exactly and define diagonals
        # as exact real sums of incident positive edge weights, rather than using
        # independently rounded serialized diagonal coefficients.
        certificate=dict(operator_definition='G_graph = sum_{i<j} (-G_stored[i,j]) (e_i-e_j)(e_i-e_j)^T',
            symbolic_definition='G_family_graph uses the same construction on each dimensionless unit matrix',
            energy_identity='v^T G_graph v = sum_{i<j} (-G_stored[i,j]) (v_i-v_j)^2 >= 0',
            positive_family_combination='G_graph + sum_f lambda_f G_family_graph_f is PSD for all lambda_f >= 0',
            coefficient_interpretation='Stored finite x87 offdiagonal coefficients interpreted as exact dyadic real numbers',
            implicit_graph_diagonals='exact incident edge-weight sums; no independent diagonal rounding in the mathematical operator',
            known_graph_edges=s['results']['negative_offdiagonal_records'],
            symbolic_unit_graph_edges=sum(r['results']['negative_offdiagonal_records'] for r in unit_results),
            constrained_voltage_nodes=nodes,
            scope='Exact nominal edge graph defined above, including arbitrary nonnegative symbolic multipliers; no material/PVT qualification')
        save(output/'certificate.json',certificate)
        if any(sha(p)!=pins[str(p)] for p in paths):raise ValueError('graph certificate input changed')
        save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(output/'certificate.json'):sha(output/'certificate.json')},
             exact_defined_nominal_edge_graph_and_nonnegative_symbolic_family_PSD_certified=True,
             unit_family_offdiagonal_audits=unit_results,
             known_stored_matrix_scaled_gauge_residual=a['numerical_matrix_structure']['maximum_scaled_charge_residual'],
             stored_matrix_and_exact_graph_differ_only_in_diagonal_entries=True,
             stored_matrix_exact_PSD_proved=False,
             rounded_diagonal_perturbation_rigorously_enclosed=False,
             exact_graph_implemented_in_native_solver=False,
             material_values_selected=False,full_numeric_spatial_G_matrix_assembled=False,
             physical_RC_qualified=False,runtime_model_eligible=False,release_qualified=False))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path);run(p.parse_args().output.resolve())
