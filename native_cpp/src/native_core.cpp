#include "fap/native_core.hpp"

#include <algorithm>
#include <chrono>
#include <cmath>
#include <cctype>
#include <fstream>
#include <iomanip>
#include <regex>
#include <set>
#include <sstream>
#include <stdexcept>
#include <unordered_map>

namespace fap::cppcore {
namespace {

double clip01(double value) {
    if (!std::isfinite(value)) return 0.0;
    return std::max(0.0, std::min(1.0, value));
}

std::string ascii_lower(std::string value) {
    for (char& c : value) {
        const unsigned char u = static_cast<unsigned char>(c);
        if (u < 128) c = static_cast<char>(std::tolower(u));
    }
    return value;
}

std::string trim(std::string value) {
    auto non_space = [](unsigned char c) { return !std::isspace(c); };
    auto begin = std::find_if(value.begin(), value.end(), non_space);
    auto end = std::find_if(value.rbegin(), value.rend(), non_space).base();
    if (begin >= end) return {};
    return std::string(begin, end);
}

std::string collapse_spaces(const std::string& input) {
    std::string out;
    out.reserve(input.size());
    bool pending_space = false;
    for (unsigned char c : input) {
        if (std::isspace(c)) {
            pending_space = !out.empty();
            continue;
        }
        if (pending_space) out.push_back(' ');
        pending_space = false;
        out.push_back(static_cast<char>(c));
    }
    return trim(out);
}

void replace_all(std::string& value, const std::string& from, const std::string& to = "") {
    if (from.empty()) return;
    std::size_t pos = 0;
    while ((pos = value.find(from, pos)) != std::string::npos) {
        value.replace(pos, from.size(), to);
        pos += to.size();
    }
}

std::string compact_text(std::string value) {
    value = ascii_lower(value);
    static const std::vector<std::string> utf8_punct = {
        "‐","‑","–","—","_","・","･","、","。","，","．",
        "：","；","！","？","　"
    };
    for (const auto& p : utf8_punct) replace_all(value, p);

    std::string out;
    out.reserve(value.size());
    for (unsigned char c : value) {
        if (std::isspace(c)) continue;
        switch (c) {
            case '-': case ',': case '.': case ':': case ';':
            case '!': case '?': case '\'': case '"':
                continue;
            default:
                out.push_back(static_cast<char>(c));
        }
    }
    return out;
}

bool contains_any(const std::string& text, const std::vector<std::string>& needles) {
    const std::string lower = ascii_lower(text);
    for (const auto& n : needles) {
        if (lower.find(ascii_lower(n)) != std::string::npos) return true;
    }
    return false;
}

std::vector<std::string> split_sentences(const std::string& text) {
    std::vector<std::string> out;
    std::string current;
    for (std::size_t i = 0; i < text.size();) {
        const unsigned char c = static_cast<unsigned char>(text[i]);
        if (c == '\n' || c == '!' || c == '?') {
            const auto value = collapse_spaces(current);
            if (!value.empty()) out.push_back(value);
            current.clear();
            ++i;
            continue;
        }
        const std::string rest = text.substr(i);
        bool sep = false;
        for (const std::string& p : {"。","！","？"}) {
            if (rest.rfind(p, 0) == 0) {
                const auto value = collapse_spaces(current);
                if (!value.empty()) out.push_back(value);
                current.clear();
                i += p.size();
                sep = true;
                break;
            }
        }
        if (sep) continue;
        current.push_back(static_cast<char>(c));
        ++i;
    }
    const auto value = collapse_spaces(current);
    if (!value.empty()) out.push_back(value);
    return out;
}

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
                if (c < 0x20) {
                    out << "\\u"
                        << std::hex << std::setw(4) << std::setfill('0')
                        << static_cast<int>(c) << std::dec;
                } else {
                    out << static_cast<char>(c);
                }
        }
    }
    return out.str();
}

std::string json_unescape(const std::string& value) {
    std::string out;
    out.reserve(value.size());
    bool esc = false;
    for (char c : value) {
        if (!esc) {
            if (c == '\\') esc = true;
            else out.push_back(c);
            continue;
        }
        switch (c) {
            case 'n': out.push_back('\n'); break;
            case 'r': out.push_back('\r'); break;
            case 't': out.push_back('\t'); break;
            case '\\': out.push_back('\\'); break;
            case '"': out.push_back('"'); break;
            default: out.push_back(c); break;
        }
        esc = false;
    }
    if (esc) out.push_back('\\');
    return out;
}

std::optional<std::string> json_string(const std::string& line, const std::string& key) {
    const std::regex re("\\\"" + key + "\\\"\\s*:\\s*\\\"((?:\\\\.|[^\\\"\\\\])*)\\\"");
    std::smatch m;
    if (!std::regex_search(line, m, re)) return std::nullopt;
    return json_unescape(m[1].str());
}

std::vector<std::string> json_string_array(const std::string& line, const std::string& key) {
    const std::regex outer("\\\"" + key + "\\\"\\s*:\\s*\\[([^\\]]*)\\]");
    std::smatch m;
    if (!std::regex_search(line, m, outer)) return {};
    const std::string body = m[1].str();
    const std::regex item("\\\"((?:\\\\.|[^\\\"\\\\])*)\\\"");
    std::vector<std::string> out;
    for (std::sregex_iterator it(body.begin(), body.end(), item), end; it != end; ++it) {
        out.push_back(json_unescape((*it)[1].str()));
    }
    return out;
}

std::string now_iso8601_utc() {
    const auto now = std::chrono::system_clock::now();
    const std::time_t t = std::chrono::system_clock::to_time_t(now);
    std::tm tm{};
#if defined(_WIN32)
    gmtime_s(&tm, &t);
#else
    gmtime_r(&t, &tm);
#endif
    std::ostringstream out;
    out << std::put_time(&tm, "%Y-%m-%dT%H:%M:%SZ");
    return out.str();
}

void append_unique(std::vector<std::string>& values, const std::string& raw, std::size_t limit) {
    const std::string value = collapse_spaces(raw);
    if (value.empty()) return;
    values.erase(std::remove(values.begin(), values.end(), value), values.end());
    values.push_back(value);
    if (values.size() > limit) {
        values.erase(values.begin(), values.begin() + static_cast<std::ptrdiff_t>(values.size() - limit));
    }
}

std::string safe_sid(const std::string& sid) {
    std::string out;
    out.reserve(std::min<std::size_t>(80, sid.size()));
    for (unsigned char c : sid.empty() ? std::string("default") : sid) {
        if (std::isalnum(c) || c == '_' || c == '.' || c == '-') out.push_back(static_cast<char>(c));
        else out.push_back('_');
        if (out.size() >= 80) break;
    }
    return out.empty() ? "default" : out;
}

std::vector<std::string> extract_constraints(const std::string& text) {
    std::vector<std::string> out;
    static const std::vector<std::string> keys = {
        "しないで","使わない","禁止","不要","無し","なし","のみ","だけ","必須",
        "固定","以内","以上","以下","未満","Qwen","Gemma","E2B","Pixel",
        "Android","Python","HTML","JSON","Markdown","C++","CPP"
    };
    for (const auto& sentence : split_sentences(text)) {
        if (contains_any(sentence, keys)) append_unique(out, sentence.substr(0, 180), 16);
    }

    const std::regex numeric(
        R"(\b\d+(?:\.\d+)?(?:\s*[xX]\s*\d+(?:\.\d+)?|\s*(?:ms|KB|MB|GB|%))\b)",
        std::regex::icase);
    for (std::sregex_iterator it(text.begin(), text.end(), numeric), end; it != end; ++it) {
        append_unique(out, it->str(), 16);
    }
    return out;
}

std::string extract_goal(const std::string& text) {
    static const std::vector<std::string> goal_words = {
        "目的","目標","作って","作成して","構築して","実装して","直して",
        "改善して","続けて","進めて","仕上げて","完成させ","終わるまで",
        "達成するまで","完了するまで"
    };
    if (!contains_any(text, goal_words)) return {};
    const std::string value = collapse_spaces(text);
    return value.substr(0, std::min<std::size_t>(360, value.size()));
}

std::vector<std::string> extract_facts(const std::string& text) {
    std::vector<std::string> out;
    for (const auto& sentence : split_sentences(text)) {
        if (contains_any(sentence, {"合言葉は","私は","これは","それは","名前は","名称は"})) {
            append_unique(out, sentence.substr(0, 120), 8);
        }
    }
    return out;
}

std::vector<std::uint32_t> utf8_codepoints(const std::string& s) {
    std::vector<std::uint32_t> out;
    for (std::size_t i = 0; i < s.size();) {
        unsigned char c = static_cast<unsigned char>(s[i]);
        std::uint32_t cp = 0;
        std::size_t n = 1;
        if ((c & 0x80U) == 0) {
            cp = c;
        } else if ((c & 0xE0U) == 0xC0U && i + 1 < s.size()) {
            cp = (c & 0x1FU) << 6U;
            cp |= static_cast<unsigned char>(s[i + 1]) & 0x3FU;
            n = 2;
        } else if ((c & 0xF0U) == 0xE0U && i + 2 < s.size()) {
            cp = (c & 0x0FU) << 12U;
            cp |= (static_cast<unsigned char>(s[i + 1]) & 0x3FU) << 6U;
            cp |= static_cast<unsigned char>(s[i + 2]) & 0x3FU;
            n = 3;
        } else if ((c & 0xF8U) == 0xF0U && i + 3 < s.size()) {
            cp = (c & 0x07U) << 18U;
            cp |= (static_cast<unsigned char>(s[i + 1]) & 0x3FU) << 12U;
            cp |= (static_cast<unsigned char>(s[i + 2]) & 0x3FU) << 6U;
            cp |= static_cast<unsigned char>(s[i + 3]) & 0x3FU;
            n = 4;
        } else {
            cp = c;
        }
        out.push_back(cp);
        i += n;
    }
    return out;
}

std::string cp_token(std::uint32_t a, std::optional<std::uint32_t> b = std::nullopt) {
    std::ostringstream out;
    out << "u" << std::hex << a;
    if (b) out << "-" << *b;
    return out.str();
}

std::unordered_set<std::string> semantic_features(const std::string& text) {
    const std::string lower = ascii_lower(collapse_spaces(text));
    std::unordered_set<std::string> out;

    std::string latin;
    auto flush_latin = [&]() {
        if (!latin.empty()) {
            out.insert(latin);
            latin.clear();
        }
    };

    for (unsigned char c : lower) {
        if (c < 128 && (std::isalnum(c) || c == '_' || c == '+' || c == '.' || c == '-')) {
            latin.push_back(static_cast<char>(c));
        } else {
            flush_latin();
        }
    }
    flush_latin();

    std::vector<std::uint32_t> non_ascii;
    for (auto cp : utf8_codepoints(lower)) {
        if (cp > 127) non_ascii.push_back(cp);
        else if (!non_ascii.empty()) {
            if (non_ascii.size() <= 2) {
                for (auto x : non_ascii) out.insert(cp_token(x));
            } else {
                for (std::size_t i = 0; i + 1 < non_ascii.size(); ++i) {
                    out.insert(cp_token(non_ascii[i], non_ascii[i + 1]));
                }
            }
            non_ascii.clear();
        }
    }
    if (!non_ascii.empty()) {
        if (non_ascii.size() <= 2) {
            for (auto x : non_ascii) out.insert(cp_token(x));
        } else {
            for (std::size_t i = 0; i + 1 < non_ascii.size(); ++i) {
                out.insert(cp_token(non_ascii[i], non_ascii[i + 1]));
            }
        }
    }
    return out;
}

std::string memory_slot(const std::string& category, const std::string& text) {
    const std::string lower = ascii_lower(text);
    if (category == "preference") {
        if (contains_any(text, {"日本語","英語"}) && contains_any(text, {"出力","回答","言語"})) {
            return "preference:output_language";
        }
        if (contains_any(lower, {"json","markdown","html","csv"}) && contains_any(text, {"形式","出力","回答"})) {
            return "preference:output_format";
        }
        if (contains_any(text, {"簡潔","詳細","短く","長く","箇条書き","表形式"})) {
            return "preference:response_style";
        }
    }
    if (category == "goal" && contains_any(text, {"目的","目標"})) return "goal:primary";
    if (category == "constraint") {
        if (lower.find("qwen") != std::string::npos) return "constraint:model:qwen";
        if (lower.find("gemma") != std::string::npos || lower.find("e2b") != std::string::npos) {
            return "constraint:model:teacher";
        }
        if (contains_any(lower, {"ram","メモリ"})) return "constraint:memory";
    }
    if (category == "fact") {
        if (text.find("合言葉") != std::string::npos) return "fact:passphrase";
        if (contains_any(text, {"名前","名称"})) return "fact:name";
    }
    return {};
}

std::optional<std::string> classify_sentence(const std::string& sentence, bool explicit_remember) {
    if (sentence.size() < 3) return std::nullopt;
    if (contains_any(sentence, {"目的","目標","完成","達成","実装"})) return "goal";
    if (contains_any(sentence, {
        "使わない","禁止","不要","無し","なし","必須","固定","以内","以上","以下",
        "未満","だけ","のみ","制約","条件","RAM","メモリ","Qwen","Gemma","E2B"
    })) return "constraint";
    if (contains_any(sentence, {
        "標準","デフォルト","優先","好み","毎回","基本","出力","回答","形式","言語",
        "日本語","英語","json","markdown","html","csv"
    })) return "preference";
    if (explicit_remember) return "fact";
    if (contains_any(sentence, {"合言葉","名前","名称","バージョン","端末","環境"})) return "fact";
    return std::nullopt;
}

}  // namespace

Budget adaptive_budget(
    const std::vector<Signal>& signals,
    double uncertainty,
    bool disagreement) {
    double difficulty = 0.0;
    for (const auto& signal : signals) {
        const int count = std::min(8, std::max(1, signal.count));
        difficulty += clip01(signal.weight) * static_cast<double>(count) / 8.0;
    }

    const double pressure = clip01(
        0.55 * clip01(difficulty) +
        0.35 * clip01(uncertainty) +
        0.10 * static_cast<int>(disagreement));

    Budget out;
    out.routes = std::min(
        8,
        1 + static_cast<int>(pressure >= 0.20) +
        static_cast<int>(pressure >= 0.50) +
        static_cast<int>(pressure >= 0.80));
    out.steps = std::min(96, 8 + static_cast<int>(std::lround(72.0 * pressure)));
    out.verify = std::min(
        6,
        1 + static_cast<int>(pressure >= 0.25) +
        static_cast<int>(pressure >= 0.55) +
        static_cast<int>(pressure >= 0.80));
    out.retries = std::min(
        4,
        static_cast<int>(pressure >= 0.40) +
        static_cast<int>(pressure >= 0.75));
    return out;
}

bool needs_extra_path(double confidence, bool disagreement, bool counterexample) {
    return clip01(confidence) < 0.70 || disagreement || counterexample;
}

void SemanticActionRouter::clear() {
    resources_.clear();
    actions_.clear();
    rules_.clear();
}

void SemanticActionRouter::add_resource(SemanticResource value) {
    if (!value.resource_id.empty() && !value.aliases.empty()) resources_.push_back(std::move(value));
}

void SemanticActionRouter::add_action(SemanticAction value) {
    if (!value.action_id.empty() && !value.aliases.empty()) actions_.push_back(std::move(value));
}

void SemanticActionRouter::add_rule(SemanticActionRule value) {
    if (!value.rule_id.empty() && !value.resource_id.empty() &&
        !value.action_id.empty() && !value.route.empty()) {
        rules_.push_back(std::move(value));
    }
}

bool SemanticActionRouter::load_from_root(const std::filesystem::path& root) {
    clear();
    const auto folder = root / "knowledge";
    if (!std::filesystem::exists(folder)) return false;

    for (const auto& entry : std::filesystem::recursive_directory_iterator(folder)) {
        if (!entry.is_regular_file() || entry.path().extension() != ".jsonl") continue;
        std::ifstream in(entry.path(), std::ios::binary);
        std::string line;
        while (std::getline(in, line)) {
            const auto kind = json_string(line, "kind");
            if (!kind) continue;
            if (*kind == "semantic_resource") {
                const auto id = json_string(line, "id");
                auto aliases = json_string_array(line, "aliases");
                if (id && !id->empty() && !aliases.empty()) add_resource({*id, std::move(aliases)});
            } else if (*kind == "semantic_action") {
                const auto id = json_string(line, "id");
                auto aliases = json_string_array(line, "aliases");
                if (id && !id->empty() && !aliases.empty()) add_action({*id, std::move(aliases)});
            } else if (*kind == "semantic_action_rule") {
                const auto id = json_string(line, "id");
                const auto resource = json_string(line, "resource");
                const auto action = json_string(line, "action");
                const auto route = json_string(line, "route");
                if (id && resource && action && route) {
                    add_rule({*id, *resource, *action, *route});
                }
            }
        }
    }
    return !resources_.empty() || !actions_.empty() || !rules_.empty();
}

std::optional<SemanticMatch> SemanticActionRouter::match(const std::string& text) const {
    struct Ranked {
        double score{};
        std::string id;
        std::vector<std::string> hits;
    };

    const auto rank = [&](const auto& rows, auto get_id) -> std::optional<Ranked> {
        std::optional<Ranked> best;
        const std::string value = compact_text(text);
        for (const auto& row : rows) {
            std::vector<std::string> hits;
            std::size_t max_len = 0;
            for (const auto& alias : row.aliases) {
                const std::string token = compact_text(alias);
                if (!token.empty() && value.find(token) != std::string::npos) {
                    hits.push_back(alias);
                    max_len = std::max(max_len, token.size());
                }
            }
            if (hits.empty()) continue;
            Ranked current;
            current.score = 2.0 * static_cast<double>(hits.size()) +
                            static_cast<double>(max_len) / 20.0;
            current.id = get_id(row);
            current.hits = std::move(hits);
            if (!best || current.score > best->score ||
                (std::abs(current.score - best->score) < 1e-12 && current.id < best->id)) {
                best = std::move(current);
            }
        }
        return best;
    };

    const auto resource = rank(resources_, [](const SemanticResource& r) { return r.resource_id; });
    const auto action = rank(actions_, [](const SemanticAction& a) { return a.action_id; });
    if (!resource || !action) return std::nullopt;

    for (const auto& rule : rules_) {
        if (rule.resource_id == resource->id && rule.action_id == action->id) {
            return SemanticMatch{
                rule.rule_id,
                resource->id,
                action->id,
                rule.route,
                resource->hits,
                action->hits,
                resource->score + action->score
            };
        }
    }
    return std::nullopt;
}

PersistentGoalState::PersistentGoalState(std::filesystem::path root)
    : root_(std::move(root)) {
    if (root_.empty()) root_ = ".fap_native_state";
    std::filesystem::create_directories(root_);
}

std::filesystem::path PersistentGoalState::path_for(const std::string& sid) const {
    return root_ / (safe_sid(sid) + ".json");
}

GoalState PersistentGoalState::load(const std::string& sid) const {
    GoalState state;
    std::ifstream in(path_for(sid), std::ios::binary);
    if (!in) return state;
    std::ostringstream buf;
    buf << in.rdbuf();
    const std::string json = buf.str();
    state.open_goal = json_string(json, "open_goal").value_or("");
    state.goals = json_string_array(json, "goals");
    state.constraints = json_string_array(json, "constraints");
    state.facts = json_string_array(json, "facts");
    state.updated_at = json_string(json, "updated_at").value_or("");
    if (state.goals.size() > 20) state.goals.erase(state.goals.begin(), state.goals.end() - 20);
    if (state.constraints.size() > 40) state.constraints.erase(state.constraints.begin(), state.constraints.end() - 40);
    if (state.facts.size() > 40) state.facts.erase(state.facts.begin(), state.facts.end() - 40);
    return state;
}

void PersistentGoalState::save(const std::string& sid, const GoalState& state) const {
    std::filesystem::create_directories(root_);
    const auto write_array = [](std::ostringstream& out, const std::vector<std::string>& values) {
        out << "[";
        for (std::size_t i = 0; i < values.size(); ++i) {
            if (i) out << ",";
            out << "\"" << json_escape(values[i]) << "\"";
        }
        out << "]";
    };

    std::ostringstream out;
    out << "{\"open_goal\":\"" << json_escape(state.open_goal) << "\",\"goals\":";
    write_array(out, state.goals);
    out << ",\"constraints\":";
    write_array(out, state.constraints);
    out << ",\"facts\":";
    write_array(out, state.facts);
    out << ",\"updated_at\":\"" << json_escape(state.updated_at) << "\"}";

    const auto path = path_for(sid);
    const auto temp = path.string() + ".tmp";
    {
        std::ofstream file(temp, std::ios::binary | std::ios::trunc);
        if (!file) throw std::runtime_error("cannot write FAP native state");
        file << out.str();
    }
    std::filesystem::rename(temp, path);
}

GoalState PersistentGoalState::update(const std::string& sid, const std::string& text) const {
    GoalState state = load(sid);
    const std::string goal = extract_goal(text);
    const auto constraints = extract_constraints(text);
    const auto facts = extract_facts(text);
    if (goal.empty() && constraints.empty() && facts.empty()) return state;

    const GoalState before = state;
    if (!goal.empty()) {
        state.open_goal = goal;
        append_unique(state.goals, goal, 20);
    }
    for (const auto& item : constraints) append_unique(state.constraints, item, 40);
    for (const auto& item : facts) append_unique(state.facts, item, 40);

    if (state.open_goal == before.open_goal &&
        state.goals == before.goals &&
        state.constraints == before.constraints &&
        state.facts == before.facts) {
        return state;
    }

    state.updated_at = now_iso8601_utc();
    save(sid, state);
    return state;
}

std::string PersistentGoalState::summary(const std::string& sid) const {
    const auto state = load(sid);
    std::ostringstream out;
    if (!state.open_goal.empty()) out << "現在の目標: " << state.open_goal;
    if (!state.constraints.empty()) {
        if (out.tellp() > 0) out << "\n";
        out << "保持中の条件: ";
        const std::size_t start = state.constraints.size() > 8 ? state.constraints.size() - 8 : 0;
        for (std::size_t i = start; i < state.constraints.size(); ++i) {
            if (i != start) out << " / ";
            out << state.constraints[i];
        }
    }
    if (!state.facts.empty()) {
        if (out.tellp() > 0) out << "\n";
        out << "保持中の明示情報: ";
        const std::size_t start = state.facts.size() > 6 ? state.facts.size() - 6 : 0;
        for (std::size_t i = start; i < state.facts.size(); ++i) {
            if (i != start) out << " / ";
            out << state.facts[i];
        }
    }
    if (out.str().empty()) return "長期状態に明示的な目標・条件はまだありません。";
    return out.str();
}

std::vector<ToolIntent> MultiIntentPlanner::detect(const std::string& text) const {
    if (contains_any(text, {"作って","作成","生成","構築","build","create","make"})) return {};

    std::vector<ToolIntent> found;
    const auto maybe = [&](const char* name, const std::vector<std::string>& keys) {
        if (contains_any(text, keys)) found.push_back({name, 0.95});
    };
    maybe("weather", {"天気","気温","降水","雨","雪","晴","曇","weather","temperature"});
    maybe("datetime", {"何日","何時","曜日","日付","時刻","datetime","date","time"});
    maybe("calculator", {"計算","いくら","何%","何％","+","*","×","÷","/"});
    maybe("memory", {"覚えて","記憶","前に言った","さっき","以前の会話","memory"});
    return found.size() >= 2 ? found : std::vector<ToolIntent>{};
}

CriticResult CoverageCritic::evaluate(
    const std::string& text,
    const ResultView& result,
    const GoalState& state) const {
    CriticResult out;
    if (trim(result.reply).empty()) out.issues.push_back("empty_reply");
    if (result.ok && !result.has_artifacts &&
        contains_any(text, {"作って","作成して","生成して","構築して"})) {
        out.issues.push_back("artifact_missing");
    }
    if (result.ok && !result.has_artifacts &&
        !state.constraints.empty() && result.reply.size() < 12) {
        out.issues.push_back("constraint_coverage_weak");
    }
    out.unknown_boundary =
        result.reply.find("確定回答できません") != std::string::npos ||
        result.reply.find("分からない") != std::string::npos;
    if (!out.issues.empty()) out.verdict = "PARTIAL";
    return out;
}

double SemanticMemoryStore::similarity(const std::string& a, const std::string& b) {
    const auto x = semantic_features(a);
    const auto y = semantic_features(b);
    if (x.empty() || y.empty()) return 0.0;
    std::size_t intersection = 0;
    for (const auto& token : x) if (y.find(token) != y.end()) ++intersection;
    const std::size_t uni = x.size() + y.size() - intersection;
    return uni ? static_cast<double>(intersection) / static_cast<double>(uni) : 0.0;
}

void SemanticMemoryStore::upsert(
    const std::string& category,
    const std::string& raw_text,
    bool verified,
    double salience) {
    const std::string text = collapse_spaces(raw_text);
    if (text.empty()) return;
    const std::string slot = memory_slot(category, text);

    if (!slot.empty()) {
        for (auto& e : entries_) {
            if (e.slot == slot) {
                e.text = text;
                e.mentions += 1;
                e.salience = std::min(1.0, e.salience + 0.08);
                e.verified = verified;
                return;
            }
        }
    }

    MemoryEntry* best = nullptr;
    double best_score = 0.0;
    for (auto& e : entries_) {
        if (e.category != category || !e.slot.empty()) continue;
        const double s = similarity(text, e.text);
        if (s > best_score) {
            best_score = s;
            best = &e;
        }
    }
    if (best && best_score >= 0.58) {
        if (text.size() > best->text.size()) best->text = text;
        best->mentions += 1;
        best->salience = std::min(1.0, best->salience + 0.06);
        best->verified = best->verified || verified;
        return;
    }

    entries_.push_back({category, slot, text, verified, 1, clip01(salience)});
    compact();
}

void SemanticMemoryStore::compact() {
    if (entries_.size() <= kMaxEntries) return;
    std::stable_sort(entries_.begin(), entries_.end(), [](const MemoryEntry& a, const MemoryEntry& b) {
        const double ap = (a.category == "goal" || a.category == "constraint" || !a.slot.empty()) ? 2.0 : 0.0;
        const double bp = (b.category == "goal" || b.category == "constraint" || !b.slot.empty()) ? 2.0 : 0.0;
        const double as = ap + a.salience + std::min(0.8, a.mentions * 0.04);
        const double bs = bp + b.salience + std::min(0.8, b.mentions * 0.04);
        return as > bs;
    });
    entries_.resize(kMaxEntries);
}

void SemanticMemoryStore::absorb_user(const std::string& text, bool explicit_remember) {
    explicit_remember = explicit_remember || contains_any(text, {"覚えて","記憶して"});
    for (const auto& sentence : split_sentences(text)) {
        const auto category = classify_sentence(sentence, explicit_remember);
        if (!category) continue;
        double salience = 0.55;
        if (*category == "goal") salience = 0.92;
        else if (*category == "constraint") salience = 0.90;
        else if (*category == "preference") salience = 0.82;
        else if (*category == "fact") salience = 0.75;
        upsert(*category, sentence, true, salience);
    }
}

void SemanticMemoryStore::add_verified_experience(const std::string& text, double salience) {
    upsert("experience", text, true, salience);
}

std::vector<MemoryEntry> SemanticMemoryStore::recall(
    const std::string& query,
    std::size_t limit) const {
    struct Ranked {
        double score{};
        MemoryEntry entry;
    };
    std::vector<Ranked> ranked;
    ranked.reserve(entries_.size());
    for (const auto& e : entries_) {
        const double s = similarity(query, e.text);
        const double score = s + 0.15 * e.salience + std::min(0.10, e.mentions * 0.01);
        if (s > 0.0) ranked.push_back({score, e});
    }
    std::stable_sort(ranked.begin(), ranked.end(), [](const Ranked& a, const Ranked& b) {
        return a.score > b.score;
    });
    std::vector<MemoryEntry> out;
    for (std::size_t i = 0; i < ranked.size() && i < limit; ++i) out.push_back(ranked[i].entry);
    return out;
}

NativeOrchestrator::NativeOrchestrator(std::filesystem::path root) {
    if (!root.empty()) router_.load_from_root(root);
}

NativeDecision NativeOrchestrator::analyze(
    const std::string& text,
    const std::vector<Signal>& signals,
    double uncertainty,
    bool disagreement,
    bool counterexample,
    double confidence) const {
    NativeDecision out;
    out.budget = adaptive_budget(signals, uncertainty, disagreement);
    out.extra_path = needs_extra_path(confidence, disagreement, counterexample);
    out.intents = planner_.detect(text);
    out.semantic_route = router_.match(text);
    return out;
}

}  // namespace fap::cppcore
