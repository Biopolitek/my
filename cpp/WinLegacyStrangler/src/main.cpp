#include <atomic>
#include <algorithm>
#include <chrono>
#include <condition_variable>
#include <cstdint>
#include <cstdio>
#include <deque>
#include <functional>
#include <iostream>
#include <mutex>
#include <random>
#include <string>
#include <thread>
#include <vector>

#ifndef PROJECT_NAME
#define PROJECT_NAME "WinLegacyStrangler"
#endif

#ifndef PROJECT_VARIANT
#define PROJECT_VARIANT 2
#endif

namespace {
using Clock = std::chrono::steady_clock;

struct Config {
    uint64_t requests = 20000;
    uint32_t concurrency = 16;
    double errorRate = 0.02;
    double rps = 20000.0;          // token bucket rate
    uint32_t cbFailureThreshold = 50;
    uint32_t cbCoolDownMs = 500;
    double trafficToNew = 0.30;    // variant 2: legacy strangler split
    uint32_t seed = 42;
};

struct Metrics {
    std::atomic<uint64_t> processed{0};
    std::atomic<uint64_t> rejectedRateLimit{0};
    std::atomic<uint64_t> rejectedCircuit{0};
    std::atomic<uint64_t> failed{0};
    std::atomic<uint64_t> succeeded{0};

    std::mutex samplesMtx;
    std::vector<uint64_t> latencyUs;

    void recordLatency(uint64_t us) {
        std::lock_guard<std::mutex> lock(samplesMtx);
        latencyUs.push_back(us);
    }
};

struct Stats {
    double meanMs = 0.0;
    double p95Ms = 0.0;
    double p99Ms = 0.0;
    uint64_t n = 0;
};

Stats computeStatsMs(std::vector<uint64_t> us) {
    Stats s;
    s.n = us.size();
    if (s.n == 0) return s;

    std::sort(us.begin(), us.end());
    uint64_t sum = 0;
    for (auto v : us) sum += v;

    double meanUs = static_cast<double>(sum) / static_cast<double>(us.size());
    s.meanMs = meanUs / 1000.0;

    auto idx95 = static_cast<size_t>(0.95 * (us.size() - 1));
    auto idx99 = static_cast<size_t>(0.99 * (us.size() - 1));
    s.p95Ms = static_cast<double>(us[idx95]) / 1000.0;
    s.p99Ms = static_cast<double>(us[idx99]) / 1000.0;
    return s;
}

template <typename T>
class BoundedQueue {
public:
    explicit BoundedQueue(size_t cap) : cap_(cap) {}

    void push(T&& v) {
        std::unique_lock<std::mutex> lk(m_);
        cvNotFull_.wait(lk, [&]{ return q_.size() < cap_; });
        q_.push_back(std::move(v));
        cvNotEmpty_.notify_one();
    }

    void waitPop(T& out) {
        std::unique_lock<std::mutex> lk(m_);
        cvNotEmpty_.wait(lk, [&]{ return done_ || !q_.empty(); });
        if (q_.empty()) return;
        out = std::move(q_.front());
        q_.pop_front();
        cvNotFull_.notify_one();
    }

    void done() {
        std::lock_guard<std::mutex> lk(m_);
        done_ = true;
        cvNotEmpty_.notify_all();
    }

private:
    std::mutex m_;
    std::condition_variable cvNotEmpty_;
    std::condition_variable cvNotFull_;
    std::deque<T> q_;
    size_t cap_ = 0;
    bool done_ = false;
};

class ThreadPool {
public:
    ThreadPool(uint32_t threads, size_t qcap) : q_(qcap) {
        for (uint32_t i = 0; i < threads; ++i) {
            workers_.emplace_back([this] { loop(); });
        }
    }

    ~ThreadPool() { stop(); }

    void submit(std::function<void()> job) {
        q_.push(std::move(job));
    }

    void stop() {
        if (stopped_.exchange(true)) return;
        q_.done();
        for (auto& t : workers_) if (t.joinable()) t.join();
    }

private:
    void loop() {
        while (true) {
            std::function<void()> job;
            q_.waitPop(job);
            if (!job) {
                if (stopped_.load()) return;
                continue;
            }
            job();
        }
    }

    BoundedQueue<std::function<void()>> q_;
    std::vector<std::thread> workers_;
    std::atomic<bool> stopped_{false};
};

class RateLimiter {
public:
    explicit RateLimiter(double rps) {
        if (rps <= 0.0) { disabled_ = true; return; }
        disabled_ = false;
        refillPerMs_ = rps / 1000.0;
        cap_ = rps;         // burst 1 second
        tokens_ = cap_;
        last_ = Clock::now();
    }

    bool allow() {
        if (disabled_) return true;
        std::lock_guard<std::mutex> lk(m_);
        auto now = Clock::now();
        double dtMs = std::chrono::duration_cast<std::chrono::microseconds>(now - last_).count() / 1000.0;
        if (dtMs > 0) {
            tokens_ = std::min(cap_, tokens_ + dtMs * refillPerMs_);
            last_ = now;
        }
        if (tokens_ >= 1.0) { tokens_ -= 1.0; return true; }
        return false;
    }

private:
    bool disabled_ = false;
    double tokens_ = 0.0;
    double cap_ = 0.0;
    double refillPerMs_ = 0.0;
    Clock::time_point last_;
    std::mutex m_;
};

enum class CBState { Closed, Open };

class CircuitBreaker {
public:
    CircuitBreaker(uint32_t thr, uint32_t cdMs) : thr_(thr), cdMs_(cdMs) {}

    bool allow() {
        std::lock_guard<std::mutex> lk(m_);
        if (state_ == CBState::Closed) return true;
        auto now = Clock::now();
        auto elapsed = std::chrono::duration_cast<std::chrono::milliseconds>(now - openedAt_).count();
        if (elapsed >= static_cast<long long>(cdMs_)) {
            state_ = CBState::Closed;
            failures_ = 0;
            return true;
        }
        return false;
    }

    void onSuccess() {
        std::lock_guard<std::mutex> lk(m_);
        failures_ = 0;
    }

    void onFailure() {
        std::lock_guard<std::mutex> lk(m_);
        if (state_ == CBState::Open) return;
        if (++failures_ >= thr_) {
            state_ = CBState::Open;
            openedAt_ = Clock::now();
        }
    }

private:
    uint32_t thr_ = 0;
    uint32_t cdMs_ = 0;
    CBState state_ = CBState::Closed;
    uint32_t failures_ = 0;
    Clock::time_point openedAt_{};
    std::mutex m_;
};

static bool isKey(const std::string& s, const std::string& k) { return s == ("--" + k) || s == k; }

template <typename T>
T arg(int argc, char** argv, const std::string& k, T def) {
    for (int i = 1; i < argc - 1; ++i) {
        if (!argv[i] || !argv[i+1]) continue;
        if (isKey(argv[i], k)) {
            try {
                if constexpr (std::is_same_v<T, double>) return std::stod(argv[i+1]);
                if constexpr (std::is_integral_v<T>) return static_cast<T>(std::stoull(argv[i+1]));
                return def;
            } catch (...) { return def; }
        }
    }
    return def;
}

Config parse(int argc, char** argv) {
    Config c;
    c.requests = arg<uint64_t>(argc, argv, "requests", c.requests);
    c.concurrency = arg<uint32_t>(argc, argv, "concurrency", c.concurrency);
    c.errorRate = arg<double>(argc, argv, "errorRate", c.errorRate);
    c.rps = arg<double>(argc, argv, "rps", c.rps);
    c.cbFailureThreshold = arg<uint32_t>(argc, argv, "cbFailures", c.cbFailureThreshold);
    c.cbCoolDownMs = arg<uint32_t>(argc, argv, "cbCoolDownMs", c.cbCoolDownMs);
    c.trafficToNew = arg<double>(argc, argv, "trafficToNew", c.trafficToNew);
    c.seed = arg<uint32_t>(argc, argv, "seed", c.seed);
    return c;
}

uint32_t workUs(std::mt19937& rng, const Config& cfg) {
    if constexpr (PROJECT_VARIANT == 1) {
        std::uniform_real_distribution<double> p(0.0, 1.0);
        if (p(rng) < 0.01) return 20000;
        std::uniform_int_distribution<uint32_t> d(200, 800);
        return d(rng);
    } else if constexpr (PROJECT_VARIANT == 2) {
        std::uniform_real_distribution<double> p(0.0, 1.0);
        bool useNew = p(rng) < cfg.trafficToNew;
        if (useNew) {
            std::uniform_int_distribution<uint32_t> d(150, 600);
            return d(rng);
        } else {
            std::uniform_int_distribution<uint32_t> d(800, 2500);
            return d(rng);
        }
    } else if constexpr (PROJECT_VARIANT == 3) {
        std::uniform_real_distribution<double> p(0.0, 1.0);
        if (p(rng) < 0.001) return 12000;
        std::uniform_int_distribution<uint32_t> d(100, 450);
        return d(rng);
    } else {
        std::uniform_real_distribution<double> p(0.0, 1.0);
        if (p(rng) < 0.005) return 18000;
        std::uniform_int_distribution<uint32_t> d(200, 900);
        return d(rng);
    }
}

bool fail(std::mt19937& rng, const Config& cfg) {
    std::uniform_real_distribution<double> p(0.0, 1.0);
    return p(rng) < cfg.errorRate;
}

} // namespace

int main(int argc, char** argv) {
    Config cfg = parse(argc, argv);
    std::mt19937 rng(cfg.seed);

    std::cout << "== " << PROJECT_NAME << " ==" << std::endl;
    std::cout << "requests=" << cfg.requests
              << " concurrency=" << cfg.concurrency
              << " errorRate=" << cfg.errorRate
              << " rps=" << cfg.rps
              << " seed=" << cfg.seed << std::endl;

    RateLimiter rl(cfg.rps);
    CircuitBreaker cb(cfg.cbFailureThreshold, cfg.cbCoolDownMs);

    Metrics m;
    size_t qcap = static_cast<size_t>(cfg.concurrency) * 64;
    ThreadPool pool(cfg.concurrency, qcap);

    auto t0 = Clock::now();

    for (uint64_t i = 0; i < cfg.requests; ++i) {
        pool.submit([&]{
            auto start = Clock::now();

            if (!rl.allow()) { m.rejectedRateLimit.fetch_add(1); return; }
            if (!cb.allow()) { m.rejectedCircuit.fetch_add(1); return; }

            uint32_t us = workUs(rng, cfg);
            std::this_thread::sleep_for(std::chrono::microseconds(us));

            if (fail(rng, cfg)) { m.failed.fetch_add(1); cb.onFailure(); }
            else { m.succeeded.fetch_add(1); cb.onSuccess(); }

            m.processed.fetch_add(1);

            auto end = Clock::now();
            auto durUs = std::chrono::duration_cast<std::chrono::microseconds>(end - start).count();
            m.recordLatency(static_cast<uint64_t>(durUs));
        });
    }

    pool.stop();

    auto t1 = Clock::now();
    double sec = std::chrono::duration_cast<std::chrono::milliseconds>(t1 - t0).count() / 1000.0;
    double throughput = (sec > 0.0) ? static_cast<double>(m.processed.load()) / sec : 0.0;

    std::vector<uint64_t> samples;
    { std::lock_guard<std::mutex> lk(m.samplesMtx); samples = m.latencyUs; }
    Stats s = computeStatsMs(std::move(samples));

    std::cout << "throughput_rps=" << throughput << std::endl;
    std::cout << "latency_ms mean=" << s.meanMs << " p95=" << s.p95Ms << " p99=" << s.p99Ms << std::endl;
    std::cout << "processed=" << m.processed.load()
              << " ok=" << m.succeeded.load()
              << " failed=" << m.failed.load()
              << " rejRateLimit=" << m.rejectedRateLimit.load()
              << " rejCircuit=" << m.rejectedCircuit.load() << std::endl;

    if constexpr (PROJECT_VARIANT == 6) {
        double sloP99Ms = 30.0;
        bool breached = s.p99Ms > sloP99Ms;
        double costPerMinute = 1000.0;
        double minutes = breached ? (s.p99Ms - sloP99Ms) / sloP99Ms : 0.0;
        double cost = minutes * costPerMinute;

        std::FILE* f = std::fopen("metrics.prom", "w");
        if (f) {
            std::fprintf(f, "app_processed_total %llu\n", (unsigned long long)m.processed.load());
            std::fprintf(f, "app_latency_p95_ms %f\n", s.p95Ms);
            std::fprintf(f, "app_latency_p99_ms %f\n", s.p99Ms);
            std::fprintf(f, "business_slo_breach_cost_usd %f\n", cost);
            std::fclose(f);
            std::cout << "metrics.prom written" << std::endl;
        }
    }

    return 0;
}
