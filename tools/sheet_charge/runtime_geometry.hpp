// Include after the controlled GMP projection primitives. Immutable after load.
#pragma once
#include <filesystem>
#include <memory>
#include <cstdint>
#include <limits>
struct LocalRuntimeNodes{
 std::unordered_map<uint64_t,int> ids;std::vector<uint64_t> global;
 int get(uint64_t n){auto[it,added]=ids.emplace(n,int(global.size()));if(added)global.push_back(n);return it->second;}
};
class RuntimeGeometry{
 using B=std::array<I,4>;
 struct RP{I x,y;uint64_t node=0;};
 struct Tile{B box;I serial=0;std::vector<RP> points;std::vector<std::string> names;std::vector<std::array<uint32_t,3>> triangles;};
 struct Template{std::vector<P> points;std::vector<std::array<uint32_t,3>> triangles;};
 struct Field{I ox=0,oy=0;uint64_t base=0;int root=-1,shape=-1,scale=0;};
 struct Tree{B box;int left=-1,right=-1;size_t start=0,count=0;};
 std::vector<Tile> tiles;std::vector<Template> shapes;std::vector<Field> fields;
 std::vector<Tree> trees;std::vector<int> references;std::vector<std::string> R_names;
 std::vector<std::pair<uint64_t,I>> floating_bases;
 uint64_t total_nodes=1;
 static I read_le(const std::string& bytes,size_t offset,int width){require(offset+width<=bytes.size(),"index integer bounds");uint64_t n=0;for(int k=0;k<width;k++)n|=uint64_t(static_cast<unsigned char>(bytes[offset+k]))<<(8*k);return I(n);}
 static std::string bytes(const std::string& path){std::ifstream f(path,std::ios::binary);require(bool(f),"runtime input open");return std::string((std::istreambuf_iterator<char>(f)),{});}
 static B bounds(const Json& row,const char* key){B b;for(int d=0;d<4;d++)b[d]=row.at(key).at(d).integer();return b;}
 static bool overlap(B a,B b){if(b[0]==b[2])return a[0]<=b[0]&&b[0]<=a[2]&&std::max(a[1],b[1])<std::min(a[3],b[3]);
  if(b[1]==b[3])return a[1]<=b[1]&&b[1]<=a[3]&&std::max(a[0],b[0])<std::min(a[2],b[2]);
  return std::max(a[0],b[0])<std::min(a[2],b[2])&&std::max(a[1],b[1])<std::min(a[3],b[3]);}
 int tree(size_t begin,size_t end){require(begin<end,"nonempty R field geometry");B b=tiles[references[begin]].box;
  for(size_t i=begin+1;i<end;i++){auto c=tiles[references[i]].box;for(int d=0;d<2;d++){b[d]=std::min(b[d],c[d]);b[d+2]=std::max(b[d+2],c[d+2]);}}
  int id=int(trees.size());trees.push_back(Tree{b,-1,-1,begin,end-begin});if(end-begin>8){int axis=b[2]-b[0]>=b[3]-b[1]?0:1;size_t mid=(begin+end)/2;
   std::nth_element(references.begin()+begin,references.begin()+mid,references.begin()+end,[&](int a,int c){auto x=tiles[a].box,y=tiles[c].box;return std::pair{x[axis]+x[axis+2],tiles[a].serial}<std::pair{y[axis]+y[axis+2],tiles[c].serial};});
   int left=tree(begin,mid),right=tree(mid,end);trees[id].left=left;trees[id].right=right;trees[id].count=0;
  }return id;
 }
 void query(int root,B support,std::vector<int>& found)const{auto& node=trees.at(root);if(!overlap(node.box,support))return;
  if(node.count){for(size_t i=node.start;i<node.start+node.count;i++)if(overlap(tiles[references[i]].box,support))found.push_back(references[i]);}
  else{query(node.left,support,found);query(node.right,support,found);}}
 static void triangle(Basis& b,const std::array<P,3>& pp,const std::array<uint64_t,3>& names,LocalRuntimeNodes& nodes){
  Q det=cross(pp[0],pp[1],pp[2]);require(det>0,"runtime positive triangle");Vec values;
  for(int i=0;i<3;i++){auto a=pp[(i+1)%3],c=pp[(i+2)%3];Aff v{(a.x*c.y-c.x*a.y)/det,(a.y-c.y)/det,(c.x-a.x)/det};int n=nodes.get(names[i]);for(int d=0;d<3;d++)values[n][d]+=v[d];}
  b.patches.push_back({Poly{pp[0],pp[1],pp[2]},values});
 }
public:
 explicit RuntimeGeometry(const Json& cfg){
  I count=cfg.at("global_fields").integer();require(count>0&&count<100000000,"runtime field bound");fields.resize(count);
  auto& parts=cfg.at("R_parts").arr();require(parts.size()>=1&&parts.size()<=32,"R runtime partition count");
  std::vector<std::vector<Tile>> loaded(parts.size());std::vector<std::exception_ptr> errors(parts.size());
  #pragma omp parallel for num_threads(8)
  for(I part=0;part<I(parts.size());part++){try{std::ifstream input(parts[part].str());require(bool(input),"runtime R mesh input");std::string line;
   while(std::getline(input,line)){require(uptime()<cfg.at("deadline_uptime").num(),"runtime load deadline");auto row=Json::parse(line);Tile tile;tile.box=bounds(row,"box");tile.serial=row.at("tile_serial").integer();
    for(auto& p:row.at("points").arr())tile.points.push_back({p.at(0).integer(),p.at(1).integer(),0});for(auto& n:row.at("point_nodes").arr())tile.names.push_back(n.str());
    require(tile.names.size()==tile.points.size(),"runtime R point identities");for(auto& t:row.at("triangles").arr()){std::array<uint32_t,3> tri{};for(int d=0;d<3;d++){I k=t.at(d).integer();require(k>=0&&k<I(tile.points.size()),"runtime R triangle index");tri[d]=uint32_t(k);}tile.triangles.push_back(tri);}loaded[part].push_back(std::move(tile));
   }require(input.eof()&&!input.bad(),"runtime R mesh read");
  }catch(...){errors[part]=std::current_exception();}}
  for(auto& e:errors)if(e)std::rethrow_exception(e);for(auto& part:loaded)for(auto& tile:part)tiles.push_back(std::move(tile));loaded.clear();
  require(I(tiles.size())==cfg.at("expected_R_tiles").integer(),"runtime selected R tile count");
  std::unordered_map<std::string,uint64_t> ids;I max_serial=0;
  for(auto& tile:tiles){max_serial=std::max(max_serial,tile.serial);for(size_t i=0;i<tile.points.size();i++){auto[it,added]=ids.emplace(tile.names[i],total_nodes);if(added){R_names.push_back(tile.names[i]);total_nodes++;}tile.points[i].node=it->second;}tile.names.clear();tile.names.shrink_to_fit();}ids.clear();ids.rehash(0);
  std::vector<int> by_serial(size_t(max_serial)+1,-1);for(size_t i=0;i<tiles.size();i++){require(tiles[i].serial>0&&by_serial[tiles[i].serial]<0,"unique runtime tile serial");by_serial[tiles[i].serial]=int(i);}
  auto index=bytes(cfg.at("R_index").str());require(index.substr(0,8)=="RBSIDX01"&&read_le(index,8,8)==count&&index.size()==16+16*size_t(count),"runtime R field index");
  std::vector<I> bundle_field(size_t(cfg.at("expected_R_fields").integer()),-1);
  for(I f=1;f<count;f++){size_t p=16+16*size_t(f);if(read_le(index,p,8)==-1)continue;I bundle=read_le(index,p+12,4);require(bundle>=0&&bundle<I(bundle_field.size())&&bundle_field[bundle]<0,"unique runtime R bundle");bundle_field[bundle]=f;}
  std::ifstream bundles(cfg.at("R_bundles").str());require(bool(bundles),"runtime R bundles");std::string raw;I seen=0;
  while(std::getline(bundles,raw)){auto row=Json::parse(raw);I number=row.at("bundle_id").integer();require(number==seen&&number<I(bundle_field.size())&&bundle_field[number]>0,"runtime bundle order/field");I f=bundle_field[number];size_t start=references.size();
   for(auto& ref:row.at("tile_references").arr()){I serial=ref.at(3).integer();require(serial>0&&serial<I(by_serial.size())&&by_serial[serial]>=0,"bundle selected tile");references.push_back(by_serial[serial]);}
   fields[f].root=tree(start,references.size());seen++;
  }require(bundles.eof()&&!bundles.bad()&&seen==I(bundle_field.size())&&references.size()==tiles.size(),"complete runtime R bundles");
  auto aliases=Json::read(cfg.at("template_aliases").str());std::map<std::string,int> alias;for(auto& r:aliases.arr())require(alias.emplace(r.at("local_template_id").str(),int(r.at("global_template_id").integer())).second,"unique shape alias");
  std::ifstream templates(cfg.at("templates").str());require(bool(templates),"runtime floating templates");std::set<int> shape_ids;
  while(std::getline(templates,raw)){auto row=Json::parse(raw);if(row.at("refinement").integer()!=1)continue;int id=int(row.at("global_template_id").integer());require(id>=0&&id<100000&&shape_ids.insert(id).second,"floating template ID");if(size_t(id)>=shapes.size())shapes.resize(id+1);auto& shape=shapes[id];
   for(auto& p:row.at("points_native_internal").arr())shape.points.push_back({exact_coordinate(p.at(0)),exact_coordinate(p.at(1))});
   for(auto& t:row.at("triangles").arr()){std::array<uint32_t,3> tri{};for(int d=0;d<3;d++){I k=t.at(d).integer();require(k>=0&&k<I(shape.points.size()),"floating triangle index");tri[d]=uint32_t(k);}shape.triangles.push_back(tri);}
  }require(templates.eof()&&!templates.bad(),"floating template read");
  auto flags=std::make_unique<std::atomic<uint8_t>[]>(count);for(I f=0;f<count;f++)flags[f]=fields[f].root>=0?1:0;
  auto& floating=cfg.at("floating_parts").arr();require(floating.size()==7,"floating partition count");errors.assign(7,{});std::vector<I> floating_counts(7);
  #pragma omp parallel for num_threads(7)
  for(I part=0;part<7;part++){try{std::ifstream input(floating[part].str());require(bool(input),"floating instances input");std::string line;
   while(std::getline(input,line)){require(uptime()<cfg.at("deadline_uptime").num(),"floating runtime deadline");auto row=Json::parse(line);I id=row.at("physical_field_id").integer();require(id>0&&id<count&&flags[id].exchange(2)==0,"unique/disjoint floating field");auto it=alias.find(row.at("local_template_id").str());require(it!=alias.end()&&shape_ids.count(it->second),"floating field shape alias");auto& field=fields[id];field.shape=it->second;field.ox=row.at("origin_gds_dbu").at(0).integer();field.oy=row.at("origin_gds_dbu").at(1).integer();field.scale=int(row.at("coordinate_scale").integer());require(field.scale>0,"positive floating coordinate scale");floating_counts[part]++;
   }require(input.eof()&&!input.bad(),"floating runtime instance read");
  }catch(...){errors[part]=std::current_exception();}}
  for(auto& e:errors)if(e)std::rethrow_exception(e);I nf=0;for(auto n:floating_counts)nf+=n;require(nf==cfg.at("expected_floating_fields").integer(),"floating field count");
  uint64_t floating_nodes=0;for(I f=1;f<count;f++)if(fields[f].shape>=0){fields[f].base=total_nodes;floating_bases.push_back({total_nodes,f});auto n=shapes[fields[f].shape].points.size();total_nodes+=n;floating_nodes+=n;}
  require(floating_nodes==uint64_t(cfg.at("expected_floating_nodes").integer()),"floating DOF count");
 }
 uint64_t node_count()const{return total_nodes;}
 std::string name(uint64_t node)const{require(node<total_nodes,"runtime node ID");if(node==0)return "@SUBSTRATE_REFERENCE";if(node<=R_names.size())return R_names[node-1];auto found=std::upper_bound(floating_bases.begin(),floating_bases.end(),std::pair{node,std::numeric_limits<I>::max()});require(found!=floating_bases.begin(),"floating node lookup");auto[base,field]=*--found;return "_fmesh_"+std::to_string(field)+":r1:n"+std::to_string(node-base);}
 Basis resolve(I field,B support,P shift,LocalRuntimeNodes& nodes)const{require(field>=0&&field<I(fields.size()),"runtime physical field bounds");Basis result;if(field==0){result.constant=nodes.get(0);return result;}auto& f=fields[field];
  if(f.root>=0){std::vector<int> selected;query(f.root,support,selected);require(!selected.empty(),"runtime operator misses R geometry");for(int id:selected){auto& tile=tiles[id];for(auto tri:tile.triangles){std::array<P,3> pp;std::array<uint64_t,3> nn;for(int k=0;k<3;k++){auto p=tile.points[tri[k]];pp[k]={Q(long(p.x))-shift.x,Q(long(p.y))-shift.y};nn[k]=p.node;}triangle(result,pp,nn,nodes);}}}
  else{require(f.shape>=0,"runtime field has no physical basis (arithmetic or missing)");auto& shape=shapes[f.shape];P origin{Q(long(f.ox))/f.scale-shift.x,Q(long(f.oy))/f.scale-shift.y};for(auto tri:shape.triangles){std::array<P,3> pp;std::array<uint64_t,3> nn;for(int k=0;k<3;k++){auto p=shape.points[tri[k]];pp[k]={p.x+origin.x,p.y+origin.y};nn[k]=f.base+tri[k];}triangle(result,pp,nn,nodes);}}
  return result;
 }
};
