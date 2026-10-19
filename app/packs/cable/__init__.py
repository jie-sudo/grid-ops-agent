"""电缆技能包。"""
from app.packs.base import BaseSkillPack


class CablePack(BaseSkillPack):
    key = "cable"
    device_type = "电缆"
