#include "fap/native_core.hpp"

#include <cstdlib>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>

using namespace fap::cppcore;

namespace {

std::string json_escape(const std::string& value) {
    std::string out;
    for (char c : value) {
        if (c == '\\' || c == '"') out.push_back('\\');
        if (c == '\n') { out += "\\n"; continue; }
        out.push_back(c);
    }
    return out;
}

std::string join_args(int argc, char** argv, int start) {
    std::ostringstream out;
    for (int i = start; i < argc; ++i) {
        if (i != start) out << ' ';
        out << argv[i];
    }
    return out.str();
}

void usage() {
    std::cout
        << "FAP native " << kVersion << "\n"
        << "usage:\n"
        << "  fap_native_cli version\n"
        << "  fap_native_cli budget [uncertainty] [disagreement]\n"
        << "  fap_native_cli route <repo-root> <text...>\n"
        << "  fap_native_cli analyze <repo-root> <text...>\n";
}

}  // namespace

int main(int argc, char** argv) {
    if (argc < 2) {
        usage();
        return 0;
    }

    const std::string cmd = argv[1];
    if (cmd == "version") {
        std::cout << kVersion << "\n";
        return 0;
    }

    if (cmd == "budget") {
        const double uncertainty = argc >= 3 ? std::atof(argv[2]) : 0.0;
        const bool disagreement = argc >= 4 ? std::atoi(argv[3]) != 0 : false;
        const auto b = adaptive_budget({}, uncertainty, disagreement);
        std::cout
            << "{\"routes\":" << b.routes
            << ",\"steps\":" << b.steps
            << ",\"verify\":" << b.verify
            << ",\"retries\":" << b.retries << "}\n";
        return 0;
    }

    if ((cmd == "route" || cmd == "analyze") && argc >= 4) {
        const std::string root = argv[2];
        const std::string text = join_args(argc, argv, 3);
        NativeOrchestrator fap(root);

        if (cmd == "route") {
            const auto match = fap.router().match(text);
            if (!match) {
                std::cout << "null\n";
                return 0;
            }
            std::cout
                << "{\"rule_id\":\"" << json_escape(match->rule_id)
                << "\",\"resource_id\":\"" << json_escape(match->resource_id)
                << "\",\"action_id\":\"" << json_escape(match->action_id)
                << "\",\"route\":\"" << json_escape(match->route)
                << "\",\"score\":" << match->score << "}\n";
            return 0;
        }

        const auto decision = fap.analyze(text);
        std::cout
            << "{\"version\":\"" << kVersion
            << "\",\"budget\":{\"routes\":" << decision.budget.routes
            << ",\"steps\":" << decision.budget.steps
            << ",\"verify\":" << decision.budget.verify
            << ",\"retries\":" << decision.budget.retries << "}"
            << ",\"extra_path\":" << (decision.extra_path ? "true" : "false")
            << ",\"multi_intents\":" << decision.intents.size();
        if (decision.semantic_route) {
            std::cout << ",\"route\":\"" << json_escape(decision.semantic_route->route) << "\"";
        } else {
            std::cout << ",\"route\":null";
        }
        std::cout << "}\n";
        return 0;
    }

    usage();
    return 2;
}
