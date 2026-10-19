"""初始化默认用户（四角色）。用法：python scripts/init_users.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core import auth
from app.data import models
from app.data.database import get_write_session

USERS = [
    ("U0001", "admin", "admin", "admin123"),
    ("U0002", "operator", "operator", "operator123"),
    ("U0003", "monitor", "monitor", "monitor123"),
    ("U0004", "manager", "manager", "manager123"),
]


def main() -> None:
    with get_write_session() as s:
        for uid, username, role, pwd in USERS:
            if s.get(models.AppUser, uid):
                print(f"跳过（已存在）：{username}")
                continue
            s.add(models.AppUser(
                user_id=uid, username=username, role=role, password_hash=auth.hash_password(pwd)
            ))
        s.commit()
    print("用户初始化完成：admin/admin123, operator/operator123, monitor/monitor123, manager/manager123")


if __name__ == "__main__":
    main()
