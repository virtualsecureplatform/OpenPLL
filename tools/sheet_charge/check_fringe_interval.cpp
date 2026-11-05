#include "fringe_interval.hpp"
#include <iostream>
int main(int argc,char**argv){try{
 require(argc==2,"usage CONFIG");auto cfg=Json::read(argv[1]);auto bits=cfg.at("precision_bits").integer();
 require(bits>=128&&bits<=1024,"bounded precision");fringe_interval::precision=bits;
 Json results=Json::array();for(const auto& row:cfg.at("cases").arr()){
  std::array<mpq_class,4> polynomial;require(row.at("polynomial").arr().size()==4,"cubic polynomial width");
  for(int k=0;k<4;k++){polynomial[k]=mpq_class(row.at("polynomial").at(k).str());polynomial[k].canonicalize();}
  auto result=fringe_interval::integrate(polynomial,mpq_class(row.at("lower").str()),
      mpq_class(row.at("upper").str()),mpq_class(row.at("multiplier").str()));
  results.push(fringe_interval::json(result));
 }std::ofstream out(cfg.at("report").str());out<<results.dump()<<'\n';out.close();require(bool(out),"interval report close");return 0;
 }catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
