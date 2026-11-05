// Diagnostic of stock DAC time-zero and accepted-time replay semantics.
#include <N_CIR_MixedSignalSimulator.h>
#include <algorithm>
#include <cmath>
#include <iostream>
#include <fstream>
#include <iomanip>
#include <map>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>
using Pairs = std::vector<std::pair<double,double>>;
int main(int argc, char** argv) {
  try {
    if(argc!=4) throw std::runtime_error("usage: probe DECK naive|stream ramp|plateau");
    std::string mode=argv[2], shape=argv[3];
    if((mode!="naive" && mode!="stream") || (shape!="ramp" && shape!="plateau"))
      throw std::runtime_error("invalid mode or waveform");
    Pairs knots{{0,0}};
    if(shape=="plateau") knots.emplace_back(100e-12,0);
    knots.insert(knots.end(),{{.5e-9,1},{1e-9,0},{1.5e-9,1},{2e-9,0}});
    Xyce::Circuit::MixedSignalSimulator sim;
    char* args[]{argv[0],argv[1],nullptr};
    if(sim.initialize(2,args)!=Xyce::Circuit::Simulator::SUCCESS)
      throw std::runtime_error("initialization failed");
    std::vector<std::string> names;sim.getDACDeviceNames(names);
    if(names.size()!=1)throw std::runtime_error("one DAC required");
    auto update=[&](Pairs data){
      std::map<std::string,Pairs*> pointers{{names[0],&data}};
      if(!sim.updateTimeVoltagePairs(pointers)) throw std::runtime_error("DAC update failed");
    };
    if(mode=="naive") update(knots); else update({{0,0}});
    std::ofstream wave("wave.csv");
    wave<<"TIME,V(REFERENCE),V(STREAMED)\n"<<std::setprecision(17);
    double now=0;unsigned steps=0;bool primed=mode=="naive";
    while(now<2e-9-1e-18) {
      double stop=std::min(2e-9,now+10e-12);
      if(!primed)stop=1e-12;
      for(auto p:knots)if(p.first>now+1e-18)stop=std::min(stop,p.first);
      double dt=0;std::map<std::string,Pairs> events;
      if(!sim.provisionalStep(stop-now,dt,events))throw std::runtime_error("step failed");
      sim.acceptProvisionalStep();now+=dt;
      double reference=0,streamed=0;
      if(!sim.getCircuitValue("V(reference)",reference) || !sim.getCircuitValue("V(streamed)",streamed))
        throw std::runtime_error("solution readback failed");
      // DC API readback can expose the initial trial point rather than t=0.
      // Record only positive accepted transient intervals.
      if(dt>0)wave<<now<<','<<reference<<','<<streamed<<'\n';
      if(!std::isfinite(now) || now>stop+1e-17 || ++steps>100000)
        throw std::runtime_error("invalid accepted-time progress");
      if(mode=="stream" && now>0) {
        // Keep only the current segment's right endpoint in the update.
        // DAC keeps the accepted voltage and prunes consumed history.
        auto next=std::find_if(knots.begin(),knots.end(),[&](auto p){return p.first>now+1e-18;});
        if(next!=knots.end()) update({*next});
        primed=true;
      }
    }
    sim.finalize();
    std::cout<<"PROBE_COMPLETE steps="<<steps<<" time="<<now<<"\n";
    return 0;
  } catch(const std::exception& e){std::cerr<<e.what()<<"\n";return 1;}
}
