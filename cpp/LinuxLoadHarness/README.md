# LinuxLoadHarness

Senior-oriented hi-load demo (thread pool, backpressure, token bucket, circuit breaker, p95/p99).
Build:
  cmake -S . -B build
  cmake --build build --config Release
Run example:
  LinuxLoadHarness --requests 20000 --concurrency 16 --rps 20000 --errorRate 0.02

