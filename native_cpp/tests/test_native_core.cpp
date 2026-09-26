#include "fap/native_api.h"
#include "fap/native_core.hpp"

#include <filesystem>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

using namespace fap::cppcore;

namespace {

void require(bool condition, const std::string& message) {
    if (!condition) throw std::runtime_error(message);
}

void test_budget() {
    const auto base = adaptive_budget();
    require(base.routes == 1, "baseline routes must remain sparse");
    require(base.verify == 1, "baseline verify must remain sparse");
    require(base.steps == 8, "baseline steps mismatch");

    const auto hard = adaptive_budget(
        {{"multi_step", 0.9, 5}, {"verification", 0.8, 3}},
        0.8,
        true);
    require(hard.routes >= base.routes, "hard task did not grow routes");
    require(hard.steps >= base.steps, "hard task did not grow steps");
    require(hard.verify >= base.verify, "hard task did not grow verify");
    require(hard.routes <= 8 && hard.steps <= 96 && hard.verify <= 6 && hard.retries <= 4,
            "budget exceeded public bounds");
}

void test_extra_path() {
    require(!needs_extra_path(0.95), "high confidence should stay sparse");
    require(needs_extra_path(0.60), "low confidence should open extra path");
    require(needs_extra_path(0.95, true, false), "disagreement should open extra path");
    require(needs_extra_path(0.95, false, true), "counterexample should open extra path");
}

void test_router() {
    SemanticActionRouter router;
    router.add_resource({"image", {"画像", "image"}});
    router.add_action({"create", {"作って", "生成"}});
    router.add_rule({"image_create", "image", "create", "media.image.create"});
    const auto hit = router.match("猫の画像を作って");
    require(hit.has_value(), "semantic route missing");
    require(hit->route == "media.image.create", "semantic route wrong");
    require(hit->resource_id == "image", "resource wrong");
    require(hit->action_id == "create", "action wrong");
}

void test_multi_intent() {
    MultiIntentPlanner planner;
    const auto intents = planner.detect("今日の天気と今何時か、それと2+2を計算");
    require(intents.size() >= 2, "multi-intent detection failed");
    require(planner.detect("画像を作って").empty(), "builder request must not be fragmented");
}

void test_critic() {
    CoverageCritic critic;
    GoalState state;
    state.constraints = {"JSON必須"};
    const auto result = critic.evaluate(
        "JSONを作成して",
        ResultView{true, "OK", false},
        state);
    require(result.verdict == "PARTIAL", "critic must flag missing artifact/coverage");
    require(!result.issues.empty(), "critic issue list empty");
}

void test_memory() {
    SemanticMemoryStore memory;
    memory.absorb_user("今後の回答は日本語で出力してください。");
    memory.absorb_user("目標はFAPをC++化することです。");
    memory.add_verified_experience("C++ native core build verified", 0.8);
    require(!memory.entries().empty(), "memory absorb failed");
    const auto hits = memory.recall("C++ FAP native", 4);
    require(!hits.empty(), "memory recall failed");
}

void test_goal_state() {
    const auto root = std::filesystem::temp_directory_path() / "fap_cpp_native_test_state";
    std::error_code ec;
    std::filesystem::remove_all(root, ec);

    PersistentGoalState store(root);
    const auto state = store.update(
        "case",
        "目標はFAPをC++で実装して完成させる。Pythonだけには固定しないで。");
    require(!state.open_goal.empty(), "goal extraction failed");
    require(!state.goals.empty(), "goal history failed");
    require(!state.constraints.empty(), "constraint extraction failed");

    const auto loaded = store.load("case");
    require(loaded.open_goal == state.open_goal, "goal state persistence failed");
    require(store.summary("case").find("現在の目標") != std::string::npos, "summary failed");

    std::filesystem::remove_all(root, ec);
}

void test_orchestrator() {
    NativeOrchestrator fap;
    fap.router().add_resource({"memory", {"記憶", "memory"}});
    fap.router().add_action({"inspect", {"確認", "inspect"}});
    fap.router().add_rule({"memory_inspect", "memory", "inspect", "memory.inspect"});
    const auto d = fap.analyze(
        "記憶を確認",
        {{"uncertain", 0.8, 4}},
        0.7,
        false,
        false,
        0.65);
    require(d.extra_path, "orchestrator extra path failed");
    require(d.semantic_route && d.semantic_route->route == "memory.inspect",
            "orchestrator semantic route failed");
}

void test_c_api_ui_bridge() {
    require(std::string(fap_native_version()) == kVersion, "C API version mismatch");

    fap_native_engine engine = fap_native_engine_create(nullptr);
    require(engine != nullptr, "C API engine creation failed");

    char* json = fap_native_engine_analyze_json(
        engine,
        "今日の天気と今何時か",
        0.7,
        1,
        0,
        0.65);
    require(json != nullptr, "C API analyze returned null");

    const std::string payload(json);
    fap_native_string_free(json);
    fap_native_engine_destroy(engine);

    require(payload.find("\"version\":\"1.0.01-cpp-native-r002\"") != std::string::npos,
            "C API JSON version missing");
    require(payload.find("\"budget\"") != std::string::npos,
            "C API JSON budget missing");
    require(payload.find("\"extra_path\":true") != std::string::npos,
            "C API JSON extra path missing");
    require(payload.find("\"multi_intents\"") != std::string::npos,
            "C API JSON multi intent count missing");
}

}  // namespace

int main() {
    try {
        test_budget();
        test_extra_path();
        test_router();
        test_multi_intent();
        test_critic();
        test_memory();
        test_goal_state();
        test_orchestrator();
        test_c_api_ui_bridge();
        std::cout << "fap_native_tests: PASS\n";
        return 0;
    } catch (const std::exception& e) {
        std::cerr << "fap_native_tests: FAIL: " << e.what() << "\n";
        return 1;
    }
}
