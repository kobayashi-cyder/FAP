#pragma once

#include "fap/native_core.hpp"

#include <algorithm>
#include <array>
#include <cmath>
#include <cstddef>
#include <string>
#include <utility>
#include <vector>

namespace fap::cppcore {

struct ResponseLane {
    std::string lane_id;
    std::string role;
    std::string group;
    int variant{0};
    double priority{1.0};
    bool verifier{false};
    bool partial_ok{true};
};

struct ResponseRedundancyPlan {
    int capacity{64};
    int active_lanes{6};
    int synthesis_width{2};
    int quorum{2};
    int independent_groups{4};
    double pressure{0.0};
    double coverage_target{0.55};
    bool partial_coverage_allowed{true};
    std::vector<ResponseLane> lanes;
};

class ResponseRedundancyPlanner {
public:
    static constexpr int kMaxLanes = 64;
    static constexpr int kMaxSynthesis = 8;

    static double structural_pressure(const std::string& text, int intent_count = 0) {
        const auto cp = utf8_codepoints(text);
        const double chars = std::min(1.0, static_cast<double>(cp) / 1600.0);
        std::size_t separators = 0;
        for (const auto& token : std::array<std::string, 8>{"\n","。","！","？",";","；",":","："}) {
            std::size_t pos = 0;
            while ((pos = text.find(token, pos)) != std::string::npos) {
                ++separators;
                pos += token.size();
            }
        }
        const double sep_score = std::min(1.0, static_cast<double>(separators) / 24.0);
        const double chunk_score = std::min(1.0, static_cast<double>(separators) / 12.0);
        const double intent_score = std::min(1.0, static_cast<double>(std::max(0, intent_count - 1)) / 6.0);
        return clip01(0.40 * chars + 0.25 * sep_score + 0.20 * chunk_score + 0.15 * intent_score);
    }

    ResponseRedundancyPlan plan(
        const std::string& text,
        const Budget& budget,
        double uncertainty = 0.0,
        double confidence = 1.0,
        bool disagreement = false,
        bool counterexample = false,
        int intent_count = 0,
        bool has_route = false) const {
        const int routes = std::clamp(budget.routes, 1, 8);
        const int verify = std::clamp(budget.verify, 1, 6);
        const int retries = std::clamp(budget.retries, 0, 4);
        intent_count = std::clamp(intent_count, 0, 16);

        const double structural = structural_pressure(text, intent_count);
        double pressure = clip01(
            0.18 * clip01(uncertainty)
            + 0.18 * (1.0 - clip01(confidence))
            + 0.10 * static_cast<double>(disagreement)
            + 0.10 * static_cast<double>(counterexample)
            + 0.16 * structural
            + 0.10 * (static_cast<double>(routes - 1) / 7.0)
            + 0.10 * (static_cast<double>(verify - 1) / 5.0)
            + 0.08 * (static_cast<double>(retries) / 4.0));
        if (!has_route && !text.empty()) pressure = std::min(1.0, pressure + 0.04);

        int active = static_cast<int>(std::lround(
            6.0 + 42.0 * pressure + 2.0 * retries + 2.0 * std::max(0, intent_count - 1)));
        active = std::clamp(active, 6, kMaxLanes);
        const int synthesis = std::clamp(2 + active / 10, 2, kMaxSynthesis);
        const int quorum = std::clamp(
            static_cast<int>(std::ceil(static_cast<double>(synthesis) * 2.0 / 3.0)),
            2,
            synthesis);
        const int groups = std::clamp((active + 2) / 3, 4, 16);

        static constexpr std::array<std::pair<const char*, const char*>, 16> roles{{
            {"direct","answer"},
            {"decomposition","structure"},
            {"assumptions","structure"},
            {"mechanism","explanation"},
            {"evidence","grounding"},
            {"counterexample","challenge"},
            {"constraints","requirements"},
            {"edge_cases","challenge"},
            {"alternatives","diversity"},
            {"procedure","action"},
            {"analogy","explanation"},
            {"uncertainty","grounding"},
            {"user_intent","requirements"},
            {"compression","synthesis"},
            {"verifier","verification"},
            {"synthesis_probe","synthesis"},
        }};

        ResponseRedundancyPlan out;
        out.capacity = kMaxLanes;
        out.active_lanes = active;
        out.synthesis_width = synthesis;
        out.quorum = quorum;
        out.independent_groups = groups;
        out.pressure = pressure;
        out.coverage_target = std::min(0.90, 0.55 + 0.35 * pressure);
        out.lanes.reserve(static_cast<std::size_t>(active));

        for (int i = 0; i < active; ++i) {
            const auto& [role, group] = roles[static_cast<std::size_t>(i) % roles.size()];
            const int variant = i / static_cast<int>(roles.size());
            const std::string role_s(role);
            const bool verifier =
                role_s == "evidence" || role_s == "counterexample" ||
                role_s == "uncertainty" || role_s == "verifier" ||
                role_s == "synthesis_probe";
            const double priority = std::max(
                0.35,
                1.0 - static_cast<double>(i) / std::max(1.0, static_cast<double>(active) * 2.4));
            out.lanes.push_back({
                std::string(group) + ":" + role + ":" + std::to_string(variant),
                role,
                group,
                variant,
                priority,
                verifier,
                true,
            });
        }
        return out;
    }

private:
    static double clip01(double value) {
        if (!std::isfinite(value)) return 0.0;
        return std::clamp(value, 0.0, 1.0);
    }

    static std::size_t utf8_codepoints(const std::string& value) {
        std::size_t count = 0;
        for (unsigned char c : value) {
            if ((c & 0xC0u) != 0x80u) ++count;
        }
        return count;
    }
};

}  // namespace fap::cppcore
