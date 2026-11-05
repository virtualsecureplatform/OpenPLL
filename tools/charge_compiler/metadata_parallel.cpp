// Preserve the retained metadata grammar and output while parsing disjoint
// complete-line ranges in parallel. Existing production source stays frozen.
#define main retained_charge_compiler_main
#include "main_stream_ledger.cpp"
#undef main
#include <future>

struct MetadataPart {
 Json types=Json::object(),planes=Json::object();
 std::map<std::pair<I,I>,I> residues;
 bool begin=false,end=false;
 I lines=0;
};
static MetadataPart parse_part(const fs::path& path,I lo,I hi,I size,double deadline){
 MetadataPart part;std::ifstream in(path,std::ios::binary);require(bool(in),"parallel metadata open");in.seekg(lo);
 std::string line;I position=lo;bool began=lo!=0,ended=false;
 while(position<hi&&std::getline(in,line)){
  I line_end=std::min(size,position+I(line.size())+1);position=line_end;
  if(++part.lines%100000==0)check_deadline(deadline);
  auto f=split(line);require(!f.empty()&&!ended,"bad surface stream");
  if(f[0]=="BEGIN"){require(!began&&lo==0,"duplicate surface begin");began=true;part.begin=true;}
  else if(f[0]=="TYPE"||f[0]=="PLANE"){
   require(began&&f.size()>=3,"invalid type/plane metadata");size_t offset=size_t(f[2].data()-line.data());
   auto text=Json::parse(std::string_view(line).substr(offset));require(std::holds_alternative<std::string>(text.value),"type/plane name");
   auto& table=f[0]=="TYPE"?part.types:part.planes;std::string key(f[1]);require(!table.obj().count(key),"duplicate type/plane");table[key]=text;
  }else if(f[0]=="SURFACE"){
   require(began&&f.size()==9,"invalid surface metadata row");
   for(int i:{3,6})if(f[i]!="-1"){
    auto key=std::pair{integer(f[i]),integer(f[i+1])};I value=integer(f[i+2]);
    auto[it,added]=part.residues.emplace(key,value);require(added||it->second==value,"inconsistent native residue");
   }
  }else{
   require(f[0]=="END"&&f.size()==2&&began&&line_end==size,"unknown or nonterminal surface record");ended=true;part.end=true;
  }
 }
 require(position==hi&&!in.bad(),"complete metadata byte range");check_deadline(deadline);return part;
}
int main(int argc,char**argv){try{
 require(argc==6,"usage: metadata_parallel TRACE OUTPUT DEADLINE THREADS MODE");
 fs::path trace=argv[1],output=argv[2],path=trace/"surfaces.log";double deadline=number(argv[3]);I threads=integer(argv[4]);
 require(threads>=1&&threads<=32,"metadata thread bound");
 if(std::string(argv[5])=="serial"){metadata(trace,output,deadline);return 0;}
 require(std::string(argv[5])=="parallel","metadata mode");
 I size=I(fs::file_size(path));require(size>0,"nonempty surface stream");std::vector<I> boundaries{0};
 for(I i=1;i<threads;++i){I p=align_line(path,size*i/threads);if(p>boundaries.back()&&p<size)boundaries.push_back(p);}boundaries.push_back(size);
 std::vector<std::future<MetadataPart>> tasks;
 for(size_t i=0;i+1<boundaries.size();++i)tasks.push_back(std::async(std::launch::async,parse_part,path,boundaries[i],boundaries[i+1],size,deadline));
 Json types=Json::object(),planes=Json::object();std::map<std::pair<I,I>,I> residues;I begins=0,ends=0;
 for(auto& task:tasks){auto part=task.get();begins+=part.begin;ends+=part.end;
  for(auto pair:{std::pair{&types,&part.types},std::pair{&planes,&part.planes}})
   for(auto&[key,value]:pair.second->obj()){require(!pair.first->obj().count(key),"duplicate global type/plane");(*pair.first)[key]=value;}
  for(auto&[key,value]:part.residues){auto[it,added]=residues.emplace(key,value);require(added||it->second==value,"inconsistent native residue across ranges");}
 }
 require(begins==1&&ends==1,"incomplete surface metadata");check_deadline(deadline);
 Json result=Json::object(),r=Json::array();for(auto[key,value]:residues)r.push(Json::Array{key.first,key.second,value});
 result["types"]=types;result["planes"]=planes;result["residues"]=r;save(output,result);return 0;
 }catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
