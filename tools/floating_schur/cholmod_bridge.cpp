// Sparse harmonic extension for a strictly positive floating capacitor graph.
// No capacitance or retained device is changed by this linear solve.
#include <cholmod.h>
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <limits>
#include <utility>
#include <vector>
#include <omp.h>

struct Graph {
    int n, m, threads;
    cholmod_common common;
    cholmod_factor* factor=nullptr;
    std::vector<std::vector<std::pair<int,long double>>> ff, fb, by_boundary;
    std::vector<long double> fbdiag;
    Graph(int n_,int m_,int t):n(n_),m(m_),threads(t),ff(n_),fb(n_),by_boundary(m_),fbdiag(n_,0) {
        cholmod_start(&common);common.print=0;common.nthreads_max=t;
        common.supernodal=CHOLMOD_SUPERNODAL;
    }
    ~Graph(){if(factor)cholmod_free_factor(&factor,&common);cholmod_finish(&common);}
};

extern "C" {
int floating_long_double_digits(){return std::numeric_limits<long double>::digits;}
void* floating_create(int n,int m,int nff,const int* ai,const int* aj,const double* av,
                     const long double* al,int nfb,const int* wi,const int* wj,
                     const double* wv,const long double* wl,int threads){
    Graph* g=nullptr;
    try {
        if(n<=0||m<=0||threads<1)return nullptr;
        g=new Graph(n,m,threads);std::vector<long double> diagonal(n,0);
        auto* triplet=cholmod_allocate_triplet(n,n,n+nff,-1,CHOLMOD_REAL,&g->common);
        if(!triplet){delete g;return nullptr;}
        auto* rows=static_cast<int*>(triplet->i);auto* cols=static_cast<int*>(triplet->j);
        auto* values=static_cast<double*>(triplet->x);
        for(int k=0;k<nff;k++){
            int a=ai[k],b=aj[k];
            if(a<0||b<0||a>=n||b>=n||a==b||!(av[k]>0)||!(al[k]>0)){
                cholmod_free_triplet(&triplet,&g->common);delete g;return nullptr;
            }
            diagonal[a]+=al[k];diagonal[b]+=al[k];
            g->ff[a].push_back({b,al[k]});g->ff[b].push_back({a,al[k]});
            rows[k]=std::max(a,b);cols[k]=std::min(a,b);values[k]=-av[k];
        }
        for(int k=0;k<nfb;k++){
            int a=wi[k],b=wj[k];
            if(a<0||a>=n||b<0||b>=m||!(wv[k]>0)||!(wl[k]>0)){
                cholmod_free_triplet(&triplet,&g->common);delete g;return nullptr;
            }
            diagonal[a]+=wl[k];g->fbdiag[a]+=wl[k];
            g->fb[a].push_back({b,wl[k]});g->by_boundary[b].push_back({a,wl[k]});
        }
        for(int i=0;i<n;i++){
            rows[nff+i]=i;cols[nff+i]=i;values[nff+i]=static_cast<double>(diagonal[i]);
        }
        triplet->nnz=n+nff;
        auto* matrix=cholmod_triplet_to_sparse(triplet,n+nff,&g->common);
        cholmod_free_triplet(&triplet,&g->common);
        if(!matrix){delete g;return nullptr;}
        g->factor=cholmod_analyze(matrix,&g->common);
        int okay=g->factor&&cholmod_factorize(matrix,g->factor,&g->common)
            &&g->factor->minor==static_cast<size_t>(n)&&g->common.status==CHOLMOD_OK;
        cholmod_free_sparse(&matrix,&g->common);
        if(!okay){delete g;return nullptr;}
        return g;
    } catch(...){delete g;return nullptr;}
}
int floating_solve(void* handle,int first,int width,double* all_h){
    auto* g=static_cast<Graph*>(handle);
    if(!g||first<0||width<=0||first+width>g->m)return 0;
    auto* rhs=cholmod_zeros(g->n,width,CHOLMOD_REAL,&g->common);
    if(!rhs)return 0;
    auto* data=static_cast<double*>(rhs->x);
    for(int j=0;j<width;j++)for(auto [i,c]:g->by_boundary[first+j])
        data[i+static_cast<size_t>(j)*g->n]+=static_cast<double>(c);
    auto* solution=cholmod_solve(CHOLMOD_A,g->factor,rhs,&g->common);
    cholmod_free_dense(&rhs,&g->common);
    if(!solution)return 0;
    auto* x=static_cast<double*>(solution->x);
    #pragma omp parallel for num_threads(g->threads)
    for(int i=0;i<g->n;i++)for(int j=0;j<width;j++)
        all_h[static_cast<size_t>(i)*g->m+first+j]=x[i+static_cast<size_t>(j)*g->n];
    cholmod_free_dense(&solution,&g->common);return 1;
}
int floating_products(void* handle,const double* h,double* residual,long double* q,
                      long double* statistics){
    auto* g=static_cast<Graph*>(handle);if(!g)return 0;
    long double square_sum=0,max_abs=0;int bad=0;
    #pragma omp parallel num_threads(g->threads) reduction(+:square_sum,bad) reduction(max:max_abs)
    {
        std::vector<long double> row(g->m);
        #pragma omp for
        for(int i=0;i<g->n;i++){
            const double* own=h+static_cast<size_t>(i)*g->m;
            for(int b=0;b<g->m;b++)row[b]=g->fbdiag[i]*static_cast<long double>(own[b]);
            for(auto [j,c]:g->ff[i]){
                const double* other=h+static_cast<size_t>(j)*g->m;
                for(int b=0;b<g->m;b++)row[b]+=c*(static_cast<long double>(own[b])-other[b]);
            }
            for(auto [b,c]:g->fb[i])row[b]-=c;
            for(int b=0;b<g->m;b++){
                double value=static_cast<double>(row[b]);
                if(!std::isfinite(value)){residual[static_cast<size_t>(i)*g->m+b]=value;bad++;continue;}
                residual[static_cast<size_t>(i)*g->m+b]=value;
                square_sum+=static_cast<long double>(value)*value;
                max_abs=std::max(max_abs,std::abs(static_cast<long double>(value)));
            }
        }
    }
    #pragma omp parallel for num_threads(g->threads)
    for(int b=0;b<g->m;b++){
        long double* row=q+static_cast<size_t>(b)*g->m;
        std::fill(row,row+g->m,0);
        for(auto [i,c]:g->by_boundary[b]){
            const double* hi=h+static_cast<size_t>(i)*g->m;
            for(int j=0;j<g->m;j++)row[j]+=c*static_cast<long double>(hi[j]);
        }
    }
    statistics[0]=square_sum;statistics[1]=max_abs;return bad==0;
}
void floating_free(void* handle){delete static_cast<Graph*>(handle);}
}
