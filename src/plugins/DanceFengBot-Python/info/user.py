"""用户信息，对应 Java 端 ``com.DanceCube.info.UserInfo``。"""

from __future__ import annotations

from ..token import Token
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
        )
        if resp is None:
            return UserInfo.get_null()
        return _parse_user_info(resp.text)

    @staticmethod
    def get_by_id(token: Token, id: int) -> "UserInfo":
        resp = http_get(
            f"{_BASE}/api/User/GetInfo?userId={id}",
            headers={"Authorization": token.bearer_token},
        )
        text = resp.text if resp is not None else ""
        status = _status_of(text)

        user_info = UserInfo.get_null()

        if status == InfoStatus.PRIVATE:
            search = http_get(
                f"{_BASE}/api/Common/Search?keyword={id}&type=0&page=1&pagesize=1",
                headers={"Authorization": token.bearer_token},
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
                except Exception:
                    pass
            user_info.status = InfoStatus.PRIVATE
            return user_info

        if status == InfoStatus.NONEXISTENT:
            user_info = UserInfo()
            user_info.status = InfoStatus.NONEXISTENT
            return user_info

        return _parse_user_info(text)


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
    except Exception:
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
