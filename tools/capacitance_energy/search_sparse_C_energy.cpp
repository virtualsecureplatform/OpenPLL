// Candidate search only. Every reported voltage requires independent exact energy verification.
#include <gmpxx.h>
#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <vector>
struct Edge{int a,b;long double c,k;};
int main(int argc,char**argv){try{
 if(argc!=5)throw std::runtime_error("edges vector report seconds required");
 std::ifstream in(argv[1]);int n,m;in>>n>>m;if(!in||n<1||m<1)throw std::runtime_error("invalid dimensions");
 std::vector<mpq_class> exact_diagonal(n);std::vector<Edge>edges;std::vector<long double>d(n,0),q(n),next(n),best(n),scale(n),off(n,0);edges.reserve(m);
 for(int i=0;i<m;i++){int a,b;std::string value;in>>a>>b>>value;if(!in||a<0||a>=n||b < -1||b>=n||a==b)throw std::runtime_error("invalid edge");mpq_class exact(value);exact.canonicalize();long double c=exact.get_d()*1e15L;edges.push_back({a,b,c,0});exact_diagonal[a]+=exact;if(b>=0)exact_diagonal[b]+=exact;}
 for(int i=0;i<n;i++){d[i]=exact_diagonal[i].get_d()*1e15L;if(d[i]<=0)throw std::runtime_error("nonpositive diagonal requires exact principal audit");scale[i]=std::sqrt(d[i]);}
 for(auto&e:edges)if(e.b>=0){e.k=e.c/(scale[e.a]*scale[e.b]);off[e.a]+=std::abs(e.k);off[e.b]+=std::abs(e.k);}
 long double bound=1+*std::max_element(off.begin(),off.end());long double best_energy=std::numeric_limits<long double>::infinity();int steps=0;
 best_energy=1;best[0]=1/scale[0];
 auto start=std::chrono::steady_clock::now();double seconds=std::stod(argv[4]);bool expired=false,negative=false;
 for(int seed=0;seed<2&&!expired&&!negative;seed++){
  uint64_t state=0x9e3779b97f4a7c15ULL+seed;
  for(auto&v:q){state^=state<<13;state^=state>>7;state^=state<<17;v=(static_cast<long double>(state%2000001)-1000000)/1000000;}
  for(int iteration=0;iteration<2048;iteration++){
   if(std::chrono::duration<double>(std::chrono::steady_clock::now()-start).count()>seconds){expired=true;break;}
   for(int i=0;i<n;i++)next[i]=(bound-1)*q[i];
   for(auto const&e:edges)if(e.b>=0){next[e.a]+=e.k*q[e.b];next[e.b]+=e.k*q[e.a];}
   long double norm=0;for(auto v:next)norm+=v*v;norm=std::sqrt(norm);if(norm==0)break;
   for(int i=0;i<n;i++)q[i]=next[i]/norm;steps++;
   if(iteration%16==0||iteration==2047){
    long double energy=0;for(auto const&e:edges){long double delta=q[e.a]/scale[e.a]-(e.b<0?0:q[e.b]/scale[e.b]);energy+=e.c*delta*delta;}
    if(energy<best_energy){best_energy=energy;for(int i=0;i<n;i++)best[i]=q[i]/scale[i];}
    if(energy < -1e-10L){negative=true;break;}
   }
  }
 }
 if(!std::isfinite(best_energy))throw std::runtime_error("no finite candidate");
 long double maximum=0;for(auto v:best)maximum=std::max(maximum,std::abs(v));if(maximum==0)throw std::runtime_error("zero candidate");
 std::ofstream vector(argv[2]);vector<<n<<"\n";for(auto v:best)vector<<std::llround(v/maximum*1000000000.L)<<"\n";
 std::ofstream report(argv[3]);report<<std::setprecision(20)<<"{\"iterations\":"<<steps<<",\"candidate_float_energy\":"<<best_energy<<",\"time_bound_reached\":"<<(expired?"true":"false")<<",\"search_is_not_passivity_certificate\":true,\"voltage_denominator\":1000000000}\n";
 return 0;
 }catch(std::exception const&e){std::cerr<<e.what()<<"\n";return 1;}}
