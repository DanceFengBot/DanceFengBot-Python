"""舞立方机台查询，对应 Java 端 ``com.DanceCube.api.Machine``。"""

from __future__ import annotations

import json
import urllib.parse

from ..config import api_keys
from ..token import Token
from ..utils.http import http_get

_BASE = "https://dancedemo.shenghuayule.com/Dance"


def get_location_info(region: str) -> str:
    """地名转经纬度（高德地图）。"""
    url = (
        "https://restapi.amap.com/v3/geocode/geo?address="
        f"{urllib.parse.quote(region.strip())}&output=json&key={api_keys.gaode_api_key}"
    )
    resp = http_get(url)
    return resp.text if resp is not None else ""


class Machine:
    def __init__(self) -> None:
        self.place_name = ""
        self.address = ""
        self.show = False
        self.online = False

    @staticmethod
    def get_machine_list(lng: str, lat: str) -> list["Machine"]:
        resp = http_get(
            f"{_BASE}/OAuth/GetMachineListByLocation?lng={lng}&lat={lat}"
        )
        if resp is None:
            return []
        try:
            arr = resp.json()
        except Exception:
            return []
        result: list[Machine] = []
        for e in arr:
            m = Machine()
            m.place_name = e.get("PlaceName", "")
            m.address = e.get("Address", "")
            m.online = e.get("Online", False)
            m.show = e.get("MachineType", 0) == 1
            result.append(m)
        return result

    @staticmethod
    def get_machine_list_by_region(region: str) -> list["Machine"]:
        if not region or not region.strip():
            return []
        geojson = get_location_info(region)
        if not geojson:
            return []
        try:
            loc = json.loads(geojson)["geocodes"][0]["location"]
        except Exception:
            return []
        lng, lat = loc.split(",")
        return Machine.get_machine_list(lng, lat)

    @staticmethod
    def qr_login(token: Token, qr_url: str):
        url = (
            f"{_BASE}/api/Machine/AppLogin?qrCode="
            f"{urllib.parse.quote(qr_url, safe='')}"
        )
        return http_get(url, headers={"Authorization": token.bearer_token})

    def __repr__(self) -> str:
        return (
            f"Machine(PlaceName='{self.place_name}', Address='{self.address}', "
            f"Online={self.online})"
        )
