#pragma once

#ifdef __cplusplus
extern "C" {
#endif

typedef struct fap_native_budget {
    int routes;
    int steps;
    int verify;
    int retries;
} fap_native_budget;

const char* fap_native_version(void);

fap_native_budget fap_native_adaptive_budget(
    const double* weights,
    const int* counts,
    int signal_count,
    double uncertainty,
    int disagreement);

int fap_native_needs_extra_path(
    double confidence,
    int disagreement,
    int counterexample);

#ifdef __cplusplus
}
#endif
