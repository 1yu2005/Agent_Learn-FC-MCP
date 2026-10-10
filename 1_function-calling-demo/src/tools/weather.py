"""业务工具：查询天气（真实项目里此处对接天气API)"""

WEATHER_MAP = {"北京": "晴 25°C", "上海": "多云 28°C", "广州": "阵雨 30°C"}

def get_weather(city:str) -> str:
    """
    查询制定城市的实时天气
    :param city: 城市名，如“北京”
    :return: 天气描述字符串；未知城市返回提示信息
    """
    return WEATHER_MAP.get(city,f"{city}天气数据暂缺")