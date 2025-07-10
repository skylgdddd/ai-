import datetime
import requests
import os
import re
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 使用官方测试API密钥
SENIVERSE_API_KEY = os.getenv("SENIVERSE_API_KEY", "SnpVu8oYEbFAsQvm6")
HEFENG_API_KEY = os.getenv("HEFENG_API_KEY", "b8b3c3c8f0f74f2c8c0d8a6c0d3a6c0d")

# 宠物的状态属性
pet = {
    "name": "Miku",
    "mood": 65,  # 心情值 (0-100)
    "energy": 80,  # 能量值 (0-100)
    "last_fed": None  # 上次喂食时间
}

# 对话历史记录 - 现在存储为元组 (时间, 发言者, 内容)
conversation_history = []

def get_weather(city="北京"):
    """获取指定城市的实时天气（支持双API源）"""
    seniverse_result = try_seniverse_api(city)
    if seniverse_result and "解析天气数据时出错" not in seniverse_result:
        return seniverse_result
    
    hefeng_result = try_hefeng_api(city)
    if hefeng_result:
        return hefeng_result
    
    return "所有天气服务均不可用，请稍后再试"

def try_seniverse_api(city):
    """尝试使用心知天气API"""
    try:
        url = "https://api.seniverse.com/v3/weather/now.json"
        params = {
            "key": SENIVERSE_API_KEY,
            "location": city,
            "language": "zh-Hans",
            "unit": "c"
        }
        
        response = requests.get(url, params=params, timeout=5)
        response.raise_for_status()
        
        weather_data = response.json()
        result = weather_data.get("results", [{}])[0]
        
        location_name = result.get("location", {}).get("name", "未知城市")
        weather_text = result.get("now", {}).get("text", "未知")
        temperature = result.get("now", {}).get("temperature", "未知")
        last_update = result.get("last_update", "未知")
        
        return (f"【心知天气】{location_name}实时天气\n"
                f"☁️ 状况: {weather_text}\n"
                f"🌡️ 温度: {temperature}°C\n"
                f"🕒 更新: {last_update}")
            
    except requests.exceptions.RequestException as e:
        return f"心知天气请求失败: {str(e)}"
    except (KeyError, IndexError, TypeError) as e:
        return f"解析心知天气数据时出错: {str(e)}"

def try_hefeng_api(city):
    """尝试使用和风天气API"""
    try:
        location_url = "https://geoapi.qweather.com/v2/city/lookup"
        location_params = {
            "key": HEFENG_API_KEY,
            "location": city,
            "adm": "cn",
            "number": 1
        }

        location_resp = requests.get(location_url, params=location_params, timeout=5)
        location_resp.raise_for_status()
        location_data = location_resp.json()

        if location_data.get("code") == "200" and location_data.get("location"):
            location_id = location_data["location"][0]["id"]
            
            weather_url = "https://devapi.qweather.com/v7/weather/now"
            weather_params = {
                "key": HEFENG_API_KEY,
                "location": location_id
            }

            weather_resp = requests.get(weather_url, params=weather_params, timeout=5)
            weather_resp.raise_for_status()
            weather_data = weather_resp.json()

            if weather_data.get("code") == "200":
                now = weather_data["now"]
                return (f"【和风天气】{city}实时天气\n"
                        f"☁️ 状况: {now['text']}\n"
                        f"🌡️ 温度: {now['temp']}°C\n"
                        f"💨 风力: {now['windScale']}级\n"
                        f"💧 湿度: {now['humidity']}%\n"
                        f"🕒 更新: {weather_data['updateTime']}")

        return "和风天气：未获取到数据"
            
    except requests.exceptions.RequestException as e:
        return f"和风天气请求失败: {str(e)}"
    except (KeyError, IndexError, TypeError) as e:
        return f"解析和风天气数据时出错: {str(e)}"

def handle_user_command(user_input):
    user_input_lower = user_input.lower()
    should_exit = False

    if "你好" in user_input_lower:
        response, mood_change = f"你好主人，我是{pet['name']}!", 5
    elif "讨厌" in user_input_lower:
        response, mood_change = "我做错了什么吗？我会改进的...", -15
    elif "喜欢" in user_input_lower or "爱你" in user_input_lower:
        response, mood_change = "谢谢你！我也喜欢你~", 10
    elif "心情" in user_input_lower or "情绪" in user_input_lower:
        response, mood_change = get_mood_level(), 0
    elif "能量" in user_input_lower:
        response, mood_change = get_energy_level(), 0
    elif "历史" in user_input_lower or "记录" in user_input_lower:
        response, mood_change = get_conversation_history(), 0
    elif "帮助" in user_input_lower:
        response, mood_change = get_help_message(), 0
    elif "退出" in user_input_lower:
        response, mood_change = "再见主人，我会想你的！", 0
        should_exit = True
    elif "喂食" in user_input_lower or "饿了" in user_input_lower:
        pet['last_fed'] = datetime.datetime.now()
        pet['energy'] = min(100, pet['energy'] + 20)
        response, mood_change = "谢谢主人的食物！", 10
    elif "天气" in user_input_lower:
        city = extract_city_from_input(user_input)
        if not city:
            response, mood_change = "城市名称太短，请提供完整的城市名称", 0
        else:
            response, mood_change = get_weather(city), 0
    else:
        response, mood_change = "我正在学习理解这个指令...", -3

    return response, mood_change, should_exit

def extract_city_from_input(user_input):
    city_match = re.search(r'天气\s*[:：]?\s*(\S+)', user_input)
    if city_match:
        city = city_match.group(1).strip()
        if len(city) >= 2:
            return city
    return None

def get_mood_level():
    mood = pet["mood"]
    if mood >= 80:
        return "😄 非常开心！"
    elif mood >= 60:
        return "😊 心情不错"
    elif mood >= 40:
        return "😐 感觉一般"
    elif mood >= 20:
        return "😔 有点低落"
    else:
        return "😭 非常伤心"

def get_energy_level():
    energy = pet["energy"]
    if energy >= 70:
        return "⚡ 精力充沛"
    elif energy >= 40:
        return "🔋 能量中等"
    else:
        return "🪫 需要休息"

def get_conversation_history():
    if not conversation_history:
        return "还没有对话记录。"
    
    formatted_history = [f"[{timestamp.strftime('%m-%d %H:%M')}] {speaker}: {message}"
                         for timestamp, speaker, message in conversation_history[-10:]]
    
    return "最近的对话记录:\n" + "\n".join(formatted_history)

def get_help_message():
    return (
        "==== Miku 帮助菜单 ====\n"
        "· 你好 - 打招呼\n"
        "· 我讨厌你 - Miku会道歉\n"
        "· 我喜欢你 - Miku会开心\n"
        "· 喂食 - 给Miku补充能量\n"
        "· 天气 [城市] - 查询天气（默认北京）\n"
        "· 心情 - 查看Miku当前心情\n"
        "· 能量 - 查看Miku能量状态\n"
        "· 历史 - 查看带时间戳的对话记录\n"
        "· 帮助 - 显示此帮助\n"
        "· 退出 - 结束程序\n"
        "======================="
    )

def update_status():
    pet["energy"] = max(0, pet["energy"] - 1)
    if pet["last_fed"]:
        if (datetime.datetime.now() - pet["last_fed"]).total_seconds() > 60:
            pet["mood"] = max(0, min(100, pet["mood"] - 5))

def main():
    print(f"欢迎来到虚拟宠物 {pet['name']} 的世界！输入'帮助'查看命令列表。")
    
    global should_exit
    should_exit = False
    
    while not should_exit:
        update_status()
        user_input = input("您: ")
        
        now = datetime.datetime.now()
        conversation_history.append((now, "您", user_input))
        
        response, mood_change, should_exit = handle_user_command(user_input)
        pet["mood"] = max(0, min(100, pet["mood"] + mood_change))
        
        conversation_history.append((now, pet["name"], response))
        
        print(f"{pet['name']}: {response}")

if __name__ == "__main__":
    main()
