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

typedef void* fap_native_engine;

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

fap_native_engine fap_native_engine_create(const char* repository_root);
void fap_native_engine_destroy(fap_native_engine engine);

char* fap_native_engine_analyze_json(
    fap_native_engine engine,
    const char* text,
    double uncertainty,
    int disagreement,
    int counterexample,
    double confidence);

void fap_native_string_free(char* value);

#ifdef __cplusplus
}
#endif
