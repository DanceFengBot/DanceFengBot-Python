"""用户信息，对应 Java 端 ``com.DanceCube.info.UserInfo``。"""

from __future__ import annotations

from ..token import Token
from ..utils import logger
from ..utils.http import http_get
from .status import InfoStatus

_BASE = "https://dancedemo.shenghuayule.com/Dance"


class UserInfo:
    def __init__(self) -> None:
        self.user_id = 0
        self.music_score = 0
        self.lv_ratio = 0
        self.rank_nation = 0
        self.combo_percent = 0
        self.sex = 0
        self.user_name = ""
        self.headimg_url = ""
        self.phone = ""
        self.city_name = ""
        self.team_name = ""
        self.title_url = ""
        self.headimg_box_path = ""
        self.status = InfoStatus.OPEN

    @property
    def team_name_or_none(self) -> str:
        return self.team_name or ""

    @property
    def title_url_clean(self) -> str:
        if not self.title_url or len(self.title_url) < 5:
            return ""
        suffix = "/256"
        if self.title_url.endswith(suffix):
            return self.title_url[: -len(suffix)]
        return self.title_url

    @property
    def headimg_box_path_or_none(self) -> str:
        return self.headimg_box_path or ""

    @staticmethod
    def get_null() -> "UserInfo":
        u = UserInfo()
        u.user_id = -1
        u.status = InfoStatus.NONEXISTENT
        return u

    @staticmethod
    def get(token: Token) -> "UserInfo":
        resp = http_get(
            f"{_BASE}/api/User/GetInfo?userId={token.user_id}",
            headers={"Authorization": token.bearer_token},
            context="个人信息",
        )
        if resp is None:
            logger.error(f"[个人信息] 请求失败：userId={token.user_id}")
            return UserInfo.get_null()
        info = _parse_user_info(resp.text)
        logger.debug(
            f"[个人信息] userId={info.user_id} 名称={info.user_name or '-'} "
            f"战力={info.lv_ratio} 状态={info.status.value}"
        )
        return info

    @staticmethod
    def get_by_id(token: Token, id: int) -> "UserInfo":
        logger.debug(f"[个人信息] 查询目标账号：id={id}")
        resp = http_get(
            f"{_BASE}/api/User/GetInfo?userId={id}",
            headers={"Authorization": token.bearer_token},
            context="个人信息-按ID查询",
        )
        text = resp.text if resp is not None else ""
        status = _status_of(text)
        logger.debug(f"[个人信息] id={id} 可见状态={status.value}")

        user_info = UserInfo.get_null()

        if status == InfoStatus.PRIVATE:
            logger.info(f"[个人信息] id={id} 已设置保密，改用搜索接口取基础信息")
            search = http_get(
                f"{_BASE}/api/Common/Search?keyword={id}&type=0&page=1&pagesize=1",
                headers={"Authorization": token.bearer_token},
                context="个人信息-搜索接口",
            )
            if search is not None:
                try:
                    lst = search.json().get("List", [])
                    if lst:
                        o = lst[0]
                        user_info.user_id = id
                        user_info.user_name = o.get("Name", "")
                        user_info.headimg_url = o.get("HeadimgURL", "")
                        user_info.lv_ratio = o.get("LvRatio", 0)
                        user_info.city_name = o.get("Region", "")
                        logger.debug(
                            f"[个人信息] 搜索命中：名称={user_info.user_name} "
                            f"战力={user_info.lv_ratio}"
                        )
                    else:
                        logger.warning(f"[个人信息] 搜索接口未命中 id={id}")
                except Exception as exc:  # noqa: BLE001
                    logger.error(
                        f"[个人信息] 搜索接口响应解析失败：{exc}；"
                        f"内容（前 200 字符）：{search.text[:200]}"
                    )
            else:
                logger.error(f"[个人信息] 搜索接口请求失败：id={id}")
            user_info.status = InfoStatus.PRIVATE
            return user_info

        if status == InfoStatus.NONEXISTENT:
            logger.warning(f"[个人信息] 账号不存在：id={id}")
            user_info = UserInfo()
            user_info.status = InfoStatus.NONEXISTENT
            return user_info

        parsed = _parse_user_info(text)
        logger.debug(
            f"[个人信息] id={id} 查询成功：名称={parsed.user_name or '-'} "
            f"战力={parsed.lv_ratio}"
        )
        return parsed


def _status_of(message: str) -> InfoStatus:
    if "账号不存在" in message:
        return InfoStatus.NONEXISTENT
    if "已设置保密" in message:
        return InfoStatus.PRIVATE
    return InfoStatus.OPEN


def _parse_user_info(text: str) -> UserInfo:
    import json

    u = UserInfo()
    try:
        data = json.loads(text)
    except Exception as exc:  # noqa: BLE001
        logger.error(
            f"[个人信息] 响应不是合法 JSON：{exc}；内容（前 200 字符）：{text[:200]}"
        )
        return UserInfo.get_null()
    u.user_id = data.get("UserID", 0)
    u.music_score = data.get("MusicScore", 0)
    u.lv_ratio = data.get("LvRatio", 0)
    u.rank_nation = data.get("RankNation", 0)
    u.combo_percent = data.get("ComboPercent", 0)
    u.sex = data.get("Sex", 0)
    u.user_name = data.get("UserName", "")
    u.headimg_url = data.get("HeadimgURL", "")
    u.phone = data.get("Phone", "")
    u.city_name = data.get("CityName", "")
    u.team_name = data.get("TeamName", "") or ""
    u.title_url = data.get("TitleUrl", "") or ""
    u.headimg_box_path = data.get("HeadimgBoxPath", "") or ""
    u.status = InfoStatus.OPEN
    return u
