#include "fap/native_api.h"
#include "fap/native_core.hpp"

#include <vector>

const char* fap_native_version(void) {
    return fap::cppcore::kVersion;
}

fap_native_budget fap_native_adaptive_budget(
    const double* weights,
    const int* counts,
    int signal_count,
    double uncertainty,
    int disagreement) {
    std::vector<fap::cppcore::Signal> signals;
    if (weights && counts && signal_count > 0) {
        signals.reserve(static_cast<std::size_t>(signal_count));
        for (int i = 0; i < signal_count; ++i) {
            signals.push_back({"ffi", weights[i], counts[i]});
        }
    }
    const auto budget = fap::cppcore::adaptive_budget(
        signals,
        uncertainty,
        disagreement != 0);
    return {
        budget.routes,
        budget.steps,
        budget.verify,
        budget.retries
    };
}

int fap_native_needs_extra_path(
    double confidence,
    int disagreement,
    int counterexample) {
    return fap::cppcore::needs_extra_path(
        confidence,
        disagreement != 0,
        counterexample != 0) ? 1 : 0;
}
