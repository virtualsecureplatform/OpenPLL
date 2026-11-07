#include <array>
#include <cmath>
#include <cstdlib>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <sstream>
#include <string>
#include <vector>
#include <cctype>
struct Device { int model,d,g,s,b; long count; };
struct Extreme {double low=std::numeric_limits<double>::infinity(),high=-std::numeric_limits<double>::infinity();long low_sample=-1,high_sample=-1;size_t low_card=0,high_card=0;double low_time=0,high_time=0;};
bool remainder_blank(const char*p){while(*p){if(!std::isspace(static_cast<unsigned char>(*p)))return false;++p;}return true;}
int main(int argc,char**argv){
 if(argc!=4)return 2;
 char*window_end;double start_ns=std::strtod(argv[3],&window_end);
 if(window_end==argv[3]||!remainder_blank(window_end)||!std::isfinite(start_ns)||start_ns<0||start_ns>=260)return 2;
 double start_s=start_ns/1e9;long selected_samples=0;double first_selected=-1;
 std::ifstream raw(argv[1]),mapping(argv[2]);int models=0,expected_columns=0;long expected_devices=0,expected_cards=0;
 if(!raw||!(mapping>>models>>expected_columns>>expected_devices>>expected_cards)||models<=0||models>100||expected_columns<2||expected_devices<=0||expected_cards<=0)return 3;
 std::vector<Device> devices;Device d;long expanded=0;
 std::string mapline;
 while(std::getline(mapping,mapline)){
  if(mapline.find_first_not_of(" \t\r")==std::string::npos)continue;
  std::istringstream row(mapline);std::string extra;
  if(!(row>>d.model>>d.d>>d.g>>d.s>>d.b>>d.count)||(row>>extra))return 4;
  if(d.model<0||d.model>=models||d.count<=0)return 4;
  for(int i:{d.d,d.g,d.s,d.b})if(i< -1||i==0||i>=expected_columns)return 4;
  expanded+=d.count;if(expanded>expected_devices)return 4;devices.push_back(d);
 }
 if(!mapping.eof()||long(devices.size())!=expected_cards||expanded!=expected_devices)return 5;
 std::string line;int columns=0;long declared=0;
 while(std::getline(raw,line)){if(line.rfind("No. Variables:",0)==0)columns=std::stoi(line.substr(14));if(line.rfind("No. Points:",0)==0)declared=std::stol(line.substr(11));if(line=="Values:")break;}
 if(!raw||columns!=expected_columns||declared<2)return 6;
 std::vector<double> values(columns);std::vector<std::array<Extreme,6>> extrema(models);long samples=0;double previous=-1;
 while(std::getline(raw,line)){
  if(line.empty())continue;char*end;long index=std::strtol(line.c_str(),&end,10);if(end==line.c_str())return 7;
  char*start=end;double t=std::strtod(start,&end);if(end==start||index!=samples||!std::isfinite(t)||t<=previous||!remainder_blank(end))return 7;
  if(samples==0&&t!=0)return 7;previous=t;
  for(int i=1;i<columns;i++){
   if(!std::getline(raw,line))return 8;char*tail;double v=std::strtod(line.c_str(),&tail);
   if(tail==line.c_str()||!std::isfinite(v)||!remainder_blank(tail))return 9;values[i]=v;
  }
  auto v=[&](int i){return i<0?0.0:values[i];};
  if(t>=start_s){
  if(!selected_samples)first_selected=t;++selected_samples;
  for(size_t j=0;j<devices.size();j++){
   auto&device=devices[j];double D=v(device.d),G=v(device.g),S=v(device.s),B=v(device.b);
   std::array<double,6> diffs={D-S,G-S,G-D,G-B,B-S,B-D};
   for(size_t k=0;k<diffs.size();k++){
    double x=diffs[k];if(!std::isfinite(x))return 10;auto&e=extrema[device.model][k];
    if(x<e.low){e.low=x;e.low_sample=samples;e.low_card=j;e.low_time=t;}
    if(x>e.high){e.high=x;e.high_sample=samples;e.high_card=j;e.high_time=t;}
   }
  }
  }
  ++samples;if(samples%5000==0)std::cerr<<"samples="<<samples<<'\n';
 }
 if(samples!=declared||std::abs(previous-260e-9)>1e-18)return 11;
 const char*relations[]={"DS","GS","GD","GB","BS","BD"};std::cout<<std::setprecision(17);
 for(int m=0;m<models;m++)for(int k=0;k<6;k++){
  auto&e=extrema[m][k];if(!std::isfinite(e.low)||!std::isfinite(e.high))return 12;
  std::cout<<"EXT\t"<<m<<'\t'<<relations[k]<<'\t'<<e.low<<'\t'<<e.high<<'\t'<<e.low_sample<<'\t'<<e.low_time<<'\t'<<e.low_card<<'\t'<<e.high_sample<<'\t'<<e.high_time<<'\t'<<e.high_card<<'\n';
 }
 std::cout<<"WINDOW\t"<<start_ns<<'\t'<<selected_samples<<'\t'<<first_selected<<'\n';
 std::cout<<"COMPLETE\t"<<samples<<'\t'<<columns<<'\t'<<expanded<<'\t'<<devices.size()<<'\t'<<previous<<'\n';return std::cout?0:13;
}
