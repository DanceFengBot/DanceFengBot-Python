"""DanceFengBot-Python 入口文件。"""

import nonebot
from nonebot.adapters.onebot.v11 import Adapter as OneBotV11Adapter

# 初始化 NoneBot
nonebot.init()

# 注册 OneBot V11 适配器
driver = nonebot.get_driver()
driver.register_adapter(OneBotV11Adapter)

# 从 pyproject.toml 加载插件（src/plugins）
nonebot.load_from_toml("pyproject.toml")

if __name__ == "__main__":
    nonebot.run()
