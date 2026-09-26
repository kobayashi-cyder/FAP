#include "fap/native_core.hpp"

#include <algorithm>
#include <chrono>
#include <cstdint>
#include <cstdlib>
#include <iomanip>
#include <iostream>
#include <string>
#include <vector>

using namespace fap::cppcore;
using clock_type = std::chrono::steady_clock;

namespace {
volatile std::uint64_t sink = 0;

template <class Fn>
double bench_ns(std::size_t iterations, Fn&& fn) {
    const auto start = clock_type::now();
    for (std::size_t i = 0; i < iterations; ++i) {
        sink = sink + static_cast<std::uint64_t>(fn(i));
    }
    const auto end = clock_type::now();
    const auto ns = std::chrono::duration_cast<std::chrono::nanoseconds>(end - start).count();
    return static_cast<double>(ns) / static_cast<double>(iterations);
}

void warmup(std::size_t n, SemanticActionRouter& router, SemanticMemoryStore& memory, MultiIntentPlanner& planner) {
    for (std::size_t i = 0; i < n; ++i) {
        const auto b = adaptive_budget({{"multi", 0.9, 5}, {"verify", 0.7, 2}}, 0.65, true);
        sink = sink + static_cast<std::uint64_t>(b.steps);
        const auto r = router.match("猫の画像を生成して");
        sink = sink + static_cast<std::uint64_t>(r ? r->route.size() : 0);
        const auto m = memory.recall("C++ FAP native memory", 4);
        sink = sink + static_cast<std::uint64_t>(m.size());
        const auto intents = planner.detect("今日の天気と今何時か、それと2+2を計算");
        sink = sink + static_cast<std::uint64_t>(intents.size());
    }
}
}  // namespace

int main(int argc, char** argv) {
    std::size_t iterations = 1'000'000;
    if (argc >= 2) iterations = std::max<std::size_t>(1, std::strtoull(argv[1], nullptr, 10));
    const std::string root = argc >= 3 ? argv[2] : ".";

    SemanticActionRouter router;
    router.load_from_root(root);
    if (router.resource_count() == 0 || router.action_count() == 0 || router.rule_count() == 0) {
        router.add_resource({"image", {"画像", "image"}});
        router.add_action({"create", {"生成", "作って", "create"}});
        router.add_rule({"image_create", "image", "create", "media.image.create"});
    }

    SemanticMemoryStore memory;
    const std::vector<std::string> memories = {
        "目標はFAPをC++化することです。","回答は日本語で出力してください。",
        "C++ native core build verified","semantic router verified","WASM UI bridge verified",
        "FAP native memory is bounded","repository agent remains compatibility boundary",
        "Android JNI is a target","dynamic sparse routing is preferred",
        "verification expands under uncertainty","counterexamples open an extra path",
        "semantic routing is data driven","native UI can operate in native only mode",
        "C ABI exposes deterministic decisions","Python remains for compatibility",
        "benchmark compares identical runner hardware"
    };
    for (const auto& row : memories) memory.absorb_user(row, true);

    MultiIntentPlanner planner;
    warmup(std::min<std::size_t>(10'000, iterations / 10 + 1), router, memory, planner);

    const double budget_ns = bench_ns(iterations, [](std::size_t i) {
        const auto b = adaptive_budget(
            {{"multi_step", 0.9, static_cast<int>((i % 7) + 1)}, {"verification", 0.7, 2}}, 0.65, true);
        return b.routes + b.steps + b.verify + b.retries;
    });
    const double routing_ns = bench_ns(iterations, [&](std::size_t i) {
        const auto r = router.match((i & 1) ? "猫の画像を生成して" : "image create");
        return r ? r->route.size() + r->resource_id.size() + r->action_id.size() : 0;
    });
    const double memory_ns = bench_ns(iterations, [&](std::size_t i) {
        const auto rows = memory.recall((i & 1) ? "C++ FAP native memory" : "日本語 出力 FAP", 4);
        return rows.size() + (rows.empty() ? 0 : rows.front().text.size());
    });
    const double intent_ns = bench_ns(iterations, [&](std::size_t i) {
        const auto rows = planner.detect((i & 1)
            ? "今日の天気と今何時か、それと2+2を計算"
            : "weather and time and 2+2 calculation");
        return rows.size();
    });

    std::cout << std::fixed << std::setprecision(3)
              << "{" << "\"runtime\":\"cpp\","
              << "\"iterations\":" << iterations << ","
              << "\"budget_ns_per_op\":" << budget_ns << ","
              << "\"routing_ns_per_op\":" << routing_ns << ","
              << "\"memory_ns_per_op\":" << memory_ns << ","
              << "\"intent_ns_per_op\":" << intent_ns << ","
              << "\"checksum\":" << sink << "}\n";
    return 0;
}
