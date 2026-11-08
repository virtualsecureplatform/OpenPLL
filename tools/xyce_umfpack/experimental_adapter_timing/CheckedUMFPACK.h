// Experimental iterative refinement with current-equation checks and fresh fallback.
// This is a linear solver optimization; it never changes the input matrix or RHS.
#ifndef OPENPLL_DOUBLE_PRODUCT_UMFPACK_H
#define OPENPLL_DOUBLE_PRODUCT_UMFPACK_H
#include <umfpack.h>
#include <algorithm>
#include <cmath>
#include <limits>
#include <vector>
#include <utility>

class CheckedUMFPACK {
    int n_ = 0;
    std::vector<int> ap_, ai_;
    std::vector<double> ax_, factorValues_, rowValues_;
    std::vector<int> rowPtr_, rowCols_, rowFromCSC_;
    std::vector<long double> rowNorm_;
    void *symbolic_ = nullptr, *numeric_ = nullptr;
    double control_[UMFPACK_CONTROL], info_[UMFPACK_INFO];

    int triangular(const double *b, double *x) {
        double options[UMFPACK_CONTROL];
        std::copy(control_, control_ + UMFPACK_CONTROL, options);
        options[UMFPACK_IRSTEP] = 0;
        return umfpack_di_solve(UMFPACK_A, ap_.data(), ai_.data(), ax_.data(),
                                x, b, numeric_, options, info_);
    }

    double residual(const double *x, const double *b, std::vector<double> &r, bool mixed = false) const {
        r.resize(n_);double maximum=0;
        for(int i=0;i<n_;++i){
            long double sum=b[i],scale=std::abs(static_cast<long double>(b[i]));
            for(int p=rowPtr_[i];p<rowPtr_[i+1];++p){
                long double term=static_cast<long double>(rowValues_[p])*x[rowCols_[p]];
                sum-=term;scale+=std::abs(term);
            }
            if(!std::isfinite(sum)||!std::isfinite(scale))return std::numeric_limits<double>::infinity();
            r[i]=static_cast<double>(sum);
            long double denominator=mixed ? 1e-13L*scale+1e-16L*rowNorm_[i] : scale;
            long double error=denominator>0 ? std::abs(sum)/denominator : (sum==0 ? 0 : std::numeric_limits<long double>::infinity());
            maximum=std::max(maximum,static_cast<double>(error));
        }
        return maximum;
    }

    bool smallChange() const {
        if (factorValues_.size() != ax_.size()) return false;
        std::vector<long double> changes(n_, 0), scales(n_, 0);
        for (size_t p = 0; p < ax_.size(); ++p) {
            changes[ai_[p]] += std::abs(static_cast<long double>(ax_[p]) - factorValues_[p]);
            scales[ai_[p]] += std::abs(static_cast<long double>(factorValues_[p]));
        }
        for (int i = 0; i < n_; ++i)
            if (!std::isfinite(changes[i]) || changes[i] > .05L * scales[i]) return false;
        return true;
    }

    // Weighted left-preconditioned GMRES. The old factors are only a
    // preconditioner; every operator application uses the current matrix.
    // Independent current-equation refinement below remains the acceptance gate.
    bool krylov(const double *b, double *x) {
        if (triangular(b, x) != UMFPACK_OK) return false;
        const int limit = 12;
        std::vector<double> r, z(n_), scale(n_), product(n_);
        if (!std::isfinite(residual(x, b, r))) return false;
        if (triangular(r.data(), z.data()) != UMFPACK_OK) return false;
        auto dot = [](const std::vector<double> &a, const std::vector<double> &b) {
            long double s = 0;
            for (size_t i = 0; i < a.size(); ++i) s += static_cast<long double>(a[i]) * b[i];
            return static_cast<double>(s);
        };
        auto norm = [&](const std::vector<double> &v) { return std::sqrt(dot(v,v)); };
        for (int i = 0; i < n_; ++i) {
            scale[i] = 1e-12 + 1e-10 * std::abs(x[i]);
            z[i] /= scale[i];
        }
        double beta = norm(z);
        if (!std::isfinite(beta)) return false;
        if (beta <= .05) return true;
        std::vector<std::vector<double>> basis(limit+1, std::vector<double>(n_));
        for (int i = 0; i < n_; ++i) basis[0][i] = z[i] / beta;
        double h[limit+1][limit] = {}, c[limit] = {}, s[limit] = {}, g[limit+1] = {};
        g[0] = beta;
        int used = 0;
        std::vector<double> sums(n_);
        for (int k = 0; k < limit; ++k) {
            for(int j=0;j<n_;++j)sums[j]=scale[j]*basis[k][j];
            for(int i=0;i<n_;++i){
                double value=0;
                for(int p=rowPtr_[i];p<rowPtr_[i+1];++p)
                    value+=rowValues_[p]*sums[rowCols_[p]];
                product[i]=static_cast<double>(value);
            }
            if (triangular(product.data(), z.data()) != UMFPACK_OK) return false;
            ++krylovSolves;
            for (int i = 0; i < n_; ++i) z[i] /= scale[i];
            // Two passes limit loss of orthogonality on ill-conditioned systems.
            for (int pass = 0; pass < 2; ++pass)
                for (int j = 0; j <= k; ++j) {
                    double value = dot(z, basis[j]);
                    if (!std::isfinite(value)) return false;
                    h[j][k] += value;
                    for (int i = 0; i < n_; ++i) z[i] -= value * basis[j][i];
                }
            h[k+1][k] = norm(z);
            if (!std::isfinite(h[k+1][k])) return false;
            const bool breakdown = h[k+1][k] == 0;
            if (!breakdown)
                for (int i = 0; i < n_; ++i) basis[k+1][i] = z[i] / h[k+1][k];
            for (int j = 0; j < k; ++j) {
                double a = c[j]*h[j][k] + s[j]*h[j+1][k];
                h[j+1][k] = -s[j]*h[j][k] + c[j]*h[j+1][k];
                h[j][k] = a;
            }
            double magnitude = std::hypot(h[k][k], h[k+1][k]);
            if (!std::isfinite(magnitude) || magnitude == 0) return false;
            c[k] = h[k][k] / magnitude; s[k] = h[k+1][k] / magnitude;
            h[k][k] = magnitude; h[k+1][k] = 0;
            g[k+1] = -s[k]*g[k]; g[k] *= c[k]; used = k+1;
            if (std::abs(g[k+1]) <= .05 || breakdown) break;
        }
        double y[limit] = {};
        for (int i = used-1; i >= 0; --i) {
            long double value = g[i];
            for (int j = i+1; j < used; ++j) value -= static_cast<long double>(h[i][j])*y[j];
            if (h[i][i] == 0) return false;
            y[i] = static_cast<double>(value/h[i][i]);
            if (!std::isfinite(y[i])) return false;
        }
        for (int i = 0; i < n_; ++i) {
            long double value = 0;
            for (int j = 0; j < used; ++j) value += static_cast<long double>(basis[j][i])*y[j];
            x[i] += static_cast<double>(value*scale[i]);
            if (!std::isfinite(x[i])) return false;
        }
        return true;
    }

    bool refine(const double *b, double *x, bool supplied = false) {
        if (!supplied && triangular(b, x) != UMFPACK_OK) return false;
        std::vector<double> r(n_), correction(n_);
        double previousCorrection = std::numeric_limits<double>::infinity();
        double error = residual(x, b, r, true);
        if (!std::isfinite(error)) return false;
        for (int iteration = 0; iteration < 6; ++iteration) {
            if (triangular(r.data(), correction.data()) != UMFPACK_OK) return false;
            double scaled = 0;
            bool allZero = true;
            for (int i = 0; i < n_; ++i) {
                if (!std::isfinite(x[i]) || !std::isfinite(correction[i])) return false;
                const double next = x[i] + correction[i];
                scaled = std::max(scaled, std::abs(correction[i]) /
                    (1e-12 + 1e-10 * std::max(std::abs(x[i]), std::abs(next))));
                allZero = allZero && correction[i] == 0;
                x[i] = next;
            }
            ++refinementSolves;
            error = residual(x, b, r, true);
            lastMixedResidualRatio = error;
            // Once GMRES has reduced the correction to roundoff, a ratio
            // between successive rounding errors is not a contraction test.
            // Require two current-equation corrections 100x below the original
            // correction threshold, with a mixed current-equation residual bound.
            if (supplied && error <= 1 && scaled <= .01) {
                if (previousCorrection <= .01) return true;
                previousCorrection = scaled;
                continue;
            }
            if (!supplied && error <= 1 && scaled <= 1 &&
                (allZero || (iteration > 0 && scaled <= .5 * previousCorrection)))
                return true;
            if (iteration > 0 && scaled > .8 * previousCorrection) return false;
            previousCorrection = scaled;
        }
        return false;
    }

    int fresh(const double *b, double *x, bool transpose) {
        if (!symbolic_) {
            ++symbolicCalls;
            int status = umfpack_di_symbolic(n_, n_, ap_.data(), ai_.data(), ax_.data(),
                                             &symbolic_, control_, info_);
            if (status != UMFPACK_OK) return status;
        }
        umfpack_di_free_numeric(&numeric_);
        ++numericCalls;
        int status = umfpack_di_numeric(ap_.data(), ai_.data(), ax_.data(), symbolic_,
                                       &numeric_, control_, info_);
        if (status != UMFPACK_OK) {
            umfpack_di_free_numeric(&numeric_);
            return status;
        }
        factorValues_ = ax_;
        return umfpack_di_solve(transpose ? UMFPACK_At : UMFPACK_A,
            ap_.data(), ai_.data(), ax_.data(), x, b, numeric_, control_, info_);
    }

public:
    long symbolicCalls = 0, numericCalls = 0, reuseAttempts = 0;
    long reuseAccepted = 0, exactReuseAccepted = 0, refinementSolves = 0;
    long krylovSolves = 0;
    double lastMixedResidualRatio = 0;
    bool lastUsedReuse = false;

    CheckedUMFPACK() { umfpack_di_defaults(control_); }
    CheckedUMFPACK(const CheckedUMFPACK&) = delete;
    CheckedUMFPACK &operator=(const CheckedUMFPACK&) = delete;
    ~CheckedUMFPACK() {
        umfpack_di_free_numeric(&numeric_);
        umfpack_di_free_symbolic(&symbolic_);
    }

    bool hasNumeric() const { return numeric_ != nullptr; }
    void invalidate() { umfpack_di_free_numeric(&numeric_); factorValues_.clear(); }

    void matrix(int n, std::vector<int> ap, std::vector<int> ai, std::vector<double> ax) {
        if (n != n_ || ap != ap_ || ai != ai_) {
            umfpack_di_free_numeric(&numeric_);
            umfpack_di_free_symbolic(&symbolic_);
            factorValues_.clear();
            n_ = n; ap_ = std::move(ap); ai_ = std::move(ai);
            rowPtr_.assign(n_+1,0);
            for(int row:ai_)++rowPtr_[row+1];
            for(int i=0;i<n_;++i)rowPtr_[i+1]+=rowPtr_[i];
            auto next=rowPtr_;rowCols_.resize(ai_.size());rowFromCSC_.resize(ai_.size());
            for(int j=0;j<n_;++j)for(int p=ap_[j];p<ap_[j+1];++p){
                int at=next[ai_[p]]++;rowCols_[at]=j;rowFromCSC_[at]=p;
            }
        }
        ax_ = std::move(ax);
        rowValues_.resize(ax_.size());rowNorm_.assign(n_,0);
        for(int i=0;i<n_;++i)for(int p=rowPtr_[i];p<rowPtr_[i+1];++p){
            rowValues_[p]=ax_[rowFromCSC_[p]];
            rowNorm_[i]+=std::abs(static_cast<long double>(rowValues_[p]));
        }
    }

    int solve(const double *b, double *x, bool allowReuse,
              bool explicitSameMatrixReuse = false, bool transpose = false) {
        lastUsedReuse = false;
        if (numeric_ && factorValues_ == ax_ && (allowReuse || explicitSameMatrixReuse)) {
            ++exactReuseAccepted;
            int status = umfpack_di_solve(transpose ? UMFPACK_At : UMFPACK_A,
                ap_.data(), ai_.data(), ax_.data(), x, b, numeric_, control_, info_);
            if (status == UMFPACK_OK) { lastUsedReuse = true; return status; }
        }
        if (allowReuse && !transpose && numeric_) {
            ++reuseAttempts;
            if (krylov(b, x) && refine(b, x, true)) {
                ++reuseAccepted; lastUsedReuse = true; return UMFPACK_OK;
            }
        }
        return fresh(b, x, transpose);
    }

    double mixedResidualRatio(const double *x, const double *b) const {
        std::vector<double> r; return residual(x,b,r,true);
    }

    double componentwiseError(const double *x, const double *b) const {
        std::vector<double> r;
        return residual(x, b, r);
    }
};
#endif
