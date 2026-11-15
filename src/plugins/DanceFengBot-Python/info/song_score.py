"""单曲成绩文本格式化。

按歌曲 id 汇总个人各难度成绩，输出纯文本即可（无需生成图片）。
对应参考实现 ``/dc song [id]`` 的文字版。
"""

from __future__ import annotations

from ..ratio.acc_grade import AccGrade
from ..ratio.rank_music import RankMusicInfo

# 难度类型（MusicLev）→ 展示名称
LEVEL_TYPE_NAMES: dict[int, str] = {
    11: "经典·基础",
    12: "经典·进阶",
    13: "经典·专家",
    14: "经典·大师",
    15: "经典·传奇",
    101: "show+·基础",
    102: "show+·进阶",
    103: "show+·专家",
    104: "show+·大师",
    105: "show+·传奇",
}

GRADE_NAMES: dict[AccGrade, str] = {
    AccGrade.SSS_AP: "SSS+",
    AccGrade.SSS: "SSS",
    AccGrade.SS: "SS",
    AccGrade.S: "S",
    AccGrade.A: "A",
    AccGrade.B: "B",
    AccGrade.C: "C",
    AccGrade.D: "D",
}


def level_type_name(level_type: int) -> str:
    """把 ``MusicLev`` 转成可读难度名，未知类型原样标注。"""
    return LEVEL_TYPE_NAMES.get(int(level_type), f"类型{level_type}")


def grade_name(grade: AccGrade) -> str:
    """把准确率评级转成展示文本（AP 记为 SSS+）。"""
    return GRADE_NAMES.get(grade, grade.name)


def format_song_score(song_id: int, records: list[RankMusicInfo]) -> str:
    """把同一首歌的各难度成绩格式化为文本。"""
    if not records:
        return f"没有找到 id:{song_id} 的游玩记录，请检查歌曲 id 是否正确。"

    name = next((record.name for record in records if record.name), "未知曲目")
    lines = [f"🎵 {name}（id:{song_id}）", ""]
    for record in sorted(records, key=lambda item: item.level_type):
        lines.append(f"【{level_type_name(record.level_type)}】Lv.{record.level}")
        lines.append(
            f"准确率：{record.accuracy:.2f}%  {grade_name(record.acc_grade)}"
        )
        statistics = (
            f"分数：{record.score:,}  战力：{record.ratio_int}"
            f"  Combo：{record.combo}  Miss：{record.miss}"
        )
        if record.ranking > 0:
            statistics += f"  排名：#{record.ranking}"
        lines.append(statistics)
        lines.append("")
    return "\n".join(lines).rstrip()
