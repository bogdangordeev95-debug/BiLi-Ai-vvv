import os
import re
import time
import requests
import vk_api
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
from ddgs import DDGS
from dotenv import load_dotenv

load_dotenv()

# =====================================================================
# НАСТРОЙКИ (ключи берутся из файла .env, в коде их нет)
# =====================================================================
VK_TOKEN = os.getenv("VK_TOKEN")
AI_API_KEY = os.getenv("AI_API_KEY")
GROUP_ID = os.getenv("GROUP_ID")  # ID сообщества без минуса

AI_URL = "https://openrouter.ai/api/v1/chat/completions"
AI_MODEL = "google/gemini-2.5-flash"

# True  - отвечать на каждое сообщение в беседах
# False - только когда зовут по имени, упоминают или отвечают на сообщение бота
ANSWER_ALL_IN_CHATS = False

# Сколько последних сообщений помнить в каждом диалоге (вопросы и ответы вместе)
MAX_HISTORY = 10

if not VK_TOKEN or not AI_API_KEY or not GROUP_ID:
    raise SystemExit("Не найдены VK_TOKEN, AI_API_KEY или GROUP_ID. Проверьте файл .env")

# =====================================================================
# ПОДКЛЮЧЕНИЕ К ВКОНТАКТЕ
# =====================================================================
vk_session = vk_api.VkApi(token=VK_TOKEN)
longpoll = VkBotLongPoll(vk_session, int(GROUP_ID))
vk = vk_session.get_api()

# =====================================================================
# ХАРАКТЕР БИЛИ
# =====================================================================
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
    "5. Беседы: ты можешь находиться в групповых чатах, где пишут много людей. "
    "Сообщения из бесед приходят в виде 'Имя: текст'. Обращайся к человеку по имени, когда это уместно, "
    "и различай собеседников между собой. Отвечай по теме и коротко. Никогда не начинай свой ответ с имени и двоеточия.\n"
    "6. Память: тебе передаётся история последних сообщений диалога. Учитывай её, чтобы понимать вопросы вроде 'а почему?'.\n"
    "7. Формат ответа: пиши сразу текст ответа. Никогда не пиши префиксы вроде 'BiLi: ' или 'Били: '."
)

SEARCH_KEYWORDS = [
    "новости", "погода", "сколько стоит", "курс", "кто такой",
    "что сейчас", "какой сегодня", "почему", "как там",
]

# =====================================================================
# ПАМЯТЬ ДИАЛОГОВ И ИМЕНА (хранится, пока бот запущен)
# =====================================================================
chat_history = {}  # peer_id -> список сообщений
user_names = {}    # user_id -> имя


def remember(peer_id, role, content):
    """Запоминает сообщение и обрезает историю до MAX_HISTORY"""
    history = chat_history.setdefault(peer_id, [])
    history.append({"role": role, "content": content})
    del history[:-MAX_HISTORY]


def get_user_name(user_id):
    """Имя пользователя ВК (с кэшем)"""
    if user_id in user_names:
        return user_names[user_id]
    try:
        name = vk.users.get(user_ids=user_id)[0]["first_name"]
    except Exception as e:
        print(f"[!] Не удалось получить имя {user_id}: {e}")
        name = "Участник"
    user_names[user_id] = name
    return name


# =====================================================================
# ПОИСК В ИНТЕРНЕТЕ
# =====================================================================
def search_internet(query):
    """Поиск свежей информации в интернете"""
    try:
        with DDGS() as ddgs:
            results = [r["body"] for r in ddgs.text(query, max_results=3)]
        return "\n".join(results)
    except Exception as e:
        print(f"[!] Ошибка поиска: {e}")
        return "Не удалось получить свежие данные из сети."


# =====================================================================
# ЗАПРОС К НЕЙРОСЕТИ
# =====================================================================
def ask_bili_ai(peer_id, user_message, author=None):
    """Получает ответ Били от нейросети с учётом истории диалога.
    author - имя собеседника (передаётся в беседах)"""
    internet_data = ""
    lower_msg = user_message.lower()

    if any(word in lower_msg for word in SEARCH_KEYWORDS) or len(user_message) > 20:
        print(f"[~] Били ищет в интернете: {user_message}")
        internet_data = f"\n\n[Информация из интернета для справки]:\n{search_internet(user_message)}"

    # В беседах подписываем, кто именно пишет
    labeled_message = f"{author}: {user_message}" if author else user_message

    headers = {
        "Authorization": f"Bearer {AI_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://vk.com",
        "X-Title": "BiLi Online Bot",
    }

    messages = (
        [{"role": "system", "content": SYSTEM_PROMPT}]
        + chat_history.get(peer_id, [])
        + [{"role": "user", "content": labeled_message + internet_data}]
    )

    data = {
        "model": AI_MODEL,
        "messages": messages,
        "temperature": 0.95,
    }

    try:
        response = requests.post(AI_URL, json=data, headers=headers, timeout=30)
        response.raise_for_status()
        answer = response.json()["choices"][0]["message"]["content"].strip()

        for prefix in ("bili:", "били:"):
            if answer.lower().startswith(prefix):
                answer = answer[len(prefix):].strip()

        # В историю идёт сообщение без интернет-справки, чтобы не раздувать память
        remember(peer_id, "user", labeled_message)
        remember(peer_id, "assistant", answer)
        return answer
    except Exception as e:
        print(f"[!] Ошибка при запросе к нейросети: {e}")
        return "Слушай, у меня тут шестеренки в голове заклинило на секунду... Можешь повторить вопрос?"


# =====================================================================
# ОБРАЩЕНИЕ К БОТУ В БЕСЕДАХ
# =====================================================================
def is_addressed(message):
    """Обратились ли к боту в беседе"""
    text = message.get("text", "").lower()
    reply = message.get("reply_message") or {}
    return (
        re.search(r"\bбили\b|\bbili\b", text) is not None
        or f"club{GROUP_ID}" in text
        or reply.get("from_id") == -int(GROUP_ID)
    )


# =====================================================================
# ГЛАВНЫЙ ЦИКЛ
# =====================================================================
print("[+] Бот BiLi онлайн запущен")
print("[+] Слушаю личные сообщения и беседы ВК...")

while True:
    try:
        for event in longpoll.listen():
            if event.type != VkBotEventType.MESSAGE_NEW:
                continue

            message = event.obj.message
            text = message.get("text", "").strip()
            peer_id = message["peer_id"]
            from_id = message["from_id"]

            # Пропускаем пустые сообщения и сообщения от сообществ
            if not text or from_id < 0:
                continue
                # В беседе отвечаем, если зовут бота (или включён режим "отвечать на всё")
            if event.from_chat and not (ANSWER_ALL_IN_CHATS or is_addressed(message)):
                continue

            # Убираем упоминание бота вида [club123|@bili] из текста
            text = re.sub(r"\[club\d+\|[^\]]*\]", "", text).strip() or "привет"
            print(f"[<-] {peer_id} от {from_id}: {text}")

            # Имя собеседника нужно только в беседах
            author = get_user_name(from_id) if event.from_chat else None

            # 1. Временное сообщение "Секундочку..."
            wait_id = None
            try:
                wait_id = vk.messages.send(
                    peer_id=peer_id,
                    message="Секундочку...",
                    random_id=vk_api.utils.get_random_id(),
                )
            except Exception as e:
                print(f"[!] Не удалось отправить 'Секундочку...': {e}")

            # 2. Ответ нейросети
            answer = ask_bili_ai(peer_id, text, author)[:4000]

            # 3. Заменяем "Секундочку..." ответом (если не вышло, отправляем новым и удаляем старое)
            sent = False
            if wait_id:
                try:
                    vk.messages.edit(peer_id=peer_id, message_id=wait_id, message=answer)
                    sent = True
                except Exception as e:
                    print(f"[!] Не удалось отредактировать: {e}")

            if not sent:
                vk.messages.send(
                    peer_id=peer_id,
                    message=answer,
                    random_id=vk_api.utils.get_random_id(),
                )
                if wait_id:
                    try:
                        vk.messages.delete(message_ids=wait_id, delete_for_all=1)
                    except Exception as e:
                        print(f"[!] Не удалось удалить временное сообщение: {e}")

            print(f"[->] Били ответил в {peer_id}")

    except requests.exceptions.RequestException:
        print("[!] Проблема с сетью. Переподключение через 5 секунд...")
        time.sleep(5)
    except Exception as e:
        print(f"[!!] Непредвиденная ошибка: {e}")
        time.sleep(5)
