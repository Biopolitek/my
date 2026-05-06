#pragma once
#include <cstdint>

#ifdef _WIN32
  #ifdef ANALYTICS_C_EXPORTS
    #define ANALYTICS_C_API __declspec(dllexport)
  #else
    #define ANALYTICS_C_API __declspec(dllimport)
  #endif
#else
  #define ANALYTICS_C_API
#endif

extern "C" {

struct StatsU {
    double mean;
    double p95;
    double p99;
};

ANALYTICS_C_API StatsU compute_latency_stats_u32(const uint32_t* samples, uint64_t n);

}
