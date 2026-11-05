// Materialize every selected native R mesh once, rather than per C operator.
#include "../charge_compiler/json.hpp"
#include <array>
#include <algorithm>
#include <filesystem>
#include <iostream>
#include <set>
#include <omp.h>
#include <fcntl.h>
#include <unistd.h>
#include <time.h>
using I=long long;using Point=std::array<I,2>;using Box=std::array<I,4>;
static double now(){timespec t{};require(clock_gettime(CLOCK_BOOTTIME,&t)==0,"clock");return t.tv_sec+t.tv_nsec*1e-9;}
static Json row_at(int fd,I offset){require(offset>=0,"row offset");std::string raw;char buffer[8192];
 while(true){auto n=pread(fd,buffer,sizeof(buffer),offset+I(raw.size()));require(n>0&&raw.size()<16*1024*1024,"bounded complete geometry row");
  auto end=std::find(buffer,buffer+n,'\n');raw.append(buffer,end);if(end!=buffer+n)break;
 }return Json::parse(raw);}
static Box get_box(const Json& row,const char* key){Box b{};for(int d=0;d<4;d++)b[d]=row.at(key).at(d).integer();require(b[0]<b[2]&&b[1]<b[3],"positive tile box");return b;}
struct Mesh{
 std::vector<Point> points;std::vector<std::string> names;std::vector<std::array<I,3>> triangles;std::map<Point,I> ids;
 I node(Point p,const std::string& name){require(!name.empty(),"voltage identity");auto[it,added]=ids.emplace(p,I(points.size()));
  if(added){points.push_back(p);names.push_back(name);}else require(names[it->second]==name,"coincident native voltage identity mismatch");return it->second;}
 void cell(const std::array<Point,4>& p,const std::array<std::string,4>& n){std::array<I,4> v{};for(int k=0;k<4;k++)v[k]=node(p[k],n[k]);triangles.push_back({v[0],v[1],v[2]});triangles.push_back({v[0],v[2],v[3]});}
 Json json()const{Json r=Json::object(),p=Json::array(),n=Json::array(),t=Json::array();
  for(auto v:points)p.push(Json::Array{v[0],v[1]});for(auto& s:names)n.push(s);for(auto v:triangles)t.push(Json::Array{v[0],v[1],v[2]});
  r["points"]=p;r["point_nodes"]=n;r["triangles"]=t;return r;}
};
static Mesh axis_mesh(Box b,int axis,const std::vector<std::pair<I,std::string>>& knots){
 require((axis==0||axis==1)&&knots.size()>=2&&knots.front().first==b[axis]&&knots.back().first==b[axis+2],"full native axis coverage");Mesh m;
 for(size_t k=1;k<knots.size();k++){auto[a,na]=knots[k-1];auto[c,nc]=knots[k];require(a<c,"increasing native axis");
  if(axis==0)m.cell({Point{a,b[1]},Point{c,b[1]},Point{c,b[3]},Point{a,b[3]}},{na,nc,nc,na});
  else m.cell({Point{b[0],a},Point{b[2],a},Point{b[2],c},Point{b[0],c}},{na,na,nc,nc});
 }return m;
}
static Json compile(const Json& tile,int axes,int chains){
 auto b=get_box(tile,"box_internal");require(tile.at("split").integer()==0,"unsplit native R tile");Mesh m;Json aux=Json::object();
 auto group=tile.at("native_group_id").str();I serial=tile.at("tile_serial").integer();
 if(tile.at("catalog_state").str()=="anchored_sheet_candidate"){
  std::map<Point,std::string> anchors;std::set<std::string> native;
  for(auto& a:tile.at("native_anchor_points").arr()){Point p{a.at(0).at(0).integer(),a.at(0).at(1).integer()};auto name=a.at(1).str();
   require(b[0]<=p[0]&&p[0]<=b[2]&&b[1]<=p[1]&&p[1]<=b[3],"native anchor inside tile");auto[it,added]=anchors.emplace(p,name);require(added||it->second==name,"anchor identity");native.insert(name);}
  require(native.size()==1,"one native anchored voltage");std::vector<I> xs{b[0],b[2]},ys{b[1],b[3]};for(auto&[p,n]:anchors){xs.push_back(p[0]);ys.push_back(p[1]);}
  auto unique=[](std::vector<I>& v){std::sort(v.begin(),v.end());v.erase(std::unique(v.begin(),v.end()),v.end());};unique(xs);unique(ys);
  auto prefix=tile.at("latent_node_namespace").str()+":r1:";
  for(size_t y=1;y<ys.size();y++)for(size_t x=1;x<xs.size();x++){
   std::array<Point,4> pp{Point{xs[x-1],ys[y-1]},Point{xs[x],ys[y-1]},Point{xs[x],ys[y]},Point{xs[x-1],ys[y]}};std::array<std::string,4> nn;
   for(int k=0;k<4;k++){auto found=anchors.find(pp[k]);if(found!=anchors.end())nn[k]=found->second;else{auto existing=m.ids.find(pp[k]);nn[k]=prefix+std::to_string(existing==m.ids.end()?I(m.points.size()):existing->second);}
    m.node(pp[k],nn[k]);}
   m.cell(pp,nn);
  }
  aux["kind"]="anchored_sheet";aux["nominal_sheet_milliohms_per_square"]=tile.at("nominal_sheet_milliohms_per_square");
 }else{
  auto axis=row_at(axes,tile.at("axis_registry_byte_offset").integer());require(axis.at("native_group_id").str()==group&&get_box(axis,"tile_box_internal")==b,"tile/axis identity");
  std::vector<std::pair<I,std::string>> knots;int flow=int(axis.at("flow_axis").integer());
  if(tile.at("axis_preparation_state").str()=="deferred_zero_R_constraint"){
   auto chain=row_at(chains,axis.at("source_chain_byte_offset").integer());require(chain.at("native_group_id").str()==group&&get_box(chain,"tile_box_internal")==b,"zero-R chain identity");
   auto& segments=chain.at("segments").arr();require(!segments.empty(),"native zero-R segments");Json constraints=Json::array();auto prefix="_zero_R_"+group+"_"+std::to_string(serial);
   for(size_t i=0;i<segments.size();i++){auto& s=segments[i];I lo=s.at(0).integer(),hi=s.at(1).integer();auto a=s.at(2).str(),c=s.at(3).str();
    require(lo<hi,"zero-R increasing interval");if(knots.empty())knots.push_back({lo,a});else require(knots.back()==std::pair{lo,a},"zero-R chain continuity");knots.push_back({hi,c});
    if(s.at(4).str()=="0"){Json constraint=Json::object();constraint["current_unknown"]=prefix+":current:"+std::to_string(i);constraint["positive"]=a;constraint["negative"]=c;constraint["native_branch"]=s.at(5);constraint["voltage_rhs"]=0;constraints.push(constraint);}
   }require(!constraints.arr().empty(),"zero-R constraint required");
   if(knots.front().first>b[flow])knots.insert(knots.begin(),{b[flow],prefix+":lo"});if(knots.back().first<b[flow+2])knots.push_back({b[flow+2],prefix+":hi"});
   aux["kind"]="zero_R_symbolic_ends";aux["constraints"]=constraints;aux["raw_material"]=chain.at("raw_material");
  }else{
   require(axis.at("geometric_axis_prepared").boolean(),"prepared native axis");for(auto& k:axis.at("candidate_voltage_knots").arr())knots.push_back({k.at(0).integer(),k.at(1).str()});
   aux["kind"]="nominal_axis_ends";aux["stubs"]=axis.at("end_stub_resistors");
  }m=axis_mesh(b,flow,knots);
 }
 auto result=m.json();result["box"]=tile.at("box_internal");result["tile_serial"]=serial;result["native_group_id"]=group;result["auxiliary"]=aux;
 result["catalog_state"]=tile.at("catalog_state");result["raw_material"]=tile.at("raw_material");result["physical_RC_qualified"]=false;return result;
}
int main(int argc,char**argv){try{
 require(argc==2,"usage: compile_R_meshes CONFIG");auto cfg=Json::read(argv[1]);I threads=cfg.at("threads").integer();require(threads>=1&&threads<=32,"thread bound");double deadline=cfg.at("deadline_uptime").num();
 auto path=cfg.at("catalog").str();I size=I(std::filesystem::file_size(path));int axes=open(cfg.at("axes").str().c_str(),O_RDONLY),chains=open(cfg.at("chains").str().c_str(),O_RDONLY);require(axes>=0&&chains>=0,"geometry sources open");
 std::filesystem::path out=cfg.at("output").str();require(std::filesystem::create_directory(out),"fresh runtime geometry directory");std::vector<std::exception_ptr> errors(threads);std::vector<I> counts(threads),points(threads),triangles(threads);
 #pragma omp parallel for num_threads(threads)
 for(I part=0;part<threads;part++){try{
  std::ifstream input(path,std::ios::binary);I start=size*part/threads,end=size*(part+1)/threads;std::string raw;input.seekg(start?start-1:0);
  if(start){char c;require(bool(input.get(c)),"range seek");if(c!='\n')std::getline(input,raw);}std::ofstream output(out/("part_"+std::to_string(part)+".jsonl"));require(bool(output),"runtime mesh output");
  while(true){I offset=I(input.tellg());if(offset<0||offset>=end)break;if(!std::getline(input,raw))break;require(now()<deadline,"runtime compilation deadline");auto tile=Json::parse(raw);auto mesh=compile(tile,axes,chains);mesh["source_catalog_byte_offset"]=offset;
   counts[part]++;points[part]+=I(mesh.at("points").arr().size());triangles[part]+=I(mesh.at("triangles").arr().size());output<<mesh.dump()<<'\n';require(bool(output),"runtime mesh write");
  }require(!input.bad(),"catalog read");output.close();require(bool(output),"runtime mesh close");
 }catch(...){errors[part]=std::current_exception();}}
 close(axes);close(chains);for(auto& e:errors)if(e)std::rethrow_exception(e);I total=0,np=0,nt=0;for(I p=0;p<threads;p++){total+=counts[p];np+=points[p];nt+=triangles[p];}
 require(total==cfg.at("expected_tiles").integer(),"complete selected tile coverage");Json result=Json::object();result["tiles"]=total;result["points"]=np;result["triangles"]=nt;result["threads"]=threads;result["R_refinement"]=1;result["physical_RC_qualified"]=false;result["release_qualified"]=false;
 std::cout<<result.dump()<<'\n';return 0;
 }catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 2;}}
