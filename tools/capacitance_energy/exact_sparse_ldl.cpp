// Exact signed capacitor Laplacian congruence using GMP rational arithmetic.
#include <gmpxx.h>
#include <chrono>
#include <fstream>
#include <iostream>
#include <map>
#include <queue>
#include <set>
#include <stdexcept>
#include <vector>
int main(int argc,char**argv){try{
 if(argc!=4)throw std::runtime_error("edges report seconds required");
 std::ifstream in(argv[1]);size_t n,m;in>>n>>m;
 std::vector<mpq_class>d(n);std::vector<std::map<int,mpq_class>>a(n);std::vector<bool>live(n,true);
 for(size_t k=0;k<m;k++){int x,y;std::string value;in>>x>>y>>value;if(!in||x<0||x>=int(n)||y>=int(n)||y < -1||x==y)throw std::runtime_error("invalid edge");mpq_class c(value);c.canonicalize();d[x]+=c;if(y>=0){d[y]+=c;a[x][y]-=c;a[y][x]-=c;}}
 using Entry=std::pair<size_t,int>;std::priority_queue<Entry,std::vector<Entry>,std::greater<Entry>>q;
 for(size_t i=0;i<n;i++){for(auto it=a[i].begin();it!=a[i].end();)if(it->second==0)it=a[i].erase(it);else ++it;q.push({a[i].size(),int(i)});}
 auto start=std::chrono::steady_clock::now();double seconds=std::stod(argv[3]);size_t done=0;std::string state="positive_semidefinite";int failed=-1;
 while(done<n){
  if(std::chrono::duration<double>(std::chrono::steady_clock::now()-start).count()>seconds){state="time_bound_inconclusive";break;}
  Entry e;do{if(q.empty())throw std::runtime_error("lost pivot");e=q.top();q.pop();}while(!live[e.second]||e.first!=a[e.second].size());int p=e.second;
  if(d[p]<0||(d[p]==0&&!a[p].empty())){state="indefinite";failed=p;break;}
  auto row=a[p];if(d[p]!=0){
   for(auto const&[i,c]:row)d[i]-=c*c/d[p];
   for(auto i=row.begin();i!=row.end();++i)for(auto j=std::next(i);j!=row.end();++j){int x=i->first,y=j->first;mpq_class v=a[x][y]-i->second*j->second/d[p];if(v==0){a[x].erase(y);a[y].erase(x);}else{a[x][y]=v;a[y][x]=v;}}
  }
  live[p]=false;a[p].clear();for(auto const&[i,c]:row){a[i].erase(p);q.push({a[i].size(),i});}done++;
 }
 std::ofstream out(argv[2]);out<<"{\"state\":\""<<state<<"\",\"eliminated\":"<<done<<",\"remaining\":"<<(n-done)<<",\"failed_pivot\":"<<failed<<",\"passivity_certified\":"<<(state=="positive_semidefinite"?"true":"false")<<",\"indefiniteness_proved\":"<<(state=="indefinite"?"true":"false")<<"}\n";
 return 0;
 }catch(std::exception const&e){std::cerr<<e.what()<<"\n";return 1;}}
