#include <sys/mman.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <unistd.h>
#include <cmath>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <string>
#include <string_view>
#include <thread>
#include <vector>
#include <iomanip>
struct Stats {uint64_t caps=0,zero=0,negative=0;long double sum=0,min=std::numeric_limits<long double>::infinity(),max=0;std::string error;};
std::string_view token(std::string_view &line){auto n=line.find_first_not_of(" \t\r");if(n==line.npos){line={};return {};};line.remove_prefix(n);n=line.find_first_of(" \t\r");auto t=line.substr(0,n);if(n==line.npos)line={};else line.remove_prefix(n);return t;}
void row(std::string_view line,Stats &s){if(line.empty()||line[0]!='C')return;auto id=token(line);if(id.size()<2)throw std::runtime_error("empty C identifier");for(char c:id.substr(1))if(c<'0'||c>'9')throw std::runtime_error("non-numeric C identifier");auto a=token(line),b=token(line),v=token(line);if(a.empty()||b.empty()||v.empty())throw std::runtime_error("incomplete C record");auto tail=token(line);if(!tail.empty()&&tail[0]!='$'&&tail!="**FLOATING")throw std::runtime_error("unexpected capacitor trailing token");std::string value(v);char *end=nullptr;long double x=strtold(value.c_str(),&end),factor=1;std::string suffix(end);if(suffix=="f")factor=1e-15L;else if(suffix=="p")factor=1e-12L;else if(suffix=="n")factor=1e-9L;else if(suffix=="u")factor=1e-6L;else if(suffix=="m")factor=1e-3L;else if(suffix=="k")factor=1e3L;else if(suffix=="G")factor=1e9L;else if(!suffix.empty())throw std::runtime_error("unsupported capacitance suffix");if(end==value.c_str()||!std::isfinite(x))throw std::runtime_error("invalid capacitance");x*=factor;if(!std::isfinite(x))throw std::runtime_error("capacitance overflow");s.caps++;if(x==0)s.zero++;else{s.sum+=x;if(x<0)s.negative++;else s.min=std::min(s.min,x);s.max=std::max(s.max,std::fabs(x));}}
int main(int argc,char**argv){try{if(argc!=4)throw std::runtime_error("usage input threads report");int threads=std::stoi(argv[2]);if(threads<1||threads>32)throw std::runtime_error("thread bounds");int fd=open(argv[1],O_RDONLY);if(fd<0)throw std::runtime_error("open");struct stat st;if(fstat(fd,&st)||st.st_size<=0)throw std::runtime_error("size");size_t size=st.st_size;char*data=(char*)mmap(nullptr,size,PROT_READ,MAP_PRIVATE,fd,0);if(data==MAP_FAILED)throw std::runtime_error("mmap");std::vector<Stats> stats(threads);std::vector<std::thread> jobs;for(int t=0;t<threads;t++)jobs.emplace_back([&,t]{try{size_t begin=size*t/threads,end=size*(t+1)/threads;if(begin&&data[begin-1]!='\n')while(begin<size&&data[begin++]!='\n'){};while(begin<end){size_t stop=begin;while(stop<size&&data[stop]!='\n')stop++;row(std::string_view(data+begin,stop-begin),stats[t]);begin=stop+1;}}catch(const std::exception&e){stats[t].error=e.what();}});for(auto&t:jobs)t.join();Stats total;for(auto&s:stats){if(!s.error.empty())throw std::runtime_error(s.error);total.caps+=s.caps;total.zero+=s.zero;total.negative+=s.negative;total.sum+=s.sum;total.min=std::min(total.min,s.min);total.max=std::max(total.max,s.max);}munmap(data,size);close(fd);std::ofstream out(argv[3]);out<<std::setprecision(20)<<"{\n\"capacitor_records\":"<<total.caps<<",\n\"printed_zero_capacitor_records\":"<<total.zero<<",\n\"positive_capacitor_records\":"<<total.caps-total.zero-total.negative<<",\n\"negative_capacitor_records\":"<<total.negative<<",\n\"serialized_capacitance_sum_F_diagnostic\":"<<total.sum<<",\n\"minimum_positive_capacitance_F\":";if(std::isfinite(total.min))out<<total.min;else out<<"null";out<<",\n\"maximum_absolute_capacitance_F\":"<<total.max<<",\n\"threads\":"<<threads<<",\n\"full_matrix_equivalence_verified\":false}\n";if(!out)throw std::runtime_error("report write");}catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
