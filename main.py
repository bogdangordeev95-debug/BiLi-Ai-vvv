import os
import time
import requests
import vk_api
from vk_api.longpoll import VkLongPoll, VkEventType
from dotenv import load_dotenv

load_dotenv()

# Ключи берутся из файла .env, в коде их нет
VK_TOKEN = os.getenv("VK_TOKEN")
AI_API_KEY = os.getenv("AI_API_KEY")

AI_URL = "https://openrouter.ai/api/v1/chat/completions"
AI_MODEL = "google/gemini-2.5-flash"

if not VK_TOKEN or not AI_API_KEY:
    raise SystemExit("Не найдены VK_TOKEN или AI_API_KEY. Проверьте файл .env")

# Подключение к ВКонтакте
vk_session = vk_api.VkApi(token=VK_TOKEN)
longpoll = VkLongPoll(vk_session)
vk = vk_session.get_api()
