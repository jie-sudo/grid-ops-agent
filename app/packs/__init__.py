"""技能包注册表：按 device_type 加载对应技能包（FR-050）。"""
from __future__ import annotations

from app.packs.base import BaseSkillPack
from app.packs.switchgear import SwitchgearPack
from app.packs.transformer import TransformerPack
from app.packs.cable import CablePack

_PACK_CLASSES = [SwitchgearPack, TransformerPack, CablePack]

# 按设备类型实例化（懒加载，首次访问时读阈值 YAML）
PACKS: dict[str, BaseSkillPack] = {}


def get_pack(device_type: str) -> BaseSkillPack | None:
    if device_type not in PACKS:
        for cls in _PACK_CLASSES:
            if cls.device_type == device_type:
                PACKS[device_type] = cls()
                break
    return PACKS.get(device_type)


def available_device_types() -> list[str]:
    return [cls.device_type for cls in _PACK_CLASSES]
