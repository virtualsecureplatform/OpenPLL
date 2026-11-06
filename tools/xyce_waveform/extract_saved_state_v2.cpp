// Extract one actual native RAW knot, without interpolating circuit states.
#include <cmath>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>
static std::string escaped(const std::string& s) {
  std::string out="\"";
  for (unsigned char c:s) {
    if(c=='"'||c=='\\') {out+='\\';out+=c;}
    else if(c<32) throw std::runtime_error("control character in variable name");
    else out+=c;
  }
  return out+'"';
}
int main(int argc,char** argv) {try {
  if(argc!=4) throw std::runtime_error("usage: extract_saved_state RAW TARGET_SECONDS OUTPUT");
  const double target=std::stod(argv[2]);
  if(!std::isfinite(target)||target<=0) throw std::runtime_error("positive finite target required");
  std::ifstream in(argv[1]);if(!in) throw std::runtime_error("cannot open RAW");
  std::string line;size_t variables=0,points=0;bool header=false;
  while(std::getline(in,line)) {
    if(line.rfind("No. Variables:",0)==0) variables=std::stoull(line.substr(14));
    if(line.rfind("No. Points:",0)==0) points=std::stoull(line.substr(11));
    if(line=="Variables:") {header=true;break;}
  }
  if(!header||variables<2||points<2) throw std::runtime_error("complete RAW header required");
  std::vector<std::string> names;
  while(std::getline(in,line)&&line!="Values:") {
    std::istringstream row(line);size_t index;std::string name,type,extra;
    if(!(row>>index>>name>>type)||row>>extra||index!=names.size()) throw std::runtime_error("invalid variable ordering");
    names.push_back(name);
  }
  if(line!="Values:"||names.size()!=variables||(names[0]!="time"&&names[0]!="TIME")) throw std::runtime_error("incomplete variable inventory");
  size_t expected=0;double previous=-1;
  while(std::getline(in,line)) {
    if(line.find_first_not_of(" \t\r")==std::string::npos)continue;
    std::istringstream row(line);size_t index;double time;std::string extra;
    if(!(row>>index>>time)||row>>extra||index!=expected++||!std::isfinite(time)||time<=previous)
      throw std::runtime_error("invalid sample index or time");
    previous=time;
    const bool selected=time>=target;
    std::vector<double> values;if(selected)values.push_back(time);
    for(size_t i=1;i<variables;i++) {
      if(!std::getline(in,line))throw std::runtime_error("incomplete sample");
      if(selected) {
        std::istringstream v(line);double value;
        if(!(v>>value)||v>>extra||!std::isfinite(value))throw std::runtime_error("invalid saved voltage");
        values.push_back(value);
      }
    }
    if(selected) {
      if(index>=points||time-target>11e-12)throw std::runtime_error("saved knot too far from requested time");
      std::ofstream out(argv[3]);if(!out)throw std::runtime_error("cannot create state output");
      out<<std::setprecision(17)<<"{\"time_s\":"<<time<<",\"sample_index\":"<<index<<",\"variable_names\":[";
      for(size_t i=0;i<names.size();i++){if(i)out<<',';out<<escaped(names[i]);}
      out<<"],\"values\":[";for(size_t i=0;i<values.size();i++){if(i)out<<',';out<<values[i];}
      out<<"]}\n";if(!out)throw std::runtime_error("state output failed");
      std::cout<<"captured sample="<<index<<" time_s="<<std::setprecision(17)<<time<<" variables="<<variables<<'\n';return 0;
    }
  }
  throw std::runtime_error("target time not reached");
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
