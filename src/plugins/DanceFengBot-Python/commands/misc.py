"""菜单 / 机台查找 / 查歌 / 兑换码 / Token 管理等命令。"""

from __future__ import annotations

import re
import time

from nonebot import on_command, on_fullmatch, on_regex
from nonebot.adapters.onebot.v11 import Message
from nonebot.adapters.onebot.v11.event import GroupMessageEvent, PrivateMessageEvent
from nonebot.matcher import Matcher
from nonebot.params import ArgPlainText, CommandArg

from .. import store
from ..api.machine import Machine
from ..api.player_music import gain_music_by_code
from ..deps import (
    admin_rule,
    group_rule,
    private_rule,
    resolve_token,
    to_thread,
)
from ..token import Token, TokenBuilder


# ---------------------------------------------------------------- 菜单
menu = on_fullmatch(("菜单", "help", "帮助"), priority=5, block=True)


@menu.handle()
async def _menu(matcher: Matcher) -> None:
    await matcher.finish("详见https://www.kdocs.cn/l/ccLRaUCuNMX0。")


# ---------------------------------------------------------------- 查找舞立方机台
machine_group = on_command(
    "查找舞立方", aliases={"查找"}, rule=group_rule, priority=5, block=True
)
machine_user = on_command(
    "查找舞立方", aliases={"查找"}, rule=private_rule, priority=5, block=True
)


@machine_group.handle()
async def _machine_group(matcher: Matcher, args: Message = CommandArg()) -> None:
    region = args.extract_plain_text().strip()
    if not region or len(region) > 15:
        return
    machine_list = await to_thread(Machine.get_machine_list_by_region, region)
    if not machine_list:
        await matcher.finish(f"在“{region}”似乎没有找到舞立方欸...")

    text = f'"{region}"的舞立方机台列表：'
    for i in range(min(len(machine_list), 5)):
        m = machine_list[i]
        show = "[⭐秀]" if m.show else ""
        online = "🔵在线" if m.online else "🔴离线"
        text += f"\n店名：{show}{m.place_name} {online}\n地址：{m.address}\n"
    if len(machine_list) > 5:
        await matcher.finish(text + f"⭐刷屏哒咩！私聊查询全部{len(machine_list)}条~")
    await matcher.finish(text + f"⭐呐！一共{len(machine_list)}条~")


@machine_user.handle()
async def _machine_user(matcher: Matcher, args: Message = CommandArg()) -> None:
    region = args.extract_plain_text().strip()
    if not region:
        await matcher.finish("格式：\n查找舞立方 (地区)")
    machine_list = await to_thread(Machine.get_machine_list_by_region, region)
    if not machine_list:
        await matcher.finish("似乎没有找到舞立方诶...")

    text = f'"{region}"的舞立方机台列表：'
    for m in machine_list:
        show = "[⭐秀]" if m.show else ""
        online = "🔵在线" if m.online else "🔴离线"
        text += f"\n店名：{show}{m.place_name} {online}\n地址：{m.address}\n"
    await matcher.finish(text)

# ---------------------------------------------------------------- 兑换码
gain_music = on_regex(r"[a-zA-Z0-9]{15}", rule=private_rule, priority=5, block=True)


@gain_music.handle()
async def _gain_music(event: PrivateMessageEvent, matcher: Matcher) -> None:
    token = await resolve_token(matcher, str(event.user_id))
    if token is None:
        return
    message = event.get_plaintext()
    codes = re.findall(r"[a-zA-Z0-9]{15}", message)

    for i, code in enumerate(codes[:24], start=1):
        await matcher.send(f'#{i} 小枫在努力兑换 "{code}" ...')
        resp = await to_thread(gain_music_by_code, token, code)
        if resp is None:
            return
        if resp.status_code == 200:
            await matcher.finish(f'"{code}"兑换成功啦！快去背包找找吧')

    await matcher.finish("好像都失效了💦💦\n换几个试试吧！")


# ---------------------------------------------------------------- 文件管理
save_cmd = on_fullmatch("#save", priority=5, block=True)
load_cmd = on_fullmatch("#load", priority=5, block=True)
logout_cmd = on_fullmatch("#logout", priority=5, block=True)


@save_cmd.handle()
async def _save(matcher: Matcher) -> None:
    n = store.save_tokens()
    await matcher.finish(f"保存成功！共{n}条")


@load_cmd.handle()
async def _load(matcher: Matcher) -> None:
    store.user_tokens_map = store.load_tokens(False)
    await matcher.finish(f"不刷新加载成功！共{len(store.user_tokens_map)}条")


@logout_cmd.handle()
async def _logout(event, matcher: Matcher) -> None:
    qq = str(event.user_id)
    token = store.user_tokens_map.get(qq)
    if token is None:
        await matcher.finish("当前账号未登录到舞小铃！")
    del store.user_tokens_map[qq]
    await matcher.finish(f"id:{token.user_id} 注销成功！")


# ---------------------------------------------------------------- Token 管理
show_token = on_fullmatch("#token", priority=5, block=True)


@show_token.handle()
async def _show_token(event, matcher: Matcher) -> None:
    token = await resolve_token(matcher, str(event.user_id))
    if token is None:
        return
    if isinstance(event, GroupMessageEvent):
        await matcher.finish("私聊才能看的辣！")
    await matcher.finish(str(token))


show_others_token = on_command("#token", rule=admin_rule, priority=6, block=True)


@show_others_token.handle()
async def _show_others_token(
    event, matcher: Matcher, args: Message = CommandArg()
) -> None:
    qq = args.extract_plain_text().strip()
    if not qq:
        return
    token = store.user_tokens_map.get(qq)
    if token is None:
        return
    if isinstance(event, GroupMessageEvent):
        await matcher.finish("私聊才能看的辣！")
    await matcher.finish(str(token))


show_default_token = on_fullmatch("#token0", priority=5, block=True)


@show_default_token.handle()
async def _show_default_token(event, matcher: Matcher) -> None:
    token = store.user_tokens_map.get("0")
    if token is None:
        return
    if isinstance(event, GroupMessageEvent):
        await matcher.finish("私聊才能看的辣！")
    await matcher.finish(str(token))


refresh_token = on_fullmatch("#refresh", priority=5, block=True)


@refresh_token.handle()
async def _refresh_token(event, matcher: Matcher) -> None:
    token = await resolve_token(matcher, str(event.user_id))
    if token is None:
        return
    if isinstance(event, GroupMessageEvent):
        await matcher.finish("私聊才能用的辣！")
    if await to_thread(token.refresh):
        await matcher.finish(f"#Token已强制刷新#\n\n{token}")
    await matcher.finish("刷新失败，请重新登录！")


# ---------------------------------------------------------------- 管理员
set_default_token = on_fullmatch("#setToken0", rule=admin_rule, priority=4, block=True)


@set_default_token.handle()
async def _set_default_token_start(event, matcher: Matcher) -> None:
    if isinstance(event, GroupMessageEvent):
        await matcher.finish("私聊才能用的辣！")
    await matcher.send("请发送 Access Token 和 Refresh Token\n使用换行区分token！")


@set_default_token.got("tokens")
async def _set_default_token_got(
    matcher: Matcher, raw: str = ArgPlainText("tokens")
) -> None:
    parts = raw.strip().split("\n")
    if len(parts) < 2:
        await matcher.finish("格式错误")
    access, refresh = parts[0].strip(), parts[1].strip()
    token = Token(0, access, refresh, int(time.time() * 1000))
    if await to_thread(token.check_available):
        store.user_tokens_map["0"] = token
        await matcher.finish(f"默认Token设置成功：\n\n{token}")
    await matcher.finish("默认Token设置失败：已无效")


hot_update = on_command("#update", rule=admin_rule, priority=4, block=True)


@hot_update.handle()
async def _hot_update(matcher: Matcher, args: Message = CommandArg()) -> None:
    param = args.extract_plain_text().strip()
    if not param:
        return
    if param in ("all", "id"):
        await matcher.send(str(TokenBuilder.update_ids()))
        await matcher.send("已成功刷新TokenID")
    if param in ("all", "reply"):
        await matcher.send("nope...")


clear_login = on_command("#clearLogin", rule=private_rule, priority=5, block=True)


@clear_login.handle()
async def _clear_login(
    event: PrivateMessageEvent, matcher: Matcher, args: Message = CommandArg()
) -> None:
    param = args.extract_plain_text().strip()
    if not param:
        return
    if param == "all":
        store.log_status.clear()
    elif param == "me":
        removed = str(event.user_id) in store.log_status
        store.log_status.discard(str(event.user_id))
        await matcher.finish("已清空！" if removed else "未找到登录！")
