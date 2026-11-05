// Small strict JSON transport for compiler metadata and receipts; no dependencies.
#pragma once
#include <charconv>
#include <cmath>
#include <fstream>
#include <map>
#include <stdexcept>
#include <string>
#include <string_view>
#include <variant>
#include <vector>

inline void require(bool ok, const std::string& why) {
    if (!ok) throw std::runtime_error(why);
}
struct Json {
    using Array = std::vector<Json>;
    using Object = std::map<std::string, Json>;
    std::variant<std::nullptr_t, bool, double, std::string, Array, Object> value;
    Json(): value(nullptr) {}
    Json(bool x): value(x) {}
    Json(double x): value(x) { require(std::isfinite(x), "nonfinite JSON number"); }
    Json(int x): Json(double(x)) {}
    Json(long long x): Json(double(x)) { require(x >= -9007199254740991LL && x <= 9007199254740991LL, "integer precision"); }
    Json(const char* x): value(std::string(x)) {}
    Json(std::string x): value(std::move(x)) {}
    Json(Array x): value(std::move(x)) {}
    Json(Object x): value(std::move(x)) {}
    static Json array() { return Array{}; }
    static Json object() { return Object{}; }
    const Array& arr() const { return std::get<Array>(value); }
    const Object& obj() const { return std::get<Object>(value); }
    const std::string& str() const { return std::get<std::string>(value); }
    double num() const { return std::get<double>(value); }
    long long integer() const { double n=num(); require(std::trunc(n)==n && std::abs(n)<=9007199254740991., "invalid JSON integer"); return (long long)n; }
    bool boolean() const { return std::get<bool>(value); }
    const Json& at(const std::string& k) const { return obj().at(k); }
    const Json& at(size_t k) const { return arr().at(k); }
    Json& operator[](const std::string& k) { return std::get<Object>(value)[k]; }
    void push(Json x) { std::get<Array>(value).push_back(std::move(x)); }
    static void quoted(std::string& out, const std::string& s) {
        out += '"';
        const char* hex="0123456789abcdef";
        for (unsigned char c:s) {
            if (c=='"' || c=='\\') { out+='\\'; out+=char(c); }
            else if (c<32) { out+="\\u00"; out+=hex[c>>4]; out+=hex[c&15]; }
            else out+=char(c);
        }
        out += '"';
    }
    void append(std::string& out) const {
        if (std::holds_alternative<std::nullptr_t>(value)) out+="null";
        else if (auto p=std::get_if<bool>(&value)) out+=*p?"true":"false";
        else if (auto p=std::get_if<double>(&value)) {
            char b[64]; auto r=std::to_chars(b,b+64,*p,std::chars_format::general,17);
            require(r.ec==std::errc{}, "number serialization"); out.append(b,r.ptr);
        } else if (auto p=std::get_if<std::string>(&value)) quoted(out,*p);
        else if (auto p=std::get_if<Array>(&value)) {
            out+='['; bool first=true; for (const auto& x:*p) { if (!first) out+=','; first=false; x.append(out); } out+=']';
        } else {
            out+='{'; bool first=true; for (const auto& [k,x]:obj()) { if (!first) out+=','; first=false; quoted(out,k); out+=':'; x.append(out); } out+='}';
        }
    }
    std::string dump() const { std::string out; append(out); return out; }
    struct Parser;
    static Json parse(std::string_view s);
    static Json read(const std::string& path) {
        std::ifstream in(path,std::ios::binary); require(bool(in), "cannot open "+path);
        std::string s((std::istreambuf_iterator<char>(in)),{}); return parse(s);
    }
};
struct Json::Parser {
    std::string_view s; size_t p=0;
    void ws() { while(p<s.size() && (s[p]==' ' || s[p]=='\n' || s[p]=='\r' || s[p]=='\t')) ++p; }
    bool take(char c) { ws(); if(p<s.size() && s[p]==c) { ++p; return true; } return false; }
    unsigned hex4() {
        require(p+4<=s.size(),"truncated unicode"); unsigned n=0;
        for(int i=0;i<4;++i) { char c=s[p++]; unsigned v=c>='0'&&c<='9'?c-'0':c>='a'&&c<='f'?c-'a'+10:c>='A'&&c<='F'?c-'A'+10:99; require(v<16,"unicode escape"); n=n*16+v; } return n;
    }
    std::string string() {
        require(take('"'),"string required"); std::string out;
        while(p<s.size()) {
            unsigned char c=s[p++]; if(c=='"') return out;
            require(c>=32,"JSON control character");
            if(c!='\\') { out+=char(c); continue; }
            require(p<s.size(),"truncated escape"); char e=s[p++];
            switch(e) {
            case '"': case '\\': case '/': out+=e; break;
            case 'b':out+='\b';break; case 'f':out+='\f';break; case 'n':out+='\n';break; case 'r':out+='\r';break; case 't':out+='\t';break;
            case 'u': {
                unsigned n=hex4();
                if(n>=0xd800 && n<=0xdbff) { require(p+2<=s.size() && s.substr(p,2)=="\\u","missing surrogate"); p+=2; unsigned low=hex4(); require(low>=0xdc00&&low<=0xdfff,"invalid surrogate"); n=0x10000+(n-0xd800)*1024+low-0xdc00; }
                else require(n<0xdc00||n>0xdfff,"unpaired surrogate");
                if(n<128) out+=char(n);
                else if(n<2048) {out+=char(0xc0|(n>>6));out+=char(0x80|(n&63));}
                else if(n<65536) {out+=char(0xe0|(n>>12));out+=char(0x80|((n>>6)&63));out+=char(0x80|(n&63));}
                else {out+=char(0xf0|(n>>18));out+=char(0x80|((n>>12)&63));out+=char(0x80|((n>>6)&63));out+=char(0x80|(n&63));} break;
            }
            default: throw std::runtime_error("invalid escape");
            }
        } throw std::runtime_error("unterminated string");
    }
    Json parse(int depth=0) {
        require(depth<128,"JSON nesting limit"); ws(); require(p<s.size(),"truncated JSON");
        if(s[p]=='"') return string();
        if(take('{')) { Object o; if(take('}')) return o; do { auto k=string(); require(take(':'),"missing colon"); require(o.emplace(k,parse(depth+1)).second,"duplicate key"); } while(take(',')); require(take('}'),"missing object end"); return o; }
        if(take('[')) { Array a; if(take(']')) return a; do {a.push_back(parse(depth+1));}while(take(',')); require(take(']'),"missing array end");return a; }
        for(auto [word,result]:std::vector<std::pair<std::string,Json>>{{"true",true},{"false",false},{"null",Json{}}}) if(s.substr(p,word.size())==word) {p+=word.size();return result;}
        size_t start=p; if(s[p]=='-') ++p; require(p<s.size(),"truncated number");
        if(s[p]=='0') ++p; else {require(s[p]>='1'&&s[p]<='9',"invalid number"); while(p<s.size()&&s[p]>='0'&&s[p]<='9')++p;}
        if(p<s.size()&&s[p]=='.') {++p; size_t a=p;while(p<s.size()&&s[p]>='0'&&s[p]<='9')++p;require(p>a,"missing fraction");}
        if(p<s.size()&&(s[p]=='e'||s[p]=='E')) {++p;if(p<s.size()&&(s[p]=='+'||s[p]=='-'))++p;size_t a=p;while(p<s.size()&&s[p]>='0'&&s[p]<='9')++p;require(p>a,"missing exponent");}
        double n; auto r=std::from_chars(s.data()+start,s.data()+p,n); require(r.ec==std::errc{}&&r.ptr==s.data()+p,"invalid numeric value");return n;
    }
};
inline Json Json::parse(std::string_view s) { Parser p{s}; Json out=p.parse(); p.ws();require(p.p==s.size(),"trailing JSON");return out; }
