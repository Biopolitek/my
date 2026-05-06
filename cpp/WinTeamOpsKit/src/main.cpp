#include <filesystem>
#include <iostream>
#include <string>
#include <vector>

namespace {
bool exists(const std::string& p) { return std::filesystem::exists(std::filesystem::path(p)); }

int main() {
    std::vector<std::string> must = {
        "docs/runbook.md",
        "docs/release_checklist.md",
        "docs/onboarding_guide.md"
    };

    std::vector<std::string> errors;
    for (const auto& f : must) if (!exists(f)) errors.push_back("Missing: " + f);

    bool hasAdr = false;
    if (std::filesystem::exists("docs/adr")) {
        for (auto& e : std::filesystem::directory_iterator("docs/adr")) {
            if (e.is_regular_file() && e.path().extension() == ".md") { hasAdr = true; break; }
        }
    }
    if (!hasAdr) errors.push_back("Missing: at least one docs/adr/*.md");

    std::cout << "== WinTeamOpsKit validator ==" << std::endl;
    if (!errors.empty()) {
        for (auto& e : errors) std::cout << " - " << e << std::endl;
        return 1;
    }
    std::cout << "OK: artifacts present" << std::endl;
    return 0;
}
