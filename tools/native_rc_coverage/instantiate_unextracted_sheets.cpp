// Compact spatial basis instances with cached, translation-free shape requests.
#include "../charge_compiler/json.hpp"
#include <algorithm>
#include <array>
#include <filesystem>
#include <future>
#include <iostream>
#include <unordered_map>
#include <time.h>
using I=long long;namespace fs=std::filesystem;
static double now(){timespec t{};require(clock_gettime(CLOCK_BOOTTIME,&t)==0,"clock");return t.tv_sec+t.tv_nsec*1e-9;}
static Json shifted(const Json& ring,I x,I y){Json result=Json::array();for(auto&p:ring.arr())result.push(Json::Array{p.at(0).integer()-x,p.at(1).integer()-y});return result;}
static Json instantiate(const Json& job,const Json& cfg,const std::map<std::string,Json>& exceptions){
 auto type=job.at("native_type").str();I scale=job.at("coordinate_scale").integer(),sheet=job.at("nominal_sheet_milliohm").integer();
 require(scale>0&&sheet>0,"positive coordinate scale and nominal sheet");double deadline=cfg.at("deadline_uptime").num();
 fs::path out=fs::path(cfg.at("output").str())/type;require(fs::create_directory(out),"fresh material output");
 std::ifstream geometry(job.at("geometry").str(),std::ios::binary),native(job.at("native").str(),std::ios::binary);
 std::ofstream instances(out/"instances.jsonl"),requests(out/"shape_requests.jsonl");require(bool(geometry)&&bool(native)&&bool(instances)&&bool(requests),"basis streams");
 std::unordered_map<std::string,I> shapes;Json used_ids=Json::array();I count=0,arithmetic=0,nonrectangles=0;std::string a,b;
 while(true){I go=I(geometry.tellg()),no=I(native.tellg());bool ga=bool(std::getline(geometry,a)),nb=bool(std::getline(native,b));require(ga==nb,"native/GDS row coverage differs");if(!ga)break;
  if(++count%10000==0)require(now()<deadline,"sheet instance deadline");auto g=Json::parse(a),n=Json::parse(b);auto name=n.at("original_conductor").str();
  require(g.at("original_conductor").str()==name&&n.at("native_type").str()==type&&g.at("field_ids").dump()==n.at("field_ids").dump(),"native/GDS field identity differs");
  require(g.at("candidate_polygons").integer()==1&&g.at("native_area_equal").boolean()&&g.at("native_perimeter_equal").boolean()&&g.at("spatial_material_equal").boolean()&&!g.at("duplicate_component_box").boolean(),"unverified conductor polygon");
  require(n.at("physical_field_ids").arr().size()==1&&n.at("native_classes").arr().size()==1,"single physical field and native material class required");
  I field=n.at("physical_field_ids").at(0).integer();require(field>0&&field<cfg.at("arithmetic_field_begin").integer(),"physical field role");
  require(n.at("native_classes").at(0).at("native_sheet_class_value").integer()==sheet,"native sheet class differs from documented nominal rule");
  const auto& native_class=n.at("native_classes").at(0);
  require(g.at("area_gds_dbu_squared").integer()==native_class.at("area_internal_squared").integer()*scale*scale&&g.at("perimeter_gds_dbu").integer()==native_class.at("perimeter_internal").integer()*scale,"native/GDS area or perimeter differs");
  for(size_t i=0;i<2;++i)require(g.at("point_gds_dbu").at(i).integer()==n.at("point_internal").at(i).integer()*scale,"native/GDS point differs");
  require(n.at("spatial_field_keys").arr().size()==1&&n.at("spatial_field_keys").at(0).at(0).str()==job.at("plane").str()&&n.at("spatial_field_keys").at(0).at(1).str()==job.at("material").str(),"native spatial material differs");
  for(auto&id:n.at("arithmetic_bookkeeping_field_ids").arr())require(id.integer()>=cfg.at("arithmetic_field_begin").integer()&&id.integer()<cfg.at("arithmetic_field_end").integer(),"arithmetic field role differs");
  auto& box=g.at("bbox_gds_dbu");I x0=box.at(0).integer(),y0=box.at(1).integer(),w=box.at(2).integer()-x0,h=box.at(3).integer()-y0;require(w>0&&h>0,"positive physical box");
  Json hull,holes=Json::array();bool rectangle=g.at("rectangle").boolean();
  if(rectangle){require(g.at("exact_rectangle_geometry").boolean(),"unverified rectangle");hull=Json::Array{Json::Array{0,0},Json::Array{w,0},Json::Array{w,h},Json::Array{0,h}};}
  else{++nonrectangles;auto it=exceptions.find(name);require(it!=exceptions.end(),"complete exception contour required");const auto&e=it->second;
   require(e.at("native_type").str()==type&&e.at("bbox_gds_dbu").dump()==box.dump()&&e.at("field_ids").dump()==g.at("field_ids").dump(),"exception contour identity differs");
   hull=shifted(e.at("hull_gds_dbu"),x0,y0);for(auto&ring:e.at("holes_gds_dbu").arr())holes.push(shifted(ring,x0,y0));}
  Json shape=Json::object();shape["hull_gds_dbu"]=hull;shape["holes_gds_dbu"]=holes;shape["coordinate_scale"]=scale;
  auto[it,added]=shapes.emplace(shape.dump(),I(shapes.size()));auto local=type+":"+std::to_string(it->second);
  if(added){shape["local_template_id"]=local;shape["area_gds_dbu_squared"]=g.at("area_gds_dbu_squared");shape["perimeter_gds_dbu"]=g.at("perimeter_gds_dbu");requests<<shape.dump()<<'\n';}
  Json item=Json::object();item["physical_field_id"]=field;item["original_conductor"]=name;item["local_template_id"]=local;item["origin_gds_dbu"]=Json::Array{x0,y0};
  item["coordinate_scale"]=scale;item["native_type"]=type;item["nominal_sheet_milliohm"]=sheet;item["voltage_namespace"]="_fmesh_"+std::to_string(field);
  item["arithmetic_bookkeeping_field_ids"]=n.at("arithmetic_bookkeeping_field_ids");arithmetic+=I(n.at("arithmetic_bookkeeping_field_ids").arr().size());
  item["source_geometry_byte_offset"]=go;item["source_native_byte_offset"]=no;item["source_row"]=count;item["supported_refinements"]=Json::Array{1,2,4};
  item["physical_RC_qualified"]=false;instances<<item.dump()<<'\n';used_ids.push(field);require(bool(instances)&&bool(requests),"basis instance write");
 }
 require(geometry.eof()&&!geometry.bad()&&native.eof()&&!native.bad(),"complete basis input reads");instances.close();requests.close();require(bool(instances)&&bool(requests),"basis output close");
 Json result=Json::object();result["native_type"]=type;result["instances"]=count;result["local_shape_templates"]=I(shapes.size());result["nonrectangles"]=nonrectangles;result["arithmetic_ids_preserved_without_states"]=arithmetic;result["physical_field_ids"]=used_ids;
 return result;
}
int main(int argc,char**argv){try{
 require(argc==2,"usage: instantiate_unextracted_sheets CONFIG");auto cfg=Json::read(argv[1]);fs::path out=cfg.at("output").str();require(fs::create_directory(out),"fresh sheet instance output");
 std::map<std::string,Json> exceptions;std::ifstream contours(cfg.at("contours").str());require(bool(contours),"contours open");std::string line;
 while(std::getline(contours,line)){auto r=Json::parse(line);require(exceptions.emplace(r.at("original_conductor").str(),r).second,"duplicate contour");}
 std::vector<std::future<Json>> jobs;require(cfg.at("jobs").arr().size()<=8,"bounded material jobs");
 for(auto&job:cfg.at("jobs").arr())jobs.push_back(std::async(std::launch::async,instantiate,job,std::cref(cfg),std::cref(exceptions)));
 Json materials=Json::object();std::vector<I> fields;I count=0,shapes=0,nonrectangles=0,arithmetic=0;
 for(auto&job:jobs){auto r=job.get();auto type=r.at("native_type").str();count+=r.at("instances").integer();shapes+=r.at("local_shape_templates").integer();nonrectangles+=r.at("nonrectangles").integer();arithmetic+=r.at("arithmetic_ids_preserved_without_states").integer();
  for(auto&id:r.at("physical_field_ids").arr())fields.push_back(id.integer());std::get<Json::Object>(r.value).erase("physical_field_ids");materials[type]=r;}
 std::sort(fields.begin(),fields.end());require(std::adjacent_find(fields.begin(),fields.end())==fields.end(),"duplicate physical field basis");require(nonrectangles==I(exceptions.size()),"unused or missing exception contours");
 Json summary=Json::object();summary["basis_instances"]=count;summary["local_shape_templates"]=shapes;summary["nonrectangles"]=nonrectangles;summary["arithmetic_ids_preserved_without_states"]=arithmetic;summary["per_native_type"]=materials;
 summary["all_physical_field_ids_unique"]=true;summary["all_native_sheet_values_match_documented_nominal_rules"]=true;
 for(auto flag:{"physical_RC_qualified","full_C_energy_matrix_assembled","runtime_model_eligible","release_qualified"})summary[flag]=false;
 std::ofstream output(out/"summary.json");output<<summary.dump()<<'\n';require(bool(output),"basis summary write");std::cout<<summary.dump()<<'\n';
 }catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
