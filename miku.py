import datetime

# 宠物的状态属性
pet = {
    "name": "Miku",
    "mood": 65,  # 心情值 (0-100)
    "energy": 80,  # 能量值 (0-100)
    "last_fed": None  # 上次喂食时间
}

# 对话历史记录 - 现在存储为元组 (时间, 发言者, 内容)
conversation_history = []

# 处理用户命令的函数
def handle_user_command(user_input):
    user_input_lower = user_input.lower()
    should_exit = False  # 退出标志

    # 基础命令
    if "你好" in user_input_lower:
        return f"你好主人，我是{pet['name']}!", 5, should_exit
    elif "讨厌" in user_input_lower:
        return "我做错了什么吗？我会改进的...", -15, should_exit
    elif "喜欢" in user_input_lower or "爱你" in user_input_lower:
        return "谢谢你！我也喜欢你~", 10, should_exit
    elif "心情" in user_input_lower or "情绪" in user_input_lower:
        return get_mood_level(), 0, should_exit
    elif "能量" in user_input_lower:
        return get_energy_level(), 0, should_exit
    elif "历史" in user_input_lower or "记录" in user_input_lower:
        return get_conversation_history(), 0, should_exit
    elif "帮助" in user_input_lower:
        return get_help_message(), 0, should_exit
    elif "退出" in user_input_lower:
        should_exit = True  # 设置退出标志
        return "再见主人，我会想你的！", 0, should_exit

    # 新功能：喂食
    elif "喂食" in user_input_lower or "饿了" in user_input_lower:
        pet['last_fed'] = datetime.datetime.now()
        pet['energy'] = min(100, pet['energy'] + 20)
        return "谢谢主人的食物！", 10, should_exit

    # 默认响应
    return "我正在学习理解这个指令...", -3, should_exit

# 获取心情状态的函数
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

# 获取能量状态的函数
def get_energy_level():
    energy = pet["energy"]
    if energy >= 70:
        return "⚡ 精力充沛"
    elif energy >= 40:
        return "🔋 能量中等"
    else:
        return "🪫 需要休息"

# 获取带时间戳的对话历史记录
def get_conversation_history():
    if not conversation_history:
        return "还没有对话记录。"
    
    # 格式化时间显示
    formatted_history = []
    for timestamp, speaker, message in conversation_history:
        # 将时间转换为易读格式 (例如: 07-10 14:30)
        time_str = timestamp.strftime("%m-%d %H:%M")
        formatted_history.append(f"[{time_str}] {speaker}: {message}")
    
    # 只显示最近的10条记录
    recent_history = formatted_history[-10:] if len(formatted_history) > 10 else formatted_history
    return "最近的对话记录:\n" + "\n".join(recent_history)

# 获取帮助信息的函数
def get_help_message():
    return (
        "==== Miku 帮助菜单 ====\n"
        "· 你好 - 打招呼\n"
        "· 我讨厌你 - Miku会道歉\n"
        "· 我喜欢你 - Miku会开心\n"
        "· 喂食 - 给Miku补充能量\n"
        "· 心情 - 查看Miku当前心情\n"
        "· 能量 - 查看Miku能量状态\n"
        "· 历史 - 查看带时间戳的对话记录\n"
        "· 帮助 - 显示此帮助\n"
        "· 退出 - 结束程序\n"
        "======================="
    )

# 更新宠物状态的函数
def update_status():
    # 每次对话减少1点能量
    pet["energy"] = max(0, pet["energy"] - 1)
    
    # 如果设置了喂食时间且超过1分钟未喂食，减少心情
    if pet["last_fed"]:
        time_since_fed = datetime.datetime.now() - pet["last_fed"]
        if time_since_fed.total_seconds() > 60:  # 60秒 = 1分钟
            pet["mood"] = max(0, pet["mood"] - 5)

# 主程序循环
def main():
    print(f"欢迎来到虚拟宠物 {pet['name']} 的世界！输入'帮助'查看命令列表。")
    
    while True:
        update_status()
        user_input = input("您: ")
        
        # 记录用户输入（带时间戳）
        now = datetime.datetime.now()
        conversation_history.append((now, "您", user_input))
        
        # 处理命令并获取响应
        response, mood_change, should_exit = handle_user_command(user_input)
        pet["mood"] = max(0, min(100, pet["mood"] + mood_change))
        
        # 记录宠物响应（带时间戳）
        now = datetime.datetime.now()
        conversation_history.append((now, pet["name"], response))
        
        # 显示响应
        print(f"{pet['name']}: {response}")
        
        # 检查是否需要退出
        if should_exit:
            break

if __name__ == "__main__":
    main()