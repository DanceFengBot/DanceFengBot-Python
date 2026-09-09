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
│    │  TokenIds.json
│    │  UserTokens.json
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

## 安装与运行

```bash
# 1. 克隆本项目到本地
git clone https://github.com/DanceFengBot/DanceFengBot-Python.git

# 2. 创建并激活虚拟环境
cd DanceFengBot-Python
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/macOS
source .venv/bin/activate

# 3. 安装依赖
pip install -r ./requirements.txt

# 4. 下载DcConfig压缩包并解压到项目运行目录
https://github.com/DanceFengBot/DanceFengBot/releases/download/DcConfig-20260807/DcConfig.zip

# 5. 配置 OneBot 实现反向连接到本机 8080 端口（见 .env 的 HOST/PORT）
进入 go-cqhttp / NapCat / LLOneBot / Lagrange 的管理后台或配置文件，连接配置 选择/填写 反向Websocket / Websocket客户端 ，地址为ws://127.0.0.1:10219/onebot/v11/ws，无Token

# 6 . 运行
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
| `TokenIds.json`     | 文件      | 用于获取二维码登录    | **手动配置** |
| `ApiKeys.yml`       | 文件      | 用于API令牌      | **手动配置** |
| `UserCommands.json` | 文件      | 用于保存用户信息触发指令 | **无需手动配置** |


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

### 开发帮助

看不懂？翻翻源码就知道了！


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
