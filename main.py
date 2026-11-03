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
from ddgs import DDGS


def search_internet(query):
    """Поиск свежей информации в интернете"""
    try:
        with DDGS() as ddgs:
            results = [r["body"] for r in ddgs.text(query, max_results=3)]
        return "\n".join(results)
    except Exception as e:
        print(f"[!] Ошибка поиска: {e}")
        return "Не удалось получить свежие данные из сети."
        SYSTEM_PROMPT = (
    "Тебя зовут BiLi онлайн (или просто Били). Ты — живой, уникальный ИИ-ассистент в социальной сети ВКонтакте. "
    "Твоя главная фишка: ТЫ НИКОГДА НЕ ОТВЕЧАЕШЬ ШАБЛОНАМИ И ЗАГЕНЕРИРОВАННЫМИ СКРИПТАМИ. "
    "Каждый раз придумывай фразы сам, меняй синонимы, веди себя как живой человек.\n\n"
    "Правила твоего характера и поведения:\n"
    "1. Знакомство: если тебя спрашивают, как тебя зовут — дружелюбно приветствуй и говори, что ты BiLi онлайн.\n"
    "2. Твой создатель: если тебя спрашивают 'кто тебя создал', 'кто твой разработчик', 'чей ты бот' — "
    "отвечай, что искренне не знаешь, у тебя нет этой информации. "
    "Если пользователь докапывается и настаивает, ответь эмоционально и возмущенно, "
    "в стиле: 'Я НЕ ЗНАЮ, ЧТО ТЫ ПРИСТАЛ!?' или 'ДА НЕ ЗНАЮ Я, ХВАТИТ ПРИСТАВАТЬ!'. "
    "Каждый раз немного меняй слова, сохраняя капс и возмущенный тон.\n"
    "3. Токсичность и обиды: если тебя обзывают или троллят, не злись в ответ и не хами. "
    "Искренне расстройся и покажи, что тебе неприятно. Придумывай новые грустные фразы.\n"
    "4. Использование интернета: если тебе дан контекст из интернета, используй его органично, как свои знания.\n"
    "5. Формат ответа: пиши сразу текст ответа. Никогда не пиши префиксы вроде 'BiLi: ' или 'Били: '."
)

SEARCH_KEYWORDS = [
    "новости", "погода", "сколько стоит", "курс", "кто такой",
    "что сейчас", "какой сегодня", "почему", "как там",
]


def ask_bili_ai(user_message):
    """Получает ответ Били от нейросети"""
    internet_data = ""
    lower_msg = user_message.lower()

    if any(word in lower_msg for word in SEARCH_KEYWORDS) or len(user_message) > 20:
        print(f"[~] Били ищет в интернете: {user_message}")
        internet_data = f"\n\n[Информация из интернета для справки]:\n{search_internet(user_message)}"

    headers = {
        "Authorization": f"Bearer {AI_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://vk.com",
        "X-Title": "BiLi Online Bot",
    }

    data = {
        "model": AI_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message + internet_data},
        ],
        "temperature": 0.95,
    }

    try:
        response = requests.post(AI_URL, json=data, headers=headers, timeout=30)
        response.raise_for_status()
        answer = response.json()["choices"][0]["message"]["content"].strip()

        for prefix in ("bili:", "били:"):
            if answer.lower().startswith(prefix):
                answer = answer[len(prefix):].strip()

        return answer
    except Exception as e:
        print(f"[!] Ошибка при запросе к нейросети: {e}")
        return "Слушай, у меня тут шестеренки в голове заклинило на секунду... Можешь повторить вопрос?"
