#!/usr/bin/env python3
"""Generate an opt-in fixed-parameter capacitor candidate; leave live sources intact."""
from datetime import datetime,timezone
import difflib
from pathlib import Path
from compile_local_C_operators_v2 import digest,save
root=Path(__file__).resolve().parents[2];base=root/'build/timing400/release_001'
original=base/'wire_preconditioned_Xyce_001/source/src/DeviceModelPKG/OpenModels'
out=base/'compact_constant_cap_source_001';out.mkdir(exist_ok=False)
header=(original/'N_DEV_Capacitor.h').read_text();source=(original/'N_DEV_Capacitor.C').read_text()
new_header=header.replace('#include <N_DEV_fwd.h>','#include <limits>\n#include <vector>\n#include <N_DEV_fwd.h>')
needle='  bool separateInstances_;\n  InstanceVector      linearInstances_;'
assert header.count(needle)==1
new_header=new_header.replace(needle,'''  struct PackedConstantCap
  {
    double capacitance;
    double multiplicity;
    int positive;
    int negative;
  };
  static constexpr int notPacked_ = std::numeric_limits<int>::min();
  std::vector<PackedConstantCap> packedCaps_[3];
  bool packedReady_[3] = {false, false, false};
  double packedLastTime_ = -std::numeric_limits<double>::infinity();
  bool usePackedConstants_();
  std::vector<PackedConstantCap> &packedConstants_(int loadType,
      InstanceVector::const_iterator first, InstanceVector::const_iterator last);
  bool separateInstances_;
  InstanceVector      linearInstances_;''')
new_source=source.replace('#include <Xyce_config.h>','#include <Xyce_config.h>\n#include <cmath>\n#include <cstdlib>\n#include <cstring>\n#include <iostream>\n#include <iterator>')
marker='bool Master::updateState (double * solVec, double * staVec, double * stoVec, int loadType)'
helper='''// Opt-in, fixed-parameter transient optimization. No topology, states,
// matrix stamps or contribution order changes. Dependent/IC/probed paths
// retain the original instance implementation.
bool Master::usePackedConstants_()
{
  const char *mode = std::getenv("OPENPLL_PACKED_CONSTANT_CAPS");
  if (!mode || std::strcmp(mode, "1") != 0) return false;
  const SolverState &state = getSolverState();
  if (state.dcopFlag || !state.transientFlag || state.currTime_ < packedLastTime_)
  {
    packedReady_[0] = packedReady_[1] = packedReady_[2] = false;
  }
  packedLastTime_ = state.currTime_;
  return state.transientFlag && !state.dcopFlag;
}

std::vector<Master::PackedConstantCap> &Master::packedConstants_(int loadType,
    InstanceVector::const_iterator first, InstanceVector::const_iterator last)
{
  const int bucket = loadType == ALL ? 0 : loadType == LINEAR ? 1 : 2;
  std::vector<PackedConstantCap> &packed = packedCaps_[bucket];
  if (!packedReady_[bucket])
  {
    packed.clear(); packed.reserve(std::distance(first, last));
    size_t eligible = 0;
    for (InstanceVector::const_iterator it = first; it != last; ++it)
    {
      Instance &ci = *(*it);
      const bool valid = !ci.ICGiven && !ci.loadLeadCurrent &&
          !ci.solVarDepC && !ci.solVarDepQ && ci.isLinearDevice() &&
          ci.getDependentParams().empty() && ci.getModel().getDependentParams().empty() &&
          ci.tempCoeff1 == 0.0 && ci.tempCoeff2 == 0.0 &&
          ci.getModel().tempCoeff1 == 0.0 && ci.getModel().tempCoeff2 == 0.0 &&
          std::isfinite(ci.C) && std::isfinite(ci.multiplicityFactor);
      packed.push_back({ci.C, ci.multiplicityFactor, valid ? ci.li_Pos : notPacked_, ci.li_Neg});
      eligible += valid;
    }
    packedReady_[bucket] = true;
    std::cout << "OpenPLL_packed_constant_caps bucket=" << bucket
              << " instances=" << packed.size() << " eligible=" << eligible << std::endl;
  }
  return packed;
}

'''
assert new_source.count(marker)==1;new_source=new_source.replace(marker,helper+marker)
loop='  for ( ; it != end; ++it )\n  {\n    Instance & ci = *(*it);'
for function,body in [('bool Master::updateState (double * solVec',
'''    if (packed && (*packed)[packedIndex].positive != notPacked_) continue;
'''),('bool Master::loadDAEVectors (double * solVec',
'''    if (packed && (*packed)[packedIndex].positive != notPacked_)
    {
      const PackedConstantCap &entry = (*packed)[packedIndex];
      const double charge = entry.capacitance * (solVec[entry.positive] - solVec[entry.negative]);
      qVec[entry.positive] += (charge * entry.multiplicity);
      qVec[entry.negative] += (-charge * entry.multiplicity);
      continue;
    }
''')]:
    begin=new_source.index(function);where=new_source.index(loop,begin)
    replacement='''  std::vector<PackedConstantCap> *packed = usePackedConstants_() ? &packedConstants_(loadType, it, end) : nullptr;
  size_t packedIndex = 0;
  for ( ; it != end; ++it, ++packedIndex )
  {
'''+body+'    Instance & ci = *(*it);'
    new_source=new_source[:where]+new_source[where:].replace(loop,replacement,1)
for name,old,new in [('N_DEV_Capacitor.h',header,new_header),('N_DEV_Capacitor.C',source,new_source)]:
    (out/name).write_text(new)
    (out/(name+'.patch')).write_text(''.join(difflib.unified_diff(old.splitlines(True),new.splitlines(True),fromfile='original/'+name,tofile='candidate/'+name)))
save(out/'assessment.json',dict(prepared_utc=datetime.now(timezone.utc).isoformat(),candidate_sources_prepared=True,
    input_sha256={str(p):digest(p) for p in (Path(__file__).resolve(),original/'N_DEV_Capacitor.C',original/'N_DEV_Capacitor.h')},
    candidate_sha256={str(p):digest(p) for p in (out/'N_DEV_Capacitor.C',out/'N_DEV_Capacitor.h')},
    opt_in_environment='OPENPLL_PACKED_CONSTANT_CAPS=1',fixed_parameter_transient_only=True,
    original_instance_order_preserved=True,negative_constant_values_not_clamped=True,
    explicit_IC_dependent_and_probed_instances_use_stock_path=True,
    topology_and_matrix_stamps_unchanged=True,original_state_counts_unchanged=True,
    native_equivalence_tested=False,performance_gain_demonstrated=False,live_sources_changed=False,release_qualified=False,adopted=False))
print('Prepared isolated capacitor source candidate; no native simulation or live mutation')
