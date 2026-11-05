#include <fstream>
#include <iostream>
#include <vector>
#include <string>
#include <sstream>
#include <cmath>
#include <cstdlib>
#include <cstdio>
#include <filesystem>
int main(int argc,char**argv){
 if(argc!=4)return 2;
 std::ifstream raw(argv[1]),map(argv[2]);std::filesystem::path output(argv[3]);
 std::vector<int> indices;int col;
 while(map>>col)indices.push_back(col);
 if(!raw||indices.empty())return 3;
 std::string line;int columns=0;long declared=0;
 while(std::getline(raw,line)){if(line.rfind("No. Variables:",0)==0)columns=std::stoi(line.substr(14));if(line.rfind("No. Points:",0)==0)declared=std::stol(line.substr(11));if(line=="Values:")break;}
 if(!columns||declared<2||!raw)return 4;
 std::vector<int> slot(columns,-1);
 for(size_t i=0;i<indices.size();i++){if(indices[i]<=0||indices[i]>=columns||slot[indices[i]]!=-1)return 5;slot[indices[i]]=i;}
 std::vector<std::ofstream> files(indices.size());std::vector<std::vector<char>> buffers(indices.size());
 for(size_t i=0;i<indices.size();i++){
  auto path=output/("boundary_"+std::to_string(i)+".pwl");if(std::filesystem::exists(path))return 6;
  buffers[i].resize(65536);files[i].rdbuf()->pubsetbuf(buffers[i].data(),buffers[i].size());files[i].open(path);if(!files[i])return 7;
 }
 long samples=0;double previous=-1;
 while(std::getline(raw,line)){
  if(line.empty())continue;char*end;long index=std::strtol(line.c_str(),&end,10);double t=std::strtod(end,&end);
  if(index!=samples||!std::isfinite(t)||t<=previous)return 8;previous=t;char time[64];std::snprintf(time,sizeof(time),"%.17g",t);
  for(int i=1;i<columns;i++){
   if(!std::getline(raw,line))return 9;char*last;double v=std::strtod(line.c_str(),&last);if(last==line.c_str()||!std::isfinite(v))return 10;
   if(slot[i]>=0)files[slot[i]]<<time<<' '<<line<<'\n';
  }
  ++samples;if(samples%5000==0)std::cout<<"samples="<<samples<<std::endl;
 }
 for(auto&f:files){f.flush();if(!f)return 11;}
 if(samples!=declared||std::abs(previous-260e-9)>1e-18)return 12;
 std::cout<<"complete samples="<<samples<<" boundaries="<<indices.size()<<std::endl;return 0;
}
