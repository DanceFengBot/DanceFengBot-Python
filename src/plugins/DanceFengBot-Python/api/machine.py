"""舞立方机台查询，对应 Java 端 ``com.DanceCube.api.Machine``。"""

from __future__ import annotations

import json
import urllib.parse

from ..config import api_keys
from ..token import Token
from ..utils import logger
from ..utils.http import http_get

_BASE = "https://dancedemo.shenghuayule.com/Dance"


def get_location_info(region: str) -> str:
    """地名转经纬度（高德地图）。"""
    url = (
        "https://restapi.amap.com/v3/geocode/geo?address="
        f"{urllib.parse.quote(region.strip())}&output=json&key={api_keys.gaode_api_key}"
    )
    logger.debug(f"[机台查找] 地名转经纬度：{region}")
    resp = http_get(url, context="机台查找-地名转经纬度")
    if resp is None:
        logger.error(f"[机台查找] 高德地图请求失败：{region}")
        return ""
    if resp.status_code != 200:
        logger.error(
            f"[机台查找] 高德地图返回状态码 {resp.status_code}：{resp.text[:200]}"
        )
    elif '"status":"0"' in resp.text or '"status": "0"' in resp.text:
        # 高德 status=0 表示失败（如 key 无效 / 配额耗尽）
        logger.error(f"[机台查找] 高德地图返回业务错误：{resp.text[:200]}")
    return resp.text


class Machine:
    def __init__(self) -> None:
        self.place_name = ""
        self.address = ""
        self.show = False
        self.online = False

    @staticmethod
    def get_machine_list(lng: str, lat: str) -> list["Machine"]:
        resp = http_get(
            f"{_BASE}/OAuth/GetMachineListByLocation?lng={lng}&lat={lat}",
            context="机台查找-机台列表",
        )
        if resp is None:
            logger.error("[机台查找] 机台列表请求失败")
            return []
        try:
            arr = resp.json()
        except Exception as exc:  # noqa: BLE001
            logger.error(
                f"[机台查找] 机台列表响应解析失败：{exc}；"
                f"内容（前 200 字符）：{resp.text[:200]}"
            )
            return []
        result: list[Machine] = []
        for e in arr:
            m = Machine()
            m.place_name = e.get("PlaceName", "")
            m.address = e.get("Address", "")
            m.online = e.get("Online", False)
            m.show = e.get("MachineType", 0) == 1
            result.append(m)
        online = sum(1 for m in result if m.online)
        logger.debug(
            f"[机台查找] 经纬度({lng},{lat}) 共 {len(result)} 台机台，在线 {online} 台"
        )
        return result

    @staticmethod
    def get_machine_list_by_region(region: str) -> list["Machine"]:
        if not region or not region.strip():
            logger.debug("[机台查找] 地区为空，跳过查询")
            return []
        geojson = get_location_info(region)
        if not geojson:
            logger.warning(f"[机台查找] 未取得“{region}”的经纬度")
            return []
        try:
            loc = json.loads(geojson)["geocodes"][0]["location"]
        except Exception as exc:  # noqa: BLE001
            logger.error(
                f"[机台查找] 经纬度解析失败：{exc}；"
                f"高德返回（前 200 字符）：{geojson[:200]}"
            )
            return []
        lng, lat = loc.split(",")
        return Machine.get_machine_list(lng, lat)

    @staticmethod
    def qr_login(token: Token, qr_url: str):
        url = (
            f"{_BASE}/api/Machine/AppLogin?qrCode="
            f"{urllib.parse.quote(qr_url, safe='')}"
        )
        resp = http_get(
            url,
            headers={"Authorization": token.bearer_token},
            context="机台登录",
        )
        if resp is None:
            logger.error("[机台登录] 请求失败")
        elif resp.status_code != 200:
            logger.error(
                f"[机台登录] 登录失败，状态码 {resp.status_code}：{resp.text[:200]}"
            )
        else:
            logger.info("[机台登录] 登录成功")
        return resp

    def __repr__(self) -> str:
        return (
            f"Machine(PlaceName='{self.place_name}', Address='{self.address}', "
            f"Online={self.online})"
        )
