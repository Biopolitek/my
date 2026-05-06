import ctypes
import os
import platform
from ctypes import c_uint32, c_uint64, c_double, POINTER, Structure

class StatsU(Structure):
    _fields_ = [("mean", c_double), ("p95", c_double), ("p99", c_double)]

def find_lib():
    p = os.environ.get("ANALYTICS_C_LIB")
    if p and os.path.exists(p):
        return p

    sys = platform.system().lower()
    if "windows" in sys:
        candidates = ["build\\Release\\analytics_c.dll", "build\\Debug\\analytics_c.dll"]
    else:
        candidates = ["build/analytics_c.so", "build/libanalytics_c.so"]

    for c in candidates:
        if os.path.exists(c):
            return c
    return None

def main():
    lib_path = find_lib()
    if not lib_path:
        raise RuntimeError("Cannot find analytics_c library. Build it and/or set ANALYTICS_C_LIB.")

    lib = ctypes.CDLL(lib_path)
    lib.compute_latency_stats_u32.argtypes = [POINTER(c_uint32), c_uint64]
    lib.compute_latency_stats_u32.restype = StatsU

    samples = [100, 120, 130, 140, 150, 200, 250, 300, 500, 900]
    n = len(samples)
    arr = (c_uint32 * n)(*samples)

    s = lib.compute_latency_stats_u32(arr, n)
    print(f"mean={s.mean:.2f}us p95={s.p95:.2f}us p99={s.p99:.2f}us")

if __name__ == "__main__":
    main()
