#pragma once
// Directed MPFR enclosures for exact rational polynomial fringe moments.
#include "../charge_compiler/json.hpp"
#include <mpfr.h>
#include <gmpxx.h>
#include <array>
namespace fringe_interval {
inline thread_local mpfr_prec_t precision=128;
class Interval {
public:
 mpfr_t lo,hi;
 Interval() { mpfr_init2(lo,precision); mpfr_init2(hi,precision); mpfr_set_zero(lo,1); mpfr_set_zero(hi,1); }
 explicit Interval(const mpq_class& q):Interval() {mpfr_set_q(lo,q.get_mpq_t(),MPFR_RNDD);mpfr_set_q(hi,q.get_mpq_t(),MPFR_RNDU);}
 Interval(const Interval& b):Interval() {mpfr_set(lo,b.lo,MPFR_RNDD);mpfr_set(hi,b.hi,MPFR_RNDU);}
 Interval& operator=(const Interval& b) {if(this!=&b){mpfr_set(lo,b.lo,MPFR_RNDD);mpfr_set(hi,b.hi,MPFR_RNDU);}return *this;}
 ~Interval(){mpfr_clear(lo);mpfr_clear(hi);}
 void finite()const {require(mpfr_number_p(lo)&&mpfr_number_p(hi)&&mpfr_cmp(lo,hi)<=0,"finite ordered MPFR interval");}
};
inline Interval operator+(const Interval&a,const Interval&b) {
 Interval r;mpfr_add(r.lo,a.lo,b.lo,MPFR_RNDD);mpfr_add(r.hi,a.hi,b.hi,MPFR_RNDU);r.finite();return r;
}
inline Interval operator-(const Interval&a,const Interval&b) {
 Interval r;mpfr_sub(r.lo,a.lo,b.hi,MPFR_RNDD);mpfr_sub(r.hi,a.hi,b.lo,MPFR_RNDU);r.finite();return r;
}
inline Interval operator*(const Interval&a,const Interval&b) {
 Interval r,t;bool first=true;
 for(auto x:{a.lo,a.hi})for(auto y:{b.lo,b.hi}) {
  mpfr_mul(t.lo,x,y,MPFR_RNDD);mpfr_mul(t.hi,x,y,MPFR_RNDU);
  if(first||mpfr_cmp(t.lo,r.lo)<0)mpfr_set(r.lo,t.lo,MPFR_RNDD);
  if(first||mpfr_cmp(t.hi,r.hi)>0)mpfr_set(r.hi,t.hi,MPFR_RNDU);first=false;
 }r.finite();return r;
}
inline Interval operator/(const Interval&a,const Interval&b) {
 require(mpfr_sgn(b.lo)>0||mpfr_sgn(b.hi)<0,"interval divisor excludes zero");
 Interval reciprocal;mpfr_ui_div(reciprocal.lo,1,b.hi,MPFR_RNDD);mpfr_ui_div(reciprocal.hi,1,b.lo,MPFR_RNDU);
 return a*reciprocal;
}
inline Interval atan(const Interval&a) {Interval r;mpfr_atan(r.lo,a.lo,MPFR_RNDD);mpfr_atan(r.hi,a.hi,MPFR_RNDU);r.finite();return r;}
inline Interval log1p(const Interval&a) {require(mpfr_cmp_si(a.lo,-1)>0,"log1p domain");Interval r;mpfr_log1p(r.lo,a.lo,MPFR_RNDD);mpfr_log1p(r.hi,a.hi,MPFR_RNDU);r.finite();return r;}
inline std::array<Interval,4> primitive(const mpq_class& coordinate,const mpq_class& multiplier) {
 require(coordinate>=0&&multiplier>0,"fringe primitive domain");
 Interval d(coordinate),m(multiplier),two(mpq_class(2)),a=atan(d*m),l=log1p(d*d*m*m);
 return {a,l/(two*m),d/m-a/(m*m),d*d/(two*m)-l/(two*m*m*m)};
}
inline Interval integrate(const std::array<mpq_class,4>& polynomial,const mpq_class& lower,
                          const mpq_class& upper,const mpq_class& multiplier) {
 require(lower>=0&&upper>=lower&&multiplier>=0,"fringe integral domain");
 if(multiplier==0||lower==upper)return Interval();
 auto left=primitive(lower,multiplier),right=primitive(upper,multiplier);Interval result;
 for(int k=0;k<4;k++)if(polynomial[k]!=0)result=result+Interval(polynomial[k])*(right[k]-left[k]);
 return result;
}
inline Json endpoint(mpfr_srcptr x) {
 mpz_class n;auto exponent=mpfr_get_z_2exp(n.get_mpz_t(),x);
 return Json::Array{n.get_str(),static_cast<long long>(exponent)};
}
inline Json json(const Interval& x) {
 Json r=Json::object();r["lower_dyadic"]=endpoint(x.lo);r["upper_dyadic"]=endpoint(x.hi);
 r["precision_bits"]=static_cast<long long>(precision);return r;
}
}
