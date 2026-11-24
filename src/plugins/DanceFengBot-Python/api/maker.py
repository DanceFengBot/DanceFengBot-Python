"""创作者（谱师）相关接口。

对应 DcNana 的「创作者」功能：

* ``GetMakerInfo``：创作者信息（等级、创作金币）；
* ``GetMyPublishMusic``：已发布的自制谱列表；
* ``GetMusicCode``：为自制谱生成兑换码（每次调用返回一个）。
"""

from __future__ import annotations

from ..token import Token
from ..utils import logger
from ..utils.http import http_get

_BASE = "https://dancedemo.shenghuayule.com/Dance"

# 已发布作品列表默认分页大小（与服务端默认一致）
_PAGE_SIZE = 15


class MakerInfo:
    """创作者信息。"""

    def __init__(self) -> None:
        self.user_id = 0
        self.user_name = ""
        self.headimg_url = ""
        self.maker_grade = 0
        self.maker_exp = 0
        self.auth_status = 0
        self.total_profit = 0
        self.balance_profit = 0
        self.price_limit = 0
        self.share_times_limit = 0

    @property
    def is_creator(self) -> bool:
        """当前账号是否已开通创作者功能。

        接口对普通账号也会返回数据（实测普通账号 ``MakerGrade=1``、
        ``AuthStatus=0``、收益为 0），因此不能只看接口是否成功：

        * ``AuthStatus``：创作者实名认证状态，0 表示未认证/未开通；
        * ``MakerGrade``：创作等级，普通账号实测为 1，已开通创作者会更高；
        * ``TotalProfit``：历史创作收益，大于 0 说明开通过创作者。
        """
        return (
            self.auth_status != 0
            or self.maker_grade > 1
            or self.total_profit > 0
        )

    @staticmethod
    def get(token: Token) -> "MakerInfo | None":
        """获取当前账号的创作者信息。

        非创作者（接口返回 400/403）时返回一个空对象（``is_creator`` 为假）；
        网络或解析失败返回 ``None``。
        """
        resp = http_get(
            f"{_BASE}/api/User/GetMakerInfo?getProfit=true",
            headers={"Authorization": token.bearer_token},
            context="创作者信息",
        )
        if resp is None:
            logger.error(f"[创作者] 信息请求失败：userId={token.user_id}")
            return None
        if resp.status_code in (400, 403):
            logger.info(
                f"[创作者] userId={token.user_id} 不是创作者"
                f"（状态码 {resp.status_code}）"
            )
            return MakerInfo()
        if resp.status_code != 200:
            logger.error(
                f"[创作者] 信息请求状态码 {resp.status_code}：{resp.text[:200]}"
            )
            return None

        try:
            data = resp.json()
        except Exception as exc:  # noqa: BLE001
            logger.error(
                f"[创作者] 信息解析失败：{exc}；内容（前 200 字符）：{resp.text[:200]}"
            )
            return None
        if not isinstance(data, dict):
            logger.error(f"[创作者] 信息格式异常：{resp.text[:200]}")
            return None

        info = MakerInfo()
        info.user_id = _to_int(data.get("UserID"))
        info.user_name = str(data.get("UserName") or "")
        info.headimg_url = str(data.get("HeadimgURL") or "")
        info.maker_grade = _to_int(data.get("MakerGrade"))
        info.maker_exp = _to_int(data.get("MakerExp"))
        info.auth_status = _to_int(data.get("AuthStatus"))
        info.total_profit = _to_int(data.get("TotalProfit"))
        info.balance_profit = _to_int(data.get("BalaceProfit"))
        info.price_limit = _to_int(data.get("PriceLimit"))
        info.share_times_limit = _to_int(data.get("ShareTimesLimit"))
        logger.debug(
            f"[创作者] userId={info.user_id} 名称={info.user_name or '-'} "
            f"等级={info.maker_grade} 经验={info.maker_exp} "
            f"认证={info.auth_status} 创作金币={info.total_profit} "
            f"是否创作者={info.is_creator}"
        )
        return info


class PublishedMusic:
    """创作者已发布的一首自制谱。"""

    def __init__(self, data: dict) -> None:
        self.music_id = _to_int(data.get("MusicID"))
        self.name = str(data.get("Name") or "")
        self.intro = str(data.get("GoodsIntro") or "")
        self.cover_url = str(data.get("PicPath") or "")
        self.price_sale = _to_int(data.get("PriceSale"))
        self.clicks_ratio = str(data.get("ClicksRatio") or "")
        tags = data.get("TagList") or []
        self.tags = [str(tag) for tag in tags if tag]

    @staticmethod
    def get_page(
        token: Token, page: int = 1, pagesize: int = _PAGE_SIZE
    ) -> tuple[list["PublishedMusic"], int] | None:
        """获取一页已发布作品，返回 ``(作品列表, 总数)``。

        非创作者 / 无权限时返回 ``([], 0)``；网络或解析失败返回 ``None``。
        """
        resp = http_get(
            f"{_BASE}/api/MusicData/GetMyPublishMusic?page={page}&pagesize={pagesize}",
            headers={"Authorization": token.bearer_token},
            context=f"我的自制谱(page={page})",
        )
        if resp is None:
            logger.error(f"[创作者] 作品列表请求失败：page={page}")
            return None
        if resp.status_code in (400, 403):
            logger.info(
                f"[创作者] 作品列表无权限（状态码 {resp.status_code}）："
                f"userId={token.user_id}"
            )
            return [], 0
        if resp.status_code != 200:
            logger.error(
                f"[创作者] 作品列表状态码 {resp.status_code}：{resp.text[:200]}"
            )
            return None

        try:
            data = resp.json()
        except Exception as exc:  # noqa: BLE001
            logger.error(
                f"[创作者] 作品列表解析失败：{exc}；内容（前 200 字符）：{resp.text[:200]}"
            )
            return None
        if not isinstance(data, dict):
            logger.error(f"[创作者] 作品列表格式异常：{resp.text[:200]}")
            return None

        raw_items = data.get("List") or []
        items: list[PublishedMusic] = []
        for raw in raw_items:
            if isinstance(raw, dict):
                items.append(PublishedMusic(raw))

        total = 0
        for key in ("RecordCount", "Total", "TotalCount", "Count"):
            value = data.get(key)
            if isinstance(value, int) and value >= 0:
                total = value
                break
        logger.debug(
            f"[创作者] 第 {page} 页取得 {len(items)} 首作品，总数={total or '未知'}"
        )
        return items, total


def generate_music_code(token: Token, music_id: int, index: int = 0) -> str | None:
    """为指定自制谱生成一个兑换码，失败返回 ``None``。

    ``index`` 从 0 递增，作为接口的 ``cnt`` 参数（与 DcNana 的批量生成方式一致）。
    """
    resp = http_get(
        f"{_BASE}/api/MusicData/GetMusicCode?musicId={music_id}&cnt={index}",
        headers={"Authorization": token.bearer_token},
        context="生成兑换码",
    )
    if resp is None:
        logger.error(f"[创作者] 兑换码请求失败：musicId={music_id} cnt={index}")
        return None
    if resp.status_code != 200:
        logger.warning(
            f"[创作者] 兑换码生成失败：musicId={music_id} cnt={index} "
            f"状态码 {resp.status_code}：{resp.text[:200]}"
        )
        return None

    try:
        data = resp.json()
    except Exception as exc:  # noqa: BLE001
        logger.error(
            f"[创作者] 兑换码响应解析失败：{exc}；内容（前 200 字符）：{resp.text[:200]}"
        )
        return None
    code = str(data.get("Code") or "").strip() if isinstance(data, dict) else ""
    if not code:
        logger.warning(
            f"[创作者] 兑换码为空：musicId={music_id} cnt={index}；"
            f"响应（前 200 字符）：{resp.text[:200]}"
        )
        return None
    logger.debug(f"[创作者] 兑换码生成成功：musicId={music_id} cnt={index}")
    return code


def _to_int(value: object) -> int:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0
