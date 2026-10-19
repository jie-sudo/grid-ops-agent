"""并发测试：鉴权 / RBAC / 多用户会话隔离 / 并发性能。

用法（需服务已启动 + 已 init_users）：
    python eval/concurrency_test.py
"""
from __future__ import annotations

import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx

BASE = "http://localhost:8000/api/v1"


def login(username: str, password: str) -> str:
    r = httpx.post(f"{BASE}/auth/login", json={"username": username, "password": password})
    r.raise_for_status()
    return r.json()["data"]["token"]


def ask(token: str, message: str, session_id: str | None = None):
    body: dict = {"message": message}
    if session_id:
        body["session_id"] = session_id
    r = httpx.post(f"{BASE}/chat", json=body, headers={"Authorization": f"Bearer {token}"})
    return r.status_code, r.json()


def test_unauthorized() -> int:
    r = httpx.post(f"{BASE}/chat", json={"message": "你好"})
    return r.status_code  # 应 401


def test_rbac() -> int:
    token = login("operator", "operator123")
    r = httpx.get(f"{BASE}/traces/xxx", headers={"Authorization": f"Bearer {token}"})
    return r.status_code  # 应 403


def test_concurrent_isolation() -> tuple[bool, list[float], list[str]]:
    token = login("operator", "operator123")

    def worker(i: int):
        t0 = time.time()
        msg = f"查询设备 DEV{i:06d} 的台账" if i <= 5 else "你好"
        status, data = ask(token, msg)
        sid = (data.get("data") or {}).get("session_id")
        return status, time.time() - t0, sid

    with ThreadPoolExecutor(max_workers=10) as ex:
        results = list(ex.map(worker, range(1, 11)))

    sids = [r[2] for r in results]
    times = [r[1] for r in results]
    all_200 = all(r[0] == 200 for r in results)
    isolated = len(set(sids)) == len(sids) and all(sids)  # 每个会话 id 唯一且非空
    return all_200 and isolated, times, sids


def main() -> None:
    print("1. 未登录访问 /chat（期望 401）：", test_unauthorized())
    print("2. operator 访问 /traces（期望 403）：", test_rbac())

    print("3. 并发 10 个独立会话 ...")
    ok, times, _ = test_concurrent_isolation()
    print(f"   会话隔离 + 全部 200：{'✓' if ok else '✗'}")
    print(f"   耗时：最小 {min(times):.2f}s / 最大 {max(times):.2f}s / 平均 {sum(times) / len(times):.2f}s")


if __name__ == "__main__":
    main()
