// Memory-bounded prescribed-boundary diagnostic, not a closed-loop PLL model.
#include <N_CIR_MixedSignalSimulator.h>
#include <algorithm>
#include <cmath>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <map>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>
using Pair=std::pair<double,double>;
using Pairs=std::vector<Pair>;
struct Boundary {
  std::string name,node,path;
  std::ifstream file;
  Pair initial,right;
  bool read(Pair& point) {
    if(!(file>>point.first>>point.second))return false;
    if(!std::isfinite(point.first)||!std::isfinite(point.second))
      throw std::runtime_error("nonfinite boundary knot");
    return true;
  }
};
int main(int argc,char** argv) {
 try {
  if(argc!=6)throw std::runtime_error("usage: replay DECK BOUNDARIES OUTPUT_NODES STOP_NS CSV");
  const double end=std::stod(argv[4])*1e-9,bootstrap=1e-12;
  if(!std::isfinite(end)||end<=bootstrap||end>260e-9+1e-18)throw std::runtime_error("invalid endpoint");
  std::vector<Boundary> boundaries;
  std::ifstream list(argv[2]);std::string node,path;
  while(list>>node>>path) {
    Boundary b;b.node=node;b.path=path;b.file.open(path);
    if(!b.read(b.initial)||!b.read(b.right)||b.initial.first!=0||b.right.first<=bootstrap)
      throw std::runtime_error("initial boundary interval cannot cover bootstrap");
    boundaries.push_back(std::move(b));
  }
  if(boundaries.empty())throw std::runtime_error("no boundaries");
  std::vector<std::string> outputs;
  std::ifstream output_list(argv[3]);
  while(output_list>>node)outputs.push_back(node);
  if(outputs.empty())throw std::runtime_error("no observation nodes");
  Xyce::Circuit::MixedSignalSimulator sim;
  char solver_option[]="-linsolv",solver_name[]="umfpack_reuse";
  char* args[]{argv[0],argv[1],solver_option,solver_name,nullptr};
  if(sim.initialize(4,args)!=Xyce::Circuit::Simulator::SUCCESS)
    throw std::runtime_error("Xyce initialization failed");
  std::vector<std::string> names;sim.getDACDeviceNames(names);
  if(names.size()!=boundaries.size())throw std::runtime_error("DAC inventory mismatch");
  for(size_t i=0;i<boundaries.size();++i) {
    std::string suffix="!BOUNDARY"+std::to_string(i);unsigned found=0;
    for(auto& name:names)if(name.size()>=suffix.size() && name.compare(name.size()-suffix.size(),suffix.size(),suffix)==0) {
      boundaries[i].name=name;++found;
    }
    if(found!=1)throw std::runtime_error("DAC name mapping not unique: "+suffix);
  }
  std::map<std::string,Pairs> storage;
  std::map<std::string,Pairs*> updates;
  for(auto& b:boundaries)storage[b.name]={{0,b.initial.second}};
  for(auto& item:storage)updates[item.first]=&item.second;
  if(!sim.updateTimeVoltagePairs(updates))throw std::runtime_error("DAC initialization failed");
  std::ofstream csv(argv[5]);csv<<"time_s";
  for(auto& n:outputs)csv<<",v("<<n<<')';
  csv<<'\n'<<std::setprecision(17);
  double now=0;unsigned long steps=0;bool primed=false;
  while(now<end-1e-18) {
    double stop=std::min(end,now+10e-12);
    if(!primed)stop=bootstrap;
    for(auto& b:boundaries)stop=std::min(stop,b.right.first);
    if(stop<=now)throw std::runtime_error("boundary scheduling did not advance");
    double dt=0;std::map<std::string,Pairs> events;
    if(!sim.provisionalStep(stop-now,dt,events))throw std::runtime_error("provisional step failed");
    sim.acceptProvisionalStep();now+=dt;
    if(!std::isfinite(now)||now>stop+1e-17||++steps>1000000)
      throw std::runtime_error("invalid accepted-time progress");
    // API DC readback may describe an initial trial point. Omit that sample.
    if(dt>0) {
      csv<<now;
      for(auto& n:outputs) {
        double value=0;
        if(!sim.getCircuitValue("V("+n+")",value)||!std::isfinite(value))
          throw std::runtime_error("invalid solution readback: "+n);
        csv<<','<<value;
      }
      csv<<'\n';
    }
    if(now>0) {
      for(auto& b:boundaries) {
        if(b.right.first<=now+1e-18 && now<end-1e-18) {
          Pair next;
          if(!b.read(next)||next.first-b.right.first<=1e-15)
            throw std::runtime_error("missing or too-close future boundary knot");
          b.right=next;
        }
        storage[b.name]={{b.right.first,b.right.second}};
      }
      if(!sim.updateTimeVoltagePairs(updates))throw std::runtime_error("streamed DAC update failed");
      primed=true;
    }
    if(steps%100==0) {
      csv.flush();std::cout<<"REPLAY_PROGRESS steps="<<steps<<" accepted_time_s="<<std::setprecision(17)<<now<<'\n'<<std::flush;
    }
  }
  sim.finalize();csv.close();
  std::cout<<"BOUNDARY_REPLAY_COMPLETE steps="<<steps<<" accepted_time_s="<<std::setprecision(17)<<now<<'\n';
  return 0;
 } catch(const std::exception& e) {std::cerr<<e.what()<<'\n';return 1;}
}
