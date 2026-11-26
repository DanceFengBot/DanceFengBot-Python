# DanceFengBot-Python

舞立方 QQ 机器人（舞小枫）的 Python 移植版。基于 **NoneBot2** 框架，协议使用 **OneBot V11**。

原项目为 Java/Mirai 版本，本目录为功能等价移植：

- 框架：NoneBot2
- 适配器：nonebot-adapter-onebot（OneBot V11）
- 图片绘制：Pillow（替代 Java AWT）
- 定时任务：nonebot-plugin-apscheduler（替代 Quartz）

## 目录结构

```text
DanceFengBot-Python/
├── bot.py                          # 入口文件
├── pyproject.toml                  # 依赖与 NoneBot 配置
├── .env                            # NoneBot 配置
├── DcConfig
│    │  ApiKeys.yml
│    │  OfficialMusicIds.json
│    │  UserTokens.json
│    │
│    ├─cache                        # 生成图片的缓存目录
│    │      UserInfoImage_2587037271_20261008.png
│    │      UserRatioImage_2587037271_20261008.png ...
│    │
│    └─Images
│        │
│        ├─Cover
│        │  │  default.png
│        │  │
│        │  ├─CustomImage
│        │  │      1011.jpg
│        │  │      1023.jpg
│        │  │      1026.jpg ...
│        │  │      default.png
│        │  │
│        │  └─OfficialImage
│        │          101.jpg
│        │          106.jpg
│        │          115.jpg ...
│        │          default.png
│        │
│        ├─UserRatioImage
│        │      A.png
│        │      AP.png
│        │      B.png
│        │      Background1.png
│        │      Background2.png
│        │      Background3.png
│        │      C.png
│        │      Card1.png
│        │      Card2.png
│        │      Card3.png
│        │      D.png
│        │      result.png
│        │      S.png
│        │      SS.png
│        │      SSS.png
│        │
│        └─UserInfoImage
│                Background1.png
│                Background2.png
└── src/plugins/DanceFengBot-Python/  # 插件源码
    ├── __init__.py                 # 插件入口（Token 加载 / 定时刷新 / 加好友）
    ├── config.py                   # DcConfig 路径与 ApiKeys 解析
    ├── store.py                    # 全局 Token 状态
    ├── deps.py                     # 作用域规则 / Token 解析 / 图片发送
    ├── api/                        # 舞立方 HTTP API
    ├── token/                      # Token / TokenBuilder
    ├── ratio/                      # 成绩与战力计算
    ├── music/                      # 歌曲与封面
    ├── info/                       # 账号信息
    ├── image/                      # Pillow 图片绘制
    ├── utils/                      # http / 腾讯OCR / 字体 / 加解密
    └── commands/                   # 命令事件响应器
```

## 环境要求

- **Python >= 3.11**
- 一个支持 OneBot V11 的 QQ 实现（如 go-cqhttp / NapCat / LLOneBot / Lagrange）
- **Windows 10或Windows Server 2016及以上版本**或**2022年及以后发布的Linux发行版**

## 安装与运行

### 1. 克隆本项目到本地

```
git clone https://github.com/DanceFengBot/DanceFengBot-Python.git
```

#### 2. 创建并激活虚拟环境

```
cd DanceFengBot-Python
python -m venv .venv
```

##### Windows
```
.venv\Scripts\activate
```

##### Linux/macOS

```
source .venv/bin/activate
```

#### 3. 安装依赖

```
pip install -r ./requirements.txt
```

#### 4. 下载DcConfig压缩包并解压到项目运行目录

```
https://github.com/DanceFengBot/DanceFengBot/releases/download/DcConfig-20260807/DcConfig.zip
```

#### 5. 配置 OneBot 实现反向连接到本机 8080 端口（见 .env 的 HOST/PORT）
进入 ***go-cqhttp / NapCat / LLOneBot / Lagrange*** 的管理后台或配置文件，连接配置 **选择/填写反向Websocket / Websocket客户端 **，地址为***ws://127.0.0.1:10219/onebot/v11/ws***，无Token

#### 6 . 运行

```
python bot.py
```


## 配置文件（DcConfig）

机器人读取 `DcConfig` 目录，默认位于**项目运行目录**（当前工作目录，即运行
`python bot.py` 所在目录）下的 `DcConfig`。可用环境变量 `DCF_CONFIG_PATH` 指定其它位置。

启动时会校验以下文件/目录，**任一缺失则报错并退出**：

| 文件                  | 类型      | 功能           | 要求       |
|---------------------|---------|--------------|----------|
| `Images`            | **文件夹** | 存放素材图片文件     | **手动配置** |
| `UserTokens.json`   | 文件      | 用于保存用户令牌     | **无需手动配置** |
| `ApiKeys.yml`       | 文件      | 用于API令牌      | **手动配置** |
| `UserCommands.json` | 文件      | 用于保存用户信息触发指令 | **无需手动配置** |
| `BlackList.json` | 文件 | 用于存放黑名单列表 | **无需手动配置** |
| `WhiteList.json` | 文件 | 用于存放白名单列表 | **无需手动配置** |
| `Curfew.json` | 文件 | 宵禁时段与回复延迟配置 | **无需手动配置**（首次启动自动生成） |
| `cache` | **文件夹** | 生成图片的缓存目录 | **无需手动配置** |

### 图片缓存（`DcConfig/cache`）

所有由代码生成的图片（个人信息、战力图、分数列表、登录二维码、图形验证码等）都会先
写入 `DcConfig/cache`，再以本地文件的形式发送给用户。文件名为
`<操作>_<QQ号>_<日期>.<扩展名>`，日期为 `YYYYMMDD`，例如
`UserInfoImage_2587037271_20261008.png`；同一天内同一操作的图片会覆盖同名文件。

缓存目录每天 **0:00** 自动清空一次（由 `nonebot-plugin-apscheduler` 触发）；启动时也会
清理掉非当天的遗留缓存，避免停机错过清理时间导致文件堆积。

可能你会发现不管开几个标签都是一样的，可以尝试先**登录**一个二维码，再打开另一个标签页

#### ApiKeys

用于**二维码识别**和**地名转经纬度**

*本项目使用的是[**腾讯SDK**](https://cloud.tencent.com/)和[**高德地图**](https://lbs.amap.com/)
的API，每月限度充足且**免费**，所以请自行申请API令牌*

---

**当然，如果有别的需求或者使用其它第三方平台SDK，请自己修改源码**

```yaml
# 腾讯OCR SDK密钥
tencentScannerKeys:
  secretId: AKIDK****TBnFXeibIm*********
  secretKey: HLCrQoyzrZ8Z1************
# 高德地图定位 SDK密钥
gaodeMapKeys:
  apiKey: b1bbd99c****1172**************
```

#### Images

配置文件中已含有背景图片

如果想自定义模板，需要修改`Image`类的源码  
你也可以进入[即时设计](https://js.design/f/Y3IL8R)中获取本图片模板，自行设计

### 宵禁与回复延迟（`DcConfig/Curfew.json`）

首次启动时会自动生成该文件，**修改后无需重启**（按文件修改时间自动加载）：

```json
{
  "enabled": true,
  "ranges": [
    { "start": "23:00", "end": "07:00" }
  ],
  "delay": { "min": 3.0, "max": 4.0 },
  "admin_bypass": true
}
```

| 字段             | 说明                                                                |
|----------------|-------------------------------------------------------------------|
| `enabled`      | 宵禁总开关；`false` 时不拦截任何消息，但延迟仍然生效                                    |
| `ranges`       | 宵禁时段列表，`start` 晚于 `end` 表示跨天（如 `23:00`-`07:00`），可配置多段；起止时间相同的时段会被忽略 |
| `delay`        | 每条指令开始处理前的随机延迟（秒）；`min` 与 `max` 相同即固定延迟，都设为 `0` 可关闭延迟           |
| `admin_bypass` | 为 `true` 时管理员（`config.ADMINS` / `SUPERUSERS`）在宵禁时段内仍可正常使用命令        |

- 宵禁时段内，机器人对所有命令**静默不回复**，只在日志中记录一条 `[宵禁]` 记录，便于核对；
- 延迟只作用于指令的首次触发，`got` / `receive` 等多步会话的后续步骤不会重复等待；
- 时间按运行机器的**本地时区**判断。

## 个人信息与查看他人

| 指令                                                             | 说明                            |
|----------------------------------------------------------------|-------------------------------|
| `个人信息` / `看看我的` / `我的信息` / `我的舞立方` / `mydc` / `mywlf`           | 生成自己的个人信息图                     |
| `看看你的 [舞立方ID/QQ号/@群友]`（别名 `康康你的`）                             | 生成他人的个人信息图，需要先登录自己的账号          |

- 以 @ 方式查询时，需要对方曾在小枫登录过（才能把 QQ 换成舞立方 ID），否则请直接填写对方的舞立方 ID；
- 对方设置隐私时，会显示「该账号已设置隐私」以及可公开的基础信息。

## 单曲成绩与官方曲目封面

### 单曲成绩（纯文字）

| 指令                        | 说明                        |
|---------------------------|---------------------------|
| `歌曲成绩 [歌曲id]`             | 查询自己在该歌曲各难度的成绩，返回纯文字      |
| `单曲成绩 [歌曲id]`<br>`music [歌曲id]` | 同上（别名）                    |

- 与其它查询指令一样需要先私聊登录；
- 输出包含每个已游玩难度的难度类型、等级、准确率与评级、分数、单曲战力、
  Combo / Miss 与排名；没有记录时会提示检查歌曲 id；
- 自制谱会在歌名前加 `[自制]` 前缀（与官谱区分）。

### 更新官方曲目封面

| 指令                   | 权限  | 说明                       |
|----------------------|-----|--------------------------|
| `#updateCover`       | 管理员 | 拉取最新官方曲目清单，补齐缺失的封面       |
| `#updateCover force` | 管理员 | 强制重新下载全部封面（`force` / `all` / `强制`） |

- 每天 **03:00** 自动执行一次（只补缺失的封面），也可以用上面的指令手动触发；
- 封面保存在 `DcConfig/Images/Cover/OfficialImage/<歌曲id>.jpg`；
- 拉取到的最新封面地址会合并写入本地索引 `DcConfig/Images/Cover/CoverData`，
  远端索引（GitHub）不可用时 `music.cover` 会用它兜底；
- 更新过程只下载缺失封面，重复执行不会重复下载；同一时间只允许一个更新任务。

## 创作者（谱师）功能

面向舞立方自制谱创作者（谱师）的查询与兑换码工具，功能对标 DcNana 的「创作者」菜单。

| 指令                                                        | 说明                                    |
|-----------------------------------------------------------|---------------------------------------|
| `创作者信息`（别名 `谱师信息` / `maker` / `makerinfo`）                | 查看创作等级、创作金币                           |
| `我的自制谱 [页码]`（别名 `我的作品` / `自制谱列表` / `mypublish`）        | 查看已发布的自制谱，每页 10 首                     |
| `生成兑换码 [歌曲id] [数量]`（别名 `批量生成兑换码` / `gencode`）          | 为指定自制谱批量生成兑换码，数量 1~50，默认 1            |
| `兑换码全家桶`（别名 `全家桶` / `familycode`）                        | 为所有已发布自制谱各生成 1 个兑换码（最多 30 首）          |

- 所有指令都需要先私聊登录舞立方账号；
- `创作者信息` 会显示创作者认证状态（普通账号接口也会返回 `MakerGrade=1`，因此按
  `AuthStatus` / 创作等级 / 历史收益综合判断是否已开通创作者）；
- 兑换码属于敏感信息，`生成兑换码` / `兑换码全家桶` 仅限私聊使用；
- 兑换码仅可使用一次，请勿公开分享；兑换时直接私聊发送兑换码即可（支持一次发送多个）。
- 网页版（`web/` 的「创作者中心」）与 App（`app/` 的「创作者」页）提供同样的功能，
  数据由 PHP 后端直接请求舞立方接口。

## 服务器状态（`#status`）

管理员可在私聊/群聊发送 `#status`（别名 `服务器状态`）查看服务器状态：

```text
🖥 服务器状态
系统：Windows 10.0.26100（AMD64）
CPU：12.3%（16 核）
内存：45.6%（7.3 GB / 16.0 GB）
版本：DanceFengBot-Python 0.1.0
Python：3.11.0
运行时长：2 天 03:12:45
当前时间：2026-11-18 23:12:43（UTC+08:00）
```

- CPU / 内存优先通过 `psutil` 采集；未安装时在 Windows 调用系统 API、在 Linux 读取
  `/proc`，不需要新增依赖；
- 版本号读取自 `pyproject.toml` 的 `[project].version`；
- 运行时长按当前 Python 进程的启动时间计算，重启后重新计时。

## 捐赠说明
本项目为开源项目，接受各种形式的友情捐赠。您的支持将帮助我们持续改进和维护项目

<p>
    <img src="alipay.jpg" alt="alipay" width="50%" /><img src="weixin.png" alt="weixin" width="50%"  />
</p>
## 一些提醒

如果真的有人需要搭建，以下是一些注意事项：

- 请不要高频http请求
- 请遵循开源协议，禁止将本项目用于商业用途
- 本项目和[**广州市胜骅动漫科技有限公司**](https://arccer.com/#/home)无关

## 鸣谢
- **感谢 艾鲁Bot 的API提供** ~~呜呜呜，我的寄鲁😭~~
- **感谢各个开发者的测试与帮助**
