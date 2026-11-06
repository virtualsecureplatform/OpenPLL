#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <string>
#include <vector>
struct Stats {
 double lo=INFINITY,hi=-INFINITY,last=0,variation=0,maxdelta=0,area=0,last_t=0;
 long knots=0;
 void add(double t,double v){
  if(knots){double d=std::abs(v-last);variation+=d;maxdelta=std::max(maxdelta,d);area+=(t-last_t)*(v+last)/2;}
  lo=std::min(lo,v);hi=std::max(hi,v);last=v;last_t=t;++knots;
 }
};
int main(int argc,char**argv){
 if(argc!=6)return 2;
 double start=std::strtod(argv[4],nullptr),stop=std::strtod(argv[5],nullptr);
 if(!std::isfinite(start)||!std::isfinite(stop)||start<0||stop<=start)return 3;
 std::ifstream raw(argv[1]),mapping(argv[2]);std::vector<int> indices;int index;
 while(mapping>>index)indices.push_back(index);
 if(!raw||indices.empty())return 4;
 std::string line;int columns=0;long declared=0;
 while(std::getline(raw,line)){
  if(line.rfind("No. Variables:",0)==0)columns=std::stoi(line.substr(14));
  if(line.rfind("No. Points:",0)==0)declared=std::stol(line.substr(11));
  if(line=="Values:")break;
 }
 if(columns<2||declared<2||!raw)return 5;
 std::vector<int> slot(columns,-1);
 for(size_t i=0;i<indices.size();++i){if(indices[i]<=0||indices[i]>=columns||slot[indices[i]]!=-1)return 6;slot[indices[i]]=i;}
 std::vector<double> previous_values(indices.size()),values(indices.size());std::vector<Stats> stats(indices.size());
 double previous=-1;long samples=0;
 while(std::getline(raw,line)){
  if(line.empty())continue;
  char* end;long n=std::strtol(line.c_str(),&end,10);double t=std::strtod(end,&end);
  if(n!=samples||!std::isfinite(t)||t<=previous)return 7;
  for(int i=1;i<columns;++i){
   if(!std::getline(raw,line))return 8;
   char* last;double v=std::strtod(line.c_str(),&last);
   if(last==line.c_str()||!std::isfinite(v))return 9;
   if(slot[i]>=0)values[slot[i]]=v;
  }
  for(size_t i=0;i<stats.size();++i){
   if(!stats[i].knots&&previous<=start&&t>=start&&samples>0){
    double v=previous_values[i]+(values[i]-previous_values[i])*(start-previous)/(t-previous);stats[i].add(start,v);
   }
   if(stats[i].knots&&t>start&&t<=stop)stats[i].add(t,values[i]);
   if(stats[i].knots&&previous<stop&&t>stop){
    double v=previous_values[i]+(values[i]-previous_values[i])*(stop-previous)/(t-previous);stats[i].add(stop,v);
   }
  }
  previous=t;previous_values=values;++samples;
  if(samples%5000==0)std::cout<<"samples="<<samples<<std::endl;
 }
 if(samples!=declared||previous<stop)return 10;
 for(auto& s:stats)if(s.knots<2||std::abs(s.last_t-stop)>1e-18)return 11;
 std::ofstream out(argv[3]);if(!out)return 12;
 out<<"index,minimum_V,maximum_V,last_V,total_variation_V,max_adjacent_delta_V,window_knots,time_mean_V\n"<<std::setprecision(17);
 for(size_t i=0;i<stats.size();++i){auto&s=stats[i];out<<indices[i]<<','<<s.lo<<','<<s.hi<<','<<s.last<<','<<s.variation<<','<<s.maxdelta<<','<<s.knots<<','<<s.area/(stop-start)<<'\n';}
 out.flush();if(!out)return 13;
 std::cout<<"complete samples="<<samples<<" boundaries="<<indices.size()<<" source_end_s="<<std::setprecision(17)<<previous<<std::endl;return 0;
}
