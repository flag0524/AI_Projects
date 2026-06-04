"""
실행 PC(노트북) 사양 자동 감지.

백엔드 시작 시 GPU/CUDA · CPU 코어 · RAM 을 살펴
  - 권장 엔진 티어 (1=IDM-VTON, 2=SD1.5, 3=CV 워핑)
  - 처리 해상도 (높을수록 외곽이 정밀 → 자연스러운 핏, 단 느림)
를 자동 결정한다. 모든 감지는 실패해도 안전하게 폴백한다.
"""
from __future__ import annotations
import os
from functools import lru_cache
from loguru import logger


def _ram_gb() -> float | None:
    """설치 패키지 없이 총 RAM(GB)을 추정. 실패 시 None."""
    try:
        if os.name == "nt":
            import ctypes

            class _MemStatus(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            ms = _MemStatus()
            ms.dwLength = ctypes.sizeof(_MemStatus)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(ms))
            return round(ms.ullTotalPhys / 1024 ** 3, 1)
        else:
            return round(os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 1024 ** 3, 1)
    except Exception:
        return None


def _recommend_tier(info: dict) -> int:
    if info["cuda"] and info["vram_gb"] >= 8:
        return 1
    if info["cuda"] and info["vram_gb"] >= 2:
        return 2
    return 3


def _recommend_size(info: dict) -> tuple[int, int]:
    """(가로, 세로) 처리 해상도 — 사양이 높을수록 크게."""
    if info["cuda"]:
        return (1024, 1365)
    cores = info["cpu_cores"]
    ram = info["ram_gb"] or 8.0
    # 고사양 CPU(8스레드+/16GB+)는 기하 합성이 가벼우므로 최고 해상도로 처리
    if cores >= 8 and ram >= 16:
        return (1024, 1365)
    if cores >= 4 and ram >= 8:
        return (832, 1110)
    return (640, 854)


@lru_cache(maxsize=1)
def detect_hardware() -> dict:
    """현재 PC 사양을 감지해 권장 설정과 함께 반환 (최초 1회만 계산)."""
    info = {
        "cuda": False,
        "gpu_name": None,
        "vram_gb": 0.0,
        "cpu_cores": os.cpu_count() or 1,
        "ram_gb": _ram_gb(),
    }
    try:
        import torch
        if torch.cuda.is_available():
            p = torch.cuda.get_device_properties(0)
            info["cuda"] = True
            info["gpu_name"] = p.name
            info["vram_gb"] = round(p.total_memory / 1024 ** 3, 1)
    except Exception:
        pass

    info["recommended_tier"] = _recommend_tier(info)
    info["process_size"] = _recommend_size(info)
    return info


def log_summary() -> dict:
    h = detect_hardware()
    logger.info(
        "하드웨어 감지: CPU {c}코어 / RAM {r}GB / GPU {g} (VRAM {v}GB) "
        "→ 권장 Tier {t}, 처리해상도 {w}x{hh}".format(
            c=h["cpu_cores"], r=h["ram_gb"], g=h["gpu_name"] or "없음",
            v=h["vram_gb"], t=h["recommended_tier"],
            w=h["process_size"][0], hh=h["process_size"][1],
        )
    )
    return h
