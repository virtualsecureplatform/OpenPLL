#define main registered_projection_control_main
#include "main_registered_rational.cpp"
#undef main
#include "runtime_geometry.hpp"
int main(int argc,char** argv){try{
 require(argc==2,"usage: project_runtime_controls CONFIG");auto cfg=Json::read(argv[1]);double start=uptime();RuntimeGeometry geometry(cfg.at("geometry"));
 auto rows=Json::read(cfg.at("cases").str());std::vector<Json> output(rows.arr().size());std::vector<std::exception_ptr> errors(rows.arr().size());I threads=cfg.at("threads").integer();require(threads>=1&&threads<=32,"thread bound");
 #pragma omp parallel for num_threads(threads) schedule(dynamic,1)
 for(I i=0;i<I(rows.arr().size());i++){try{require(uptime()<cfg.at("deadline_uptime").num(),"projection deadline");auto& row=rows.at(i);auto& op=row.at("operator");std::string kind=op.at(0).str();std::array<I,4> support;for(int d=0;d<4;d++)support[d]=op.at(4).at(d).integer();P shift{Q(long(support[0])),Q(long(support[1]))};LocalRuntimeNodes nodes;
  auto source=geometry.resolve(op.at(1).integer(),support,shift,nodes);auto target_support=support;if(kind!="A")for(int d=0;d<4;d++)target_support[d]=op.at(5).at(d).integer();auto target=geometry.resolve(op.at(2).integer(),target_support,shift,nodes);auto a=box(op.at(4),shift);
  Matrix exact;FloatMatrix floating;if(kind=="A")exact=area(source,target,a,Q(op.at(5).num()));else if(kind=="L")exact=line(source,target,edge(a),edge(box(op.at(5),shift)),Q(op.at(6).num()));else{require(kind=="F","operator kind");floating=fringe(source,target,edge(a),box(op.at(5),shift),int(op.at(6).integer()),Q(op.at(7).num()),Q(op.at(8).num()),.25L);}
  Json result=Json::object(),names=Json::array(),global=Json::array(),matrix=Json::array(),ex=Json::array();for(auto id:nodes.global){names.push(geometry.name(id));global.push(I(id));}
  for(auto&[ij,value]:exact)if(value!=0){matrix.push(Json::Array{ij.first,ij.second,value.get_d()});ex.push(Json::Array{ij.first,ij.second,value.get_num().get_str(),value.get_den().get_str()});}
  for(auto&[ij,value]:floating)if(value!=0)matrix.push(Json::Array{ij.first,ij.second,double(value)});
  result["id"]=row.at("id");result["nodes"]=names;result["global_nodes"]=global;result["matrix"]=matrix;if(kind!="F")result["exact_matrix"]=ex;output[i]=result;
 }catch(...){errors[i]=std::current_exception();}}
 for(auto& e:errors)if(e)std::rethrow_exception(e);std::ofstream out(cfg.at("output").str());require(bool(out),"projection output");for(auto& r:output)out<<r.dump()<<'\n';out.close();require(bool(out),"projection output close");
 Json result=Json::object();result["projected_cases"]=I(output.size());result["global_voltage_nodes"]=I(geometry.node_count());result["threads"]=threads;result["elapsed_s"]=uptime()-start;result["physical_RC_qualified"]=false;result["release_qualified"]=false;std::cout<<result.dump()<<'\n';return 0;
 }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 2;}}
