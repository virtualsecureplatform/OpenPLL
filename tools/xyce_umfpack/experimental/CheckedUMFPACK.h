// Experimental iterative refinement with current-equation checks and fresh fallback.
// This is a linear solver optimization; it never changes the input matrix or RHS.
#ifndef OPENPLL_CHECKED_UMFPACK_H
#define OPENPLL_CHECKED_UMFPACK_H
#include <umfpack.h>
#include <algorithm>
#include <cmath>
#include <limits>
#include <vector>
#include <utility>

class CheckedUMFPACK {
    int n_ = 0;
    std::vector<int> ap_, ai_;
    std::vector<double> ax_, factorValues_;
    void *symbolic_ = nullptr, *numeric_ = nullptr;
    double control_[UMFPACK_CONTROL], info_[UMFPACK_INFO];

    int triangular(const double *b, double *x) {
        double options[UMFPACK_CONTROL];
        std::copy(control_, control_ + UMFPACK_CONTROL, options);
        options[UMFPACK_IRSTEP] = 0;
        return umfpack_di_solve(UMFPACK_A, ap_.data(), ai_.data(), ax_.data(),
                                x, b, numeric_, options, info_);
    }

    double residual(const double *x, const double *b, std::vector<double> &r) const {
        std::vector<long double> sums(n_), scales(n_);
        for (int i = 0; i < n_; ++i) {
            sums[i] = b[i];
            scales[i] = std::abs(static_cast<long double>(b[i]));
        }
        for (int j = 0; j < n_; ++j) {
            for (int p = ap_[j]; p < ap_[j+1]; ++p) {
                long double term = static_cast<long double>(ax_[p]) * x[j];
                sums[ai_[p]] -= term;
                scales[ai_[p]] += std::abs(term);
            }
        }
        double maximum = 0;
        r.resize(n_);
        for (int i = 0; i < n_; ++i) {
            if (!std::isfinite(sums[i]) || !std::isfinite(scales[i]))
                return std::numeric_limits<double>::infinity();
            r[i] = static_cast<double>(sums[i]);
            long double error = scales[i] > 0 ? std::abs(sums[i]) / scales[i]
                : (sums[i] == 0 ? 0 : std::numeric_limits<long double>::infinity());
            maximum = std::max(maximum, static_cast<double>(error));
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

    bool refine(const double *b, double *x) {
        if (triangular(b, x) != UMFPACK_OK) return false;
        std::vector<double> r(n_), correction(n_);
        double previousCorrection = std::numeric_limits<double>::infinity();
        double error = residual(x, b, r);
        if (!std::isfinite(error)) return false;
        for (int iteration = 0; iteration < 3; ++iteration) {
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
            error = residual(x, b, r);
            lastComponentwiseError = error;
            if (error <= 1e-13 && scaled <= 1 &&
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
    double lastComponentwiseError = 0;
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
        }
        ax_ = std::move(ax);
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
        if (allowReuse && !transpose && numeric_ && smallChange()) {
            ++reuseAttempts;
            if (refine(b, x)) {
                ++reuseAccepted; lastUsedReuse = true; return UMFPACK_OK;
            }
        }
        return fresh(b, x, transpose);
    }

    double componentwiseError(const double *x, const double *b) const {
        std::vector<double> r;
        return residual(x, b, r);
    }
};
#endif
