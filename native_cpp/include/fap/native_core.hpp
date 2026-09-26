#pragma once

#include <filesystem>
#include <optional>
#include <string>
#include <unordered_set>
#include <vector>

namespace fap::cppcore {

inline constexpr const char* kVersion = "1.0.01-cpp-native-r006";

struct Signal {
    std::string kind;
    double weight{0.5};
    int count{1};
};

struct Budget {
    int routes{1};
    int steps{8};
    int verify{1};
    int retries{0};

    bool operator==(const Budget&) const = default;
};

Budget adaptive_budget(
    const std::vector<Signal>& signals = {},
    double uncertainty = 0.0,
    bool disagreement = false);

bool needs_extra_path(
    double confidence,
    bool disagreement = false,
    bool counterexample = false);

struct SemanticResource {
    std::string resource_id;
    std::vector<std::string> aliases;
};

struct SemanticAction {
    std::string action_id;
    std::vector<std::string> aliases;
};

struct SemanticActionRule {
    std::string rule_id;
    std::string resource_id;
    std::string action_id;
    std::string route;
};

struct SemanticMatch {
    std::string rule_id;
    std::string resource_id;
    std::string action_id;
    std::string route;
    std::vector<std::string> resource_hits;
    std::vector<std::string> action_hits;
    double score{0.0};
};

class SemanticActionRouter {
public:
    bool load_from_root(const std::filesystem::path& root);
    void clear();

    void add_resource(SemanticResource value);
    void add_action(SemanticAction value);
    void add_rule(SemanticActionRule value);

    std::optional<SemanticMatch> match(const std::string& text) const;

    std::size_t resource_count() const noexcept { return resources_.size(); }
    std::size_t action_count() const noexcept { return actions_.size(); }
    std::size_t rule_count() const noexcept { return rules_.size(); }

private:
    std::vector<SemanticResource> resources_;
    std::vector<SemanticAction> actions_;
    std::vector<SemanticActionRule> rules_;
};

struct GoalState {
    std::string open_goal;
    std::vector<std::string> goals;
    std::vector<std::string> constraints;
    std::vector<std::string> facts;
    std::string updated_at;
};

class PersistentGoalState {
public:
    explicit PersistentGoalState(std::filesystem::path root);

    GoalState load(const std::string& sid) const;
    GoalState update(const std::string& sid, const std::string& text) const;
    std::string summary(const std::string& sid) const;

private:
    std::filesystem::path path_for(const std::string& sid) const;
    void save(const std::string& sid, const GoalState& state) const;

    std::filesystem::path root_;
};

struct ToolIntent {
    std::string name;
    double confidence{0.95};
};

class MultiIntentPlanner {
public:
    std::vector<ToolIntent> detect(const std::string& text) const;
};

struct CriticResult {
    std::string verdict{"OK"};
    std::vector<std::string> issues;
    bool unknown_boundary{false};
};

struct ResultView {
    bool ok{true};
    std::string reply;
    bool has_artifacts{false};
};

class CoverageCritic {
public:
    CriticResult evaluate(
        const std::string& text,
        const ResultView& result,
        const GoalState& state) const;
};

struct MemoryEntry {
    std::string category;
    std::string slot;
    std::string text;
    bool verified{true};
    int mentions{1};
    double salience{0.5};
};

class SemanticMemoryStore {
public:
    static constexpr std::size_t kMaxEntries = 128;

    void absorb_user(const std::string& text, bool explicit_remember = false);
    void add_verified_experience(const std::string& text, double salience = 0.58);

    std::vector<MemoryEntry> recall(
        const std::string& query,
        std::size_t limit = 8) const;

    const std::vector<MemoryEntry>& entries() const noexcept { return entries_; }

    static double similarity(const std::string& a, const std::string& b);

private:
    void upsert(
        const std::string& category,
        const std::string& text,
        bool verified,
        double salience);
    void compact();

    std::vector<MemoryEntry> entries_;
};

struct NativeDecision {
    Budget budget;
    bool extra_path{false};
    std::vector<ToolIntent> intents;
    std::optional<SemanticMatch> semantic_route;
};

class NativeOrchestrator {
public:
    explicit NativeOrchestrator(std::filesystem::path root = {});

    NativeDecision analyze(
        const std::string& text,
        const std::vector<Signal>& signals = {},
        double uncertainty = 0.0,
        bool disagreement = false,
        bool counterexample = false,
        double confidence = 1.0) const;

    SemanticActionRouter& router() noexcept { return router_; }
    const SemanticActionRouter& router() const noexcept { return router_; }

private:
    SemanticActionRouter router_;
    MultiIntentPlanner planner_;
};

}  // namespace fap::cppcore
