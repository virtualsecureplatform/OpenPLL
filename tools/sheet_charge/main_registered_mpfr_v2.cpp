#include "registered_fringe_interval.hpp"
int main(int argc,char**argv){try{
 require(argc==2,"usage CONFIG");auto cfg=Json::read(argv[1]);auto bits=cfg.at("precision_bits").integer();
 require(bits>=128&&bits<=1024,"bounded MPFR precision");fringe_interval::precision=bits;
 auto cases=Json::read(cfg.at("cases").str());std::ofstream output(cfg.at("output").str());require(bool(output),"MPFR matrix output");
 for(const auto&row:cases.arr()){
  require(uptime()<cfg.at("deadline_uptime").num(),"MPFR case deadline");const auto&op=row.at("operator");
  P shift{exact_coordinate(op.at(4).at(0)),exact_coordinate(op.at(4).at(1))};Nodes nodes;
  auto source=basis(row.at("source_basis"),nodes,shift),target=basis(row.at("target_basis"),nodes,shift);
  auto rect=box(op.at(4),shift);auto kind=op.at(0).str();IntervalMatrix matrix;
  if(kind=="F")matrix=fringe_certified(source,target,edge(rect),box(op.at(5),shift),op.at(6).integer(),Q(op.at(7).num()),Q(op.at(8).num()));
  else {
   require(kind=="A"||kind=="L","supported MPFR operator");
   auto exact=kind=="A"?area(source,target,rect,Q(op.at(5).num())):line(source,target,edge(rect),edge(box(op.at(5),shift)),Q(op.at(6).num()));
   for(const auto&[ij,v]:exact)if(ij.first<=ij.second)matrix[ij]=fringe_interval::Interval(v);
  }
  Json result=Json::object(),entries=Json::array(),names=Json::array();for(const auto&n:nodes.names)names.push(n);
  for(const auto&[ij,v]:matrix)entries.push(Json::Array{ij.first,ij.second,fringe_interval::json(v)});
  result["id"]=row.at("id");result["nodes"]=names;result["upper_matrix_intervals"]=entries;
  result["physical_RC_qualified"]=false;result["release_qualified"]=false;output<<result.dump()<<'\n';
 }
 output.close();require(bool(output),"MPFR matrix close");return 0;
 }catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
