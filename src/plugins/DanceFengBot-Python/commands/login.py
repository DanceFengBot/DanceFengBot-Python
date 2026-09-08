"""登录 / 退出登录 / 借号 / 机台登录相关命令。"""

from __future__ import annotations

from nonebot import on_command, on_fullmatch
from nonebot.adapters.onebot.v11 import Message, MessageSegment
from nonebot.adapters.onebot.v11.event import GroupMessageEvent, PrivateMessageEvent
from nonebot.matcher import Matcher
from nonebot.params import Arg, ArgPlainText, CommandArg

from .. import store
from ..api.machine import Machine
from ..api.phone_login import PhoneLoginBuilder
from ..deps import (
    group_rule,
    image_segment,
    private_rule,
    resolve_token,
    to_thread,
)
from ..token import TokenBuilder
from ..utils.http import get_bytes_from_url
from ..utils.tencent import qr_decode_tencent


# ---------------------------------------------------------------- 二维码登录
dc_login = on_fullmatch(("登录", "舞立方登录"), rule=private_rule, priority=5, block=True)


@dc_login.handle()
async def _dc_login(event: PrivateMessageEvent, matcher: Matcher) -> None:
    qq = str(event.user_id)
    if qq in store.log_status:
        await matcher.finish("(´。＿。｀)不要重复登录啊喂！")

    builder = TokenBuilder()
    try:
        qr_url = builder.get_qrcode_url()
    except RuntimeError as e:
        await matcher.finish(str(e))
    qr_bytes = get_bytes_from_url(qr_url)
    if not qr_bytes:
        await matcher.finish("二维码获取失败，请稍后再试")

    await matcher.send(
        MessageSegment.text("🤗快用微信扫码，在五分钟内登录上吧~")
        + image_segment(qr_bytes)
    )

    store.log_status.add(qq)
    try:
        token = await to_thread(builder.get_token)
        if token is None:
            await matcher.send("超时啦~ 请重试一下吧！")
        else:
            store.user_tokens_map[qq] = token
            await matcher.send(
                f"登录成功啦~(●'◡'●)\n你的ID是：{token.user_id}\n\n"
                "⭐要是账号不匹配的话，重新发送登录就好了"
            )
            await matcher.send("欢迎加入机器人的QQ群聊：908659951。")
    finally:
        store.log_status.discard(qq)


# ---------------------------------------------------------------- 退出登录
dc_logout = on_fullmatch("退出登录", rule=private_rule, priority=5, block=True)


@dc_logout.handle()
async def _dc_logout(event: PrivateMessageEvent, matcher: Matcher) -> None:
    qq = str(event.user_id)
    if qq in store.log_status:
        await matcher.finish("(´。＿。｀)你正在登录诶！登录后再试试吧")
    if qq not in store.user_tokens_map:
        await matcher.finish("舞小枫这没有过你的账号！")
    del store.user_tokens_map[qq]
    await matcher.finish("退出登录成功！")


# ---------------------------------------------------------------- 手机号登录
phone_login = on_command(
    "手机号登录", aliases={"验证码登录"}, rule=private_rule, priority=5, block=True
)


@phone_login.handle()
async def _phone_login_start(
    event: PrivateMessageEvent, matcher: Matcher, args: Message = CommandArg()
) -> None:
    number = args.extract_plain_text().strip()
    if not number:
        await matcher.finish(
            "格式：手机号登录 (手机号)\n例：手机号登录 100xxxx0000\n"
            "“手机号登录“和(手机号)之间是有空格的。"
        )

    builder = PhoneLoginBuilder(number)
    graph = await to_thread(builder.get_graph_code)
    if not graph:
        await matcher.finish("无效的手机号！")

    matcher.state["builder"] = builder
    matcher.state["qq"] = str(event.user_id)
    await matcher.send(
        MessageSegment.text("🐈reCATcha 猫娘检测！\n如果你不是一只猫娘，请发送该识别码")
        + image_segment(graph)
        + MessageSegment.text("*请勿频繁登录！")
    )


@phone_login.got("graph_code")
async def _phone_login_graph(
    matcher: Matcher, graph_code: str = ArgPlainText("graph_code")
) -> None:
    builder: PhoneLoginBuilder = matcher.state["builder"]
    text = graph_code.strip()
    if text == "取消":
        await matcher.finish("登录已取消")
    if not await to_thread(builder.get_sms_code, text):
        await matcher.reject_arg(
            "graph_code", "图形验证码错误，重新发送\n*如需要取消登录请发送“取消”"
        )
    await matcher.send(
        "很棒，你不是一只猫娘！\n验证码已发出，请及时查收并直接发送给舞小枫"
    )


@phone_login.got("sms_code")
async def _phone_login_sms(
    matcher: Matcher, sms_code: str = ArgPlainText("sms_code")
) -> None:
    builder: PhoneLoginBuilder = matcher.state["builder"]
    text = sms_code.strip()
    if text == "取消":
        await matcher.finish("登录已取消")
    token = await to_thread(builder.login, text)
    if token is None:
        await matcher.reject_arg(
            "sms_code", "验证码错误，重新发送\n*如需要取消登录请发送“取消”"
        )

    store.user_tokens_map[matcher.state["qq"]] = token
    await matcher.finish(
        f"登录成功啦~(●'◡'●)\n你的ID是：{token.user_id}\n\n"
        "⭐要是账号不匹配的话，重新登录就好了\n\n"
        "欢迎加入机器人的QQ群聊：908659951。"
    )


# ---------------------------------------------------------------- 借号扫码登录
borrow_group = on_command("借号", rule=group_rule, priority=5, block=True)
borrow_user = on_command("借号", rule=private_rule, priority=5, block=True)


@borrow_group.handle()
async def _borrow_group(matcher: Matcher) -> None:
    await matcher.finish("私聊才能借号！")


@borrow_user.handle()
async def _borrow_user_start(
    event: PrivateMessageEvent, matcher: Matcher, args: Message = CommandArg()
) -> None:
    friend_qq = args.extract_plain_text().strip()
    if not friend_qq:
        await matcher.finish("格式：借号 (QQ号)")

    token = await resolve_token(
        matcher,
        friend_qq,
        no_login="对方没有登录！这个账号借不到了诶...",
        invalid="过期！这个账号借不到了诶...",
    )
    if token is None:
        return

    matcher.state["token"] = token
    await matcher.send(
        MessageSegment.text("请在3分钟之内发送机台二维码图片哦！\n一定要清楚才好！")
    )


@borrow_user.got("qr")
async def _borrow_user_qr(matcher: Matcher, msg: Message = Arg("qr")) -> None:
    token = matcher.state["token"]
    images = [seg for seg in msg if seg.type == "image"]
    if len(images) != 1:
        await matcher.finish("这个不是图片吧...重新发送“借号”吧")

    img_url = images[0].data.get("url", "")
    qr_url = await to_thread(qr_decode_tencent, img_url)
    if not qr_url:
        await matcher.finish("没有扫出来！再试一次吧！")

    resp = await to_thread(Machine.qr_login, token, qr_url)
    if resp is not None and resp.status_code == 200:
        await matcher.finish("借号成功辣，快来出勤吧！")
    await matcher.finish("二维码失效了，换一个试试看吧")


# ---------------------------------------------------------------- 机台登录（弃用）
machine_login = on_command("机台登录", aliases={"jt"}, priority=5, block=True)


@machine_login.handle()
async def _machine_login(
    event, matcher: Matcher, args: Message = CommandArg()
) -> None:
    link = args.extract_plain_text().strip()
    if not link:
        await matcher.send("请在QQ扫码后复制链接\n格式：机台登录/jt (链接)")
    token = await resolve_token(matcher, str(event.user_id))
    if token is None:
        return
    if not link:
        return
    resp = await to_thread(Machine.qr_login, token, link)
    if resp is not None and resp.status_code == 200:
        await matcher.finish("登录成功辣，快来出勤吧！")
    await matcher.finish("链接失效了，换一个试试看吧")


# ---------------------------------------------------------------- 错别字梗
fake_login = on_fullmatch("登陆", rule=private_rule, priority=5, block=True)


@fake_login.handle()
async def _fake_login(matcher: Matcher) -> None:
    await matcher.finish("（生气）你当小枫飞机场啊！登陆登陆的...")
