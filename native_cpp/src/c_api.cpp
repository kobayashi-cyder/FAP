#include "fap/native_api.h"
#include "fap/native_core.hpp"

#include <cstdlib>
#include <cstring>
#include <filesystem>
#include <sstream>
#include <string>
#include <vector>

namespace {

std::string json_escape(const std::string& value) {
    std::ostringstream out;
    for (unsigned char c : value) {
        switch (c) {
            case '\\': out << "\\\\"; break;
            case '"': out << "\\\""; break;
            case '\n': out << "\\n"; break;
            case '\r': out << "\\r"; break;
            case '\t': out << "\\t"; break;
            default:
                if (c >= 0x20) out << static_cast<char>(c);
        }
    }
    return out.str();
}

char* duplicate_string(const std::string& value) {
    auto* out = static_cast<char*>(std::malloc(value.size() + 1));
    if (!out) return nullptr;
    std::memcpy(out, value.c_str(), value.size() + 1);
    return out;
}

using Engine = fap::cppcore::NativeOrchestrator;

}  // namespace

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

fap_native_engine fap_native_engine_create(const char* repository_root) {
    try {
        if (repository_root && *repository_root) {
            return static_cast<fap_native_engine>(
                new Engine(std::filesystem::path(repository_root)));
        }
        return static_cast<fap_native_engine>(new Engine());
    } catch (...) {
        return nullptr;
    }
}

void fap_native_engine_destroy(fap_native_engine engine) {
    delete static_cast<Engine*>(engine);
}

char* fap_native_engine_analyze_json(
    fap_native_engine engine,
    const char* text,
    double uncertainty,
    int disagreement,
    int counterexample,
    double confidence) {
    if (!engine || !text) return nullptr;

    try {
        const auto decision = static_cast<Engine*>(engine)->analyze(
            text,
            {},
            uncertainty,
            disagreement != 0,
            counterexample != 0,
            confidence);

        std::ostringstream out;
        out << "{\"version\":\"" << json_escape(fap::cppcore::kVersion) << "\""
            << ",\"budget\":{"
            << "\"routes\":" << decision.budget.routes
            << ",\"steps\":" << decision.budget.steps
            << ",\"verify\":" << decision.budget.verify
            << ",\"retries\":" << decision.budget.retries
            << "}"
            << ",\"extra_path\":" << (decision.extra_path ? "true" : "false")
            << ",\"multi_intents\":" << decision.intents.size()
            << ",\"intents\":[";

        for (std::size_t i = 0; i < decision.intents.size(); ++i) {
            if (i) out << ",";
            out << "{\"name\":\"" << json_escape(decision.intents[i].name)
                << "\",\"confidence\":" << decision.intents[i].confidence << "}";
        }
        out << "]";

        if (decision.semantic_route) {
            const auto& route = *decision.semantic_route;
            out << ",\"route\":\"" << json_escape(route.route) << "\""
                << ",\"rule_id\":\"" << json_escape(route.rule_id) << "\""
                << ",\"resource_id\":\"" << json_escape(route.resource_id) << "\""
                << ",\"action_id\":\"" << json_escape(route.action_id) << "\""
                << ",\"route_score\":" << route.score;
        } else {
            out << ",\"route\":null"
                << ",\"rule_id\":null"
                << ",\"resource_id\":null"
                << ",\"action_id\":null";
        }
        out << "}";

        return duplicate_string(out.str());
    } catch (...) {
        return nullptr;
    }
}

void fap_native_string_free(char* value) {
    std::free(value);
}
