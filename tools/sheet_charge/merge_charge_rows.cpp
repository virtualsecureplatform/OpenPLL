#include "../charge_compiler/json.hpp"
#include "charge_rows.hpp"
#include <queue>
#include <memory>
#include <iostream>
#include <time.h>
using I=long long;
static double now(){timespec t{};require(clock_gettime(CLOCK_BOOTTIME,&t)==0,"clock");return t.tv_sec+t.tv_nsec*1e-9;}
struct Item{sparse::Record record;size_t source;bool operator>(const Item&b)const{return record.key>b.record.key;}};
int main(int argc,char**argv){try{
 require(argc==2,"usage CONFIG");auto cfg=Json::read(argv[1]);double deadline=cfg.at("deadline_uptime").num();auto&paths=cfg.at("inputs").arr();require(!paths.empty()&&paths.size()<=128,"bounded charge merge inputs");std::vector<std::unique_ptr<charge::Reader>> readers;std::priority_queue<Item,std::vector<Item>,std::greater<Item>> queue;uint64_t rows=0,columns=0;
 for(size_t i=0;i<paths.size();i++){auto reader=std::make_unique<charge::Reader>(paths[i].str());if(i==0){rows=reader->rows;columns=reader->columns;}else require(rows==reader->rows&&columns==reader->columns,"matching charge dimensions");sparse::Record r;if(reader->next(r))queue.push({r,i});readers.push_back(std::move(reader));}
 std::ofstream output(cfg.at("output").str(),std::ios::binary);require(bool(output),"merged charge output");charge::header(output,rows,columns,0);uint64_t count=0,nonzero_rows=0,current_row=UINT64_MAX;bool nonzero=false;sparse::Sum row_sum,row_l1;long double maximum=0;
 auto finish=[&](){if(current_row==UINT64_MAX)return;if(nonzero)nonzero_rows++;long double scale=row_l1.value();long double residual=scale?std::fabs(row_sum.value())/scale:0;maximum=std::max(maximum,residual);row_sum={};row_l1={};nonzero=false;};
 while(!queue.empty()){if(count%10000==0)require(now()<deadline,"charge merge deadline");uint64_t key=queue.top().record.key;sparse::Value value;do{auto item=queue.top();queue.pop();value.merge(item.record.value,item.record.absolute,item.record.terms);sparse::Record next;if(readers[item.source]->next(next))queue.push({next,item.source});}while(!queue.empty()&&queue.top().record.key==key);sparse::Record r{key,value.signed_sum.value(),value.absolute_sum.value(),value.terms};charge::record(output,r,rows,columns);count++;uint64_t row=key>>32;if(row!=current_row){finish();current_row=row;}row_sum.add(r.value);row_l1.add(std::fabs(r.value));nonzero=nonzero||r.value!=0;}
 finish();output.seekp(24);char bytes[8];sparse::store(bytes,count);output.write(bytes,8);output.close();require(bool(output),"merged charge close");Json report=Json::object();report["charge_rows"]=I(rows);report["voltage_columns"]=I(columns);report["entries"]=I(count);report["nonzero_charge_rows"]=I(nonzero_rows);report["zero_charge_rows"]=I(rows-nonzero_rows);report["maximum_scaled_global_voltage_gauge_residual"]=double(maximum);std::cout<<report.dump()<<'\n';return 0;
 }catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
