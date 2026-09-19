"""
GIAI ĐOẠN 4: RESOURCE PROFILER (ĐO LƯỜNG TÀI NGUYÊN BỘ NHỚ & TỐC ĐỘ XỬ LÝ)
Đồ án Tốt nghiệp - Trường Đại học Giao thông vận tải TP.HCM (UTH)
Hệ thống: Quant AI V2.2 - Tối ưu hóa cho cấu hình máy tính 8GB RAM
"""

import time
import tracemalloc
from functools import wraps
from typing import Callable, Any, Tuple


def performance_monitor(func: Callable) -> Callable:
    """
    Decorator giám sát hiệu năng phần cứng:
    - Đo đạc thời gian thực thi chính xác (ms) qua time.perf_counter.
    - Bắt đỉnh tiêu thụ bộ nhớ RAM (Peak Memory in MB) qua tracemalloc.
    """

    @wraps(func)
    def wrapper(*args, **kwargs) -> Any:
        tracemalloc.start()
        start_time = time.perf_counter()

        result = func(*args, **kwargs)

        end_time = time.perf_counter()
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        exec_ms = (end_time - start_time) * 1000.0
        peak_mb = peak / 10**6
        current_mb = current / 10**6

        # Gắn kèm thông tin giám sát vào đối tượng trả về nếu là dict
        if isinstance(result, dict):
            result["_perf_exec_ms"] = round(exec_ms, 2)
            result["_perf_peak_ram_mb"] = round(peak_mb, 4)
            result["_perf_curr_ram_mb"] = round(current_mb, 4)

        return result

    return wrapper


def profile_callable(func: Callable, *args, **kwargs) -> Tuple[Any, float, float]:
    """Hàm phụ trợ đo đạc nhanh một hàm cụ thể trả về: (result, exec_ms, peak_mb)."""
    tracemalloc.start()
    start = time.perf_counter()

    res = func(*args, **kwargs)

    end = time.perf_counter()
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    return res, (end - start) * 1000.0, peak / 10**6
