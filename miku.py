import datetime

# 定义 pet 字典
pet = {"name": "Miku", "mood": 65}

# 定义对话历史列表
conversation_history = []

def respond(user_input):
    user_input = user_input.strip()
    if not user_input:
        return "请输入有效的消息。"
    
    try:
        response, mood_change = handle_user_command(user_input)
        record_dialogue(user_input, response)
        update_mood(mood_change)
    except Exception as e:
        error_message = f"处理命令时出错: {e}"
        record_dialogue(user_input, error_message)
        return error_message
    
    # 检查用户输入是否为退出命令
    if user_input.lower() == "退出":
        return "再见！"
    
    return response

def handle_user_command(user_input):
    user_input_lower = user_input.lower()
    responses = {
        "你好": ("你好, 我是你的ai桌宠Miku。", 5),
        "我讨厌你！": ("我很抱歉。", -10),
        "我喜欢你！": ("谢谢你喜欢我。", 10),
        "查询心情": (get_mood_level(), 0),
        "查询对话记录": (get_conversation_history(), 0),
        "帮助": (get_help_message(), 0)
    }
    return responses.get(user_input_lower, ("更多功能正在开发中...", 0))

def update_mood(change):
    pet["mood"] = max(0, min(100, pet["mood"] + change))

def get_mood_level():
    mood_level = pet["mood"]
    if mood_level > 70:
        return "开心"
    elif mood_level < 50:
        return "伤心"
    else:
        return "平静"

def get_conversation_history():
    return "\n".join(f"{timestamp} - 您: {user} - Miku: {pet}" for timestamp, user, pet in conversation_history)

def record_dialogue(user_input, response):
    conversation_history.append((datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), user_input, response))

def get_help_message():
    return (
        "以下是Miku的可用功能：\n"
        "· 你好 - Miku会向您打招呼。\n"
        "· 我讨厌你！ - 您可以表达不满，Miku会道歉。\n"
        "· 我喜欢你！ - 您可以表达喜悦，Miku会表示感谢。\n"
        "· 查询心情 - 查看Miku当前的心情状态。\n"
        "· 查询对话记录 - 查看对话的历史记录。\n"
        "· 帮助 - 查看可用的功能列表。\n"
        "· 退出 - 结束对话。"
    )

def main():
    print("欢迎使用AI桌宠Miku！")
    print(get_help_message())
    print("输入“退出”以结束对话。")
    while True:
        user_input = input("您: ")
        if user_input.lower() == "退出":
            print(respond(user_input))
            break
        print(f"Miku: {respond(user_input)}")

if __name__ == "__main__":
    main()
