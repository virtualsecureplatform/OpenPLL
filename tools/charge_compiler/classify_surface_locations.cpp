// Verify the complete event stream's located prefix and unlocated G suffix.
#define main retained_charge_compiler_main
#include "main_stream_ledger.cpp"
#undef main
struct LocationPart{I events=0,first=0,last=0,unlocated=0,first_unlocated=0,last_unlocated=0,last_located=0;};
static LocationPart locations(const fs::path& path,I lo,I hi,I size,double deadline){
 LocationPart r;std::array<char,1048576> buffer{};std::ifstream in;in.rdbuf()->pubsetbuf(buffer.data(),buffer.size());in.open(path,std::ios::binary);require(bool(in),"surface open");in.seekg(lo);
 std::string line;I position=lo,rows=0;
 while(position<hi&&std::getline(in,line)){
  position=std::min(size,position+I(line.size())+1);if(++rows%100000==0)check_deadline(deadline);
  if(line.rfind("SURFACE ",0)!=0)continue;auto f=split(line);require(f.size()==9,"surface row width");I id=integer(f[1]);
  require(!r.events||id==r.last+1,"surface event ID gap");if(!r.events)r.first=id;r.last=id;++r.events;
  require(f[2]=="G"||f[2]=="P","surface event kind");
  if(f[2]=="G")require(f[6]=="-1"&&f[7]=="-1"&&f[8]=="-1","unexpected located G reference");
  else require(integer(f[6])>=0&&integer(f[8])>=0,"unlocated pair target");
  if(integer(f[3])<0){
   require(f[2]=="G"&&f[3]=="-1"&&f[4]=="-1"&&f[5]=="-1","unsupported unlocated surface context");
   if(!r.unlocated)r.first_unlocated=id;r.last_unlocated=id;++r.unlocated;
  }else{require(integer(f[5])>=0,"unlocated effective type");r.last_located=id;}
 }
 require(position==hi&&!in.bad(),"complete surface range");return r;
}
int main(int argc,char**argv){try{
 require(argc==5,"usage: classify_surface_locations SURFACES OUTPUT DEADLINE THREADS");
 fs::path path=argv[1];double deadline=number(argv[3]);I threads=integer(argv[4]);require(threads>=1&&threads<=32,"thread bound");
 I size=I(fs::file_size(path));std::vector<I> cuts{0};for(I i=1;i<threads;++i){I c=align_line(path,size*i/threads);if(c>cuts.back()&&c<size)cuts.push_back(c);}cuts.push_back(size);
 std::vector<std::future<LocationPart>> jobs;for(size_t i=0;i+1<cuts.size();++i)jobs.push_back(std::async(std::launch::async,locations,path,cuts[i],cuts[i+1],size,deadline));
 LocationPart total;
 for(auto& job:jobs){auto p=job.get();if(!p.events)continue;require(p.first==total.last+1,"cross-range event ID gap");
  if(!total.events)total.first=p.first;total.last=p.last;total.events+=p.events;
  if(p.unlocated){if(!total.unlocated)total.first_unlocated=p.first_unlocated;total.last_unlocated=p.last_unlocated;total.unlocated+=p.unlocated;}
  total.last_located=std::max(total.last_located,p.last_located);
 }
 require(total.events>0&&total.unlocated>0,"expected located and unlocated native events");
 require(total.last_unlocated==total.last&&total.first_unlocated+total.unlocated-1==total.last_unlocated&&total.last_located<total.first_unlocated,"unlocated events are not a strict terminal suffix");
 Json r=Json::object();r["events"]=total.events;r["unlocated_G_events"]=total.unlocated;r["first_unlocated_event"]=total.first_unlocated;r["last_unlocated_event"]=total.last_unlocated;r["last_located_event"]=total.last_located;
 r["all_unlocated_sources_are_terminal_G_events"]=true;r["unlocated_pair_targets"]=0;
 std::ofstream out(argv[2]);out<<r.dump()<<'\n';require(bool(out),"location report write");std::cout<<r.dump()<<'\n';
 }catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
