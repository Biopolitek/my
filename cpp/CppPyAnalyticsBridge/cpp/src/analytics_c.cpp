#include "analytics_c.h"
#include <algorithm>
#include <vector>

extern "C" {

StatsU compute_latency_stats_u32(const uint32_t* samples, uint64_t n) {
    StatsU out{0.0, 0.0, 0.0};
    if (!samples || n == 0) return out;

    std::vector<uint32_t> sorted(samples, samples + n);
    std::sort(sorted.begin(), sorted.end());

    double sum = 0.0;
    for (auto v : sorted) sum += static_cast<double>(v);
    out.mean = sum / static_cast<double>(n);

    auto idx95 = static_cast<size_t>(0.95 * (n - 1));
    auto idx99 = static_cast<size_t>(0.99 * (n - 1));
    out.p95 = static_cast<double>(sorted[idx95]);
    out.p99 = static_cast<double>(sorted[idx99]);
    return out;
}

}
