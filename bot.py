import vk_api
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
from vk_api.upload import VkUpload
import json
import sqlite3
import os
import re
import requests
from datetime import datetime

TOKEN = "vk1.a.zVv6ija16FAXIBJa0zsLfkkG0Dv0_bJO6h9-5x7dLSkppU9oW4Sz7j3_DBIlDqojwoEZFtETTDFn-g-rMt1ROWMY4n01honBE2JyhJBzA27UoSwd0K0YZXvx9Wr5sHfxfGYnr1VuRLoikz0NvSF2RK1ZN2MKOBpc5l4a9yYRunXj173LTa2KL2bRhdJhRYsy1gFLCtGvboX4qGDmYIoSDg"
ADMIN = 540672163
GROUP = 228440770

# База данных
if os.path.exists('quests.db'):
    os.remove('quests.db')

conn = sqlite3.connect('quests.db', check_same_thread=False)
c = conn.cursor()

c.execute('''CREATE TABLE quests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    description TEXT,
    price TEXT,
    photo_id TEXT
)''')

c.execute('''CREATE TABLE bookings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    quest_id INTEGER,
    user_id INTEGER,
    user_name TEXT,
    user_phone TEXT,
    user_date TEXT,
    user_players INTEGER,
    user_level TEXT,
    user_experience TEXT,
    status TEXT DEFAULT 'pending',
    reject_reason TEXT
)''')

c.execute('''CREATE TABLE questions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    question TEXT,
    answered INTEGER DEFAULT 0
)''')

# Добавляем квесты
c.execute("INSERT INTO quests (name, description, price, photo_id) VALUES (?, ?, ?, ?)", 
          ("Полтергейст", "Вы позвонили в 911... Вас ждет 60 минут страха. Нужно выбраться из проклятого дома.", "3000 руб (до 4 чел)", ""))
c.execute("INSERT INTO quests (name, description, price, photo_id) VALUES (?, ?, ?, ?)", 
          ("Секретная лаборатория", "Секретный бункер с жуткими экспериментами. Найдите противоядие за 60 минут.", "3500 руб (до 4 чел)", ""))
conn.commit()

print("Бот запущен")

vk_session = vk_api.VkApi(token=TOKEN)
vk = vk_session.get_api()
longpoll = VkBotLongPoll(vk_session, GROUP)

users = {}

def parse_datetime(date_str):
    try:
        months = {
            'января': 1, 'февраля': 2, 'марта': 3, 'апреля': 4, 'мая': 5, 'июня': 6,
            'июля': 7, 'августа': 8, 'сентября': 9, 'октября': 10, 'ноября': 11, 'декабря': 12
        }
        parts = date_str.split()
        day = int(parts[0])
        month = months[parts[1].lower()]
        time_parts = parts[2].split(':')
        hour = int(time_parts[0])
        minute = int(time_parts[1])
        year = datetime.now().year
        return datetime(year, month, day, hour, minute)
    except:
        return None

def is_time_slot_available(date_str, quest_id):
    new_time = parse_datetime(date_str)
    if not new_time:
        return True
    
    c.execute("SELECT user_date FROM bookings WHERE quest_id=? AND status='approved'", (quest_id,))
    approved_bookings = c.fetchall()
    
    for booking in approved_bookings:
        booked_time = parse_datetime(booking[0])
        if booked_time:
            diff_hours = abs((new_time - booked_time).total_seconds() / 3600)
            if diff_hours < 1:
                return False
    return True

def get_quest_name_by_id(quest_id):
    c.execute("SELECT name FROM quests WHERE id=?", (quest_id,))
    result = c.fetchone()
    return result[0] if result else "Неизвестный квест"

def upload_photo_from_computer(file_path, group_id):
    try:
        upload_server = vk.photos.getMessagesUploadServer(group_id=group_id)
        upload_url = upload_server['upload_url']
        with open(file_path, 'rb') as photo_file:
            files = {'photo': photo_file}
            response = requests.post(upload_url, files=files).json()
        photo_data = vk.photos.saveMessagesPhoto(
            photo=response['photo'],
            server=response['server'],
            hash=response['hash']
        )[0]
        return f"photo{photo_data['owner_id']}_{photo_data['id']}"
    except Exception as e:
        print(f"Ошибка загрузки фото: {e}")
        return None

def send(user_id, text, kb=None, photo=None):
    try:
        if photo:
            vk.messages.send(user_id=user_id, message=text, random_id=0, attachment=photo, keyboard=json.dumps(kb) if kb else None)
        else:
            vk.messages.send(user_id=user_id, message=text, random_id=0, keyboard=json.dumps(kb) if kb else None)
    except Exception as e:
        print(f"Ошибка: {e}")

def validate_phone(phone):
    phone = phone.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    return re.match(r'^\+7\d{10}$', phone) is not None

def validate_date(date_str):
    return re.match(r'^\d{1,2}\s+[а-яА-Я]+\s+\d{1,2}:\d{2}$', date_str) is not None

def validate_players(players):
    try:
        num = int(players)
        return 2 <= num <= 10
    except:
        return False

def get_quest_by_name(name):
    c.execute("SELECT id, name, description, price, photo_id FROM quests WHERE name=?", (name,))
    return c.fetchone()

def cancel_action(user):
    """Отменяет текущее действие пользователя"""
    if user in users:
        del users[user]
    return True

def main_menu():
    return {
        "buttons": [
            [{"action": {"type": "text", "label": "Квесты"}}],
            [{"action": {"type": "text", "label": "Цены"}}],
            [{"action": {"type": "text", "label": "Вопрос админу"}}]
        ]
    }

def cancel_keyboard():
    return {
        "buttons": [
            [{"action": {"type": "text", "label": "❌ Отмена"}}]
        ]
    }

def quests_menu():
    c.execute("SELECT name FROM quests")
    quests = c.fetchall()
    buttons = []
    for q in quests:
        buttons.append([{"action": {"type": "text", "label": q[0]}}])
    buttons.append([{"action": {"type": "text", "label": "Назад"}}])
    return {"buttons": buttons}

def level_menu():
    return {
        "buttons": [
            [{"action": {"type": "text", "label": "Легкий"}}],
            [{"action": {"type": "text", "label": "Средний"}}],
            [{"action": {"type": "text", "label": "Хард"}}],
            [{"action": {"type": "text", "label": "❌ Отмена"}}]
        ]
    }

def admin_menu():
    return {
        "buttons": [
            [{"action": {"type": "text", "label": "Статистика"}}],
            [{"action": {"type": "text", "label": "Список заявок"}}],
            [{"action": {"type": "text", "label": "Список квестов"}}],
            [{"action": {"type": "text", "label": "Список занятых дат"}}],
            [{"action": {"type": "text", "label": "Одобрить заявку"}}],
            [{"action": {"type": "text", "label": "Отклонить заявку"}}],
            [{"action": {"type": "text", "label": "Добавить квест"}}],
            [{"action": {"type": "text", "label": "Удалить квест"}}],
            [{"action": {"type": "text", "label": "Ответить на вопросы"}}],
            [{"action": {"type": "text", "label": "Выход"}}]
        ]
    }

def handle_admin(user, text):
    if user != ADMIN:
        return False
    
    if text == "Статистика":
        c.execute("SELECT COUNT(*) FROM bookings")
        total = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM bookings WHERE status='pending'")
        pending = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM bookings WHERE status='approved'")
        approved = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM bookings WHERE status='rejected'")
        rejected = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM questions WHERE answered=0")
        qs = c.fetchone()[0]
        send(user, f"Статистика:\nВсего заявок: {total}\nОжидают: {pending}\nОдобрено: {approved}\nОтклонено: {rejected}\nВопросов без ответа: {qs}", admin_menu())
        return True
    
    elif text == "Список заявок":
        c.execute("SELECT id, quest_id, user_id, user_name, user_phone, user_date, user_players, user_level, status, reject_reason FROM bookings ORDER BY id DESC LIMIT 10")
        bookings = c.fetchall()
        if not bookings:
            send(user, "Заявок нет", admin_menu())
            return True
        msg = "Последние заявки:\n\n"
        for b in bookings:
            quest_name = get_quest_name_by_id(b[1])
            status_text = "ОЖИДАЕТ" if b[8] == "pending" else "ОДОБРЕНА" if b[8] == "approved" else "ОТКЛОНЕНА"
            msg += f"#{b[0]} | {quest_name}\nИмя: {b[3]} | Тел: {b[4]} | Дата: {b[5]} | {b[6]} чел | {b[7]} | {status_text}\nСсылка: vk.com/id{b[2]}\n"
            if b[9]:
                msg += f"Причина отказа: {b[9]}\n"
            msg += "\n"
        send(user, msg, admin_menu())
        return True
    
    elif text == "Список квестов":
        c.execute("SELECT id, name, price FROM quests")
        quests = c.fetchall()
        if not quests:
            send(user, "Квестов нет", admin_menu())
            return True
        msg = "Список квестов:\n\n"
        for q in quests:
            msg += f"#{q[0]} | {q[1]} | {q[2]}\n"
        send(user, msg, admin_menu())
        return True
    
    elif text == "Список занятых дат":
        c.execute("SELECT id, quest_id, user_date, user_name FROM bookings WHERE status='approved' ORDER BY user_date DESC")
        approved_bookings = c.fetchall()
        if not approved_bookings:
            send(user, "Нет одобренных заявок", admin_menu())
            return True
        msg = "ЗАНЯТЫЕ ДАТЫ:\n\n"
        for b in approved_bookings:
            quest_name = get_quest_name_by_id(b[1])
            msg += f"Квест: {quest_name}\nДата: {b[2]}\nЗаписался: {b[3]}\n\n"
        send(user, msg, admin_menu())
        return True
    
    elif text == "Одобрить заявку":
        users[user] = {'step': 'approve_booking'}
        send(user, "Введите номер заявки для одобрения:", cancel_keyboard())
        return True
    
    elif text == "Отклонить заявку":
        users[user] = {'step': 'reject_booking_get_id'}
        send(user, "Введите номер заявки для отклонения:", cancel_keyboard())
        return True
    
    elif text == "Добавить квест":
        users[user] = {'step': 'add_name'}
        send(user, "Введите название квеста:", cancel_keyboard())
        return True
    
    elif text == "Удалить квест":
        users[user] = {'step': 'delete_quest'}
        send(user, "Введите номер квеста для удаления (можно посмотреть в 'Список квестов'):", cancel_keyboard())
        return True
    
    elif text == "Ответить на вопросы":
        c.execute("SELECT id, user_id, question FROM questions WHERE answered=0")
        qs = c.fetchall()
        if not qs:
            send(user, "Нет новых вопросов", admin_menu())
            return True
        for q in qs:
            send(user, f"Вопрос #{q[0]} от vk.com/id{q[1]}:\n{q[2]}\n\nНапиши 'Ответить на #{q[0]}' чтобы ответить")
        return True
    
    elif text.startswith("Ответить на #"):
        try:
            qid = int(text.split("#")[1])
            users[user] = {'step': 'answer', 'qid': qid}
            send(user, "Введите ответ:", cancel_keyboard())
        except:
            send(user, "Ошибка. Напишите 'Ответить на #1'")
        return True
    
    elif text == "Выход":
        if user in users:
            del users[user]
        send(user, "Выход из админки", main_menu())
        return True
    
    return False

for event in longpoll.listen():
    if event.type == VkBotEventType.MESSAGE_NEW:
        msg = event.object.message
        user = msg['from_id']
        text = msg.get('text', '').strip()
        
        print(f"{user}: {text}")
        
        # ===== ОБРАБОТКА ОТМЕНЫ (самый приоритет) =====
        if text == "❌ Отмена":
            cancel_action(user)
            send(user, "❌ Действие отменено. Главное меню:", main_menu())
            continue
        
        # Админ панель
        if user == ADMIN and text == "Админка":
            send(user, "Админ панель", admin_menu())
            continue
        
        if handle_admin(user, text):
            continue
        
        # Обработка действий админа
        if user == ADMIN and user in users:
            step = users[user].get('step')
            
            if step == 'approve_booking':
                try:
                    bid = int(text)
                    c.execute("SELECT user_id, quest_id, user_date FROM bookings WHERE id=? AND status='pending'", (bid,))
                    booking = c.fetchone()
                    if booking:
                        if is_time_slot_available(booking[2], booking[1]):
                            c.execute("UPDATE bookings SET status='approved' WHERE id=?", (bid,))
                            conn.commit()
                            send(booking[0], f"Ваша заявка #{bid} ОДОБРЕНА! Администратор скоро свяжется с вами.")
                            send(user, f"Заявка #{bid} одобрена!", admin_menu())
                        else:
                            send(user, f"Ошибка! Время {booking[2]} уже занято на этот квест.", admin_menu())
                    else:
                        send(user, f"Заявка #{bid} не найдена.", admin_menu())
                except ValueError:
                    send(user, f"'{text}' - не номер заявки.", admin_menu())
                del users[user]
                continue
            
            elif step == 'reject_booking_get_id':
                try:
                    bid = int(text)
                    c.execute("SELECT user_id FROM bookings WHERE id=? AND status='pending'", (bid,))
                    booking = c.fetchone()
                    if booking:
                        users[user]['bid'] = bid
                        users[user]['step'] = 'reject_booking_get_reason'
                        send(user, "Введите ПРИЧИНУ отклонения:", cancel_keyboard())
                    else:
                        send(user, f"Заявка #{bid} не найдена.", admin_menu())
                        del users[user]
                except ValueError:
                    send(user, f"'{text}' - не номер заявки.", admin_menu())
                    del users[user]
                continue
            
            elif step == 'reject_booking_get_reason':
                bid = users[user]['bid']
                reason = text
                c.execute("SELECT user_id, quest_id FROM bookings WHERE id=?", (bid,))
                booking = c.fetchone()
                if booking:
                    quest_name = get_quest_name_by_id(booking[1])
                    c.execute("UPDATE bookings SET status='rejected', reject_reason=? WHERE id=?", (reason, bid))
                    conn.commit()
                    send(booking[0], f"Заявка #{bid} на квест '{quest_name}' ОТКЛОНЕНА.\nПричина: {reason}\n\nПо вопросам: vk.com/id{ADMIN}")
                    send(user, f"Заявка #{bid} отклонена: {reason}", admin_menu())
                else:
                    send(user, f"Заявка #{bid} не найдена", admin_menu())
                del users[user]
                continue
            
            elif step == 'delete_quest':
                try:
                    qid = int(text)
                    c.execute("SELECT name FROM quests WHERE id=?", (qid,))
                    quest = c.fetchone()
                    if quest:
                        c.execute("DELETE FROM quests WHERE id=?", (qid,))
                        conn.commit()
                        send(user, f"Квест '{quest[0]}' удален!", admin_menu())
                    else:
                        send(user, f"Квест #{qid} не найден.", admin_menu())
                except ValueError:
                    send(user, f"'{text}' - не номер квеста.", admin_menu())
                del users[user]
                continue
        
        # ===== ПРОВЕРЯЕМ СОСТОЯНИЯ =====
        if user in users:
            step = users[user].get('step')
            
            # Добавление квеста
            if step == 'add_name':
                users[user]['name'] = text
                users[user]['step'] = 'add_desc'
                send(user, "Введите описание квеста:", cancel_keyboard())
                continue
            
            if step == 'add_desc':
                users[user]['desc'] = text
                users[user]['step'] = 'add_price'
                send(user, "Введите цену квеста:", cancel_keyboard())
                continue
            
            if step == 'add_price':
                users[user]['price'] = text
                users[user]['step'] = 'add_photo_request'
                send(user, "Отправьте ФОТО для квеста (перетащите картинку):", cancel_keyboard())
                continue
            
            if step == 'add_photo_request':
                if msg.get('attachments'):
                    for attachment in msg['attachments']:
                        if attachment['type'] == 'photo':
                            photo_url = attachment['photo']['sizes'][-1]['url']
                            response = requests.get(photo_url)
                            temp_path = f"temp_{user}.jpg"
                            with open(temp_path, 'wb') as f:
                                f.write(response.content)
                            uploaded_photo = upload_photo_from_computer(temp_path, GROUP)
                            os.remove(temp_path)
                            if uploaded_photo:
                                c.execute("INSERT INTO quests (name, description, price, photo_id) VALUES (?, ?, ?, ?)", 
                                          (users[user]['name'], users[user]['desc'], users[user]['price'], uploaded_photo))
                                conn.commit()
                                send(user, f"Квест {users[user]['name']} добавлен с фото!", admin_menu())
                            else:
                                c.execute("INSERT INTO quests (name, description, price, photo_id) VALUES (?, ?, ?, ?)", 
                                          (users[user]['name'], users[user]['desc'], users[user]['price'], ""))
                                conn.commit()
                                send(user, f"Квест {users[user]['name']} добавлен без фото.", admin_menu())
                            del users[user]
                            break
                    else:
                        send(user, "Не вижу фото. Попробуйте еще раз.", cancel_keyboard())
                else:
                    send(user, "Отправьте ФОТО для квеста", cancel_keyboard())
                continue
            
            # Ответ на вопрос
            if step == 'answer':
                qid = users[user]['qid']
                c.execute("SELECT user_id FROM questions WHERE id=?", (qid,))
                res = c.fetchone()
                if res:
                    send(res[0], f"Ответ администратора:\n{text}")
                    c.execute("UPDATE questions SET answered=1 WHERE id=?", (qid,))
                    conn.commit()
                    send(user, "Ответ отправлен", admin_menu())
                else:
                    send(user, "Вопрос не найден", admin_menu())
                del users[user]
                continue
            
            # Вопрос админу
            if users[user].get('type') == 'question':
                c.execute("INSERT INTO questions (user_id, question) VALUES (?, ?)", (user, text))
                conn.commit()
                send(ADMIN, f"Вопрос от vk.com/id{user}:\n{text}")
                send(user, "Вопрос отправлен. Администратор ответит.", main_menu())
                del users[user]
                continue
            
            # Заполнение формы записи
            if isinstance(step, int):
                if step == 1:
                    users[user]['name'] = text
                    users[user]['step'] = 2
                    send(user, "Введите номер телефона (+7XXXXXXXXXX):", cancel_keyboard())
                    continue
                
                elif step == 2:
                    if validate_phone(text):
                        users[user]['phone'] = text
                        users[user]['step'] = 3
                        send(user, "Введите дату и время (пример: 25 июня 19:00):", cancel_keyboard())
                    else:
                        send(user, "Неверный формат. Введите +7XXXXXXXXXX", cancel_keyboard())
                    continue
                
                elif step == 3:
                    if validate_date(text):
                        quest_id = users[user]['quest_id']
                        if is_time_slot_available(text, quest_id):
                            users[user]['date'] = text
                            users[user]['step'] = 4
                            send(user, "Введите количество человек (от 2 до 10):", cancel_keyboard())
                        else:
                            send(user, f"Время {text} уже занято на этот квест. Выберите другое время:", cancel_keyboard())
                    else:
                        send(user, "Неверный формат. Пример: 25 июня 19:00", cancel_keyboard())
                    continue
                
                elif step == 4:
                    if validate_players(text):
                        users[user]['players'] = int(text)
                        users[user]['step'] = 5
                        send(user, "Выберите уровень сложности:", level_menu())
                    else:
                        send(user, "Неверное количество. От 2 до 10 человек.", cancel_keyboard())
                    continue
                
                elif step == 5:
                    if text in ["Легкий", "Средний", "Хард"]:
                        users[user]['level'] = text
                        users[user]['step'] = 6
                        send(user, "Напишите ваш опыт прохождения квестов:", cancel_keyboard())
                    else:
                        send(user, "Выберите из кнопок: Легкий, Средний, Хард", level_menu())
                    continue
                
                elif step == 6:
                    users[user]['experience'] = text
                    d = users[user]
                    c.execute("INSERT INTO bookings (quest_id, user_id, user_name, user_phone, user_date, user_players, user_level, user_experience, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                              (d['quest_id'], user, d['name'], d['phone'], d['date'], d['players'], d['level'], d['experience'], 'pending'))
                    conn.commit()
                    bid = c.lastrowid
                    quest_name = get_quest_name_by_id(d['quest_id'])
                    admin_msg = f"НОВАЯ ЗАЯВКА #{bid}\nКвест: {quest_name}\nИмя: {d['name']}\nТел: {d['phone']}\nДата: {d['date']}\nЛюдей: {d['players']}\nУровень: {d['level']}\nОпыт: {d['experience']}\nСсылка: vk.com/id{user}"
                    send(ADMIN, admin_msg)
                    send(user, f"Заявка #{bid} принята! Администратор свяжется с вами.", main_menu())
                    del users[user]
                    continue
        
        # ===== ОБЫЧНЫЕ КОМАНДЫ =====
        if text == "Квесты":
            send(user, "Выберите квест:", quests_menu())
        
        elif text == "Цены":
            c.execute("SELECT name, price FROM quests")
            prices = c.fetchall()
            msg = "Цены:\n" + "\n".join([f"{p[0]}: {p[1]}" for p in prices])
            send(user, msg)
        
        elif text == "Вопрос админу":
            users[user] = {'type': 'question'}
            send(user, "Напишите ваш вопрос:", cancel_keyboard())
        
        elif text == "Назад":
            send(user, "Главное меню:", main_menu())
        
        elif text == "Записаться":
            if user in users and 'last_quest' in users[user]:
                quest_id = users[user]['last_quest']['id']
                quest_name = users[user]['last_quest']['name']
            else:
                c.execute("SELECT id, name FROM quests LIMIT 1")
                q = c.fetchone()
                if q:
                    quest_id, quest_name = q
                else:
                    send(user, "Нет доступных квестов")
                    continue
            
            users[user] = {'step': 1, 'quest_id': quest_id, 'quest': quest_name}
            send(user, "Введите ваше имя:", cancel_keyboard())
            continue
        
        else:
            quest = get_quest_by_name(text)
            if quest:
                qid, name, desc, price, photo = quest
                if user not in users:
                    users[user] = {}
                users[user]['last_quest'] = {'id': qid, 'name': name}
                msg = f"{name}\n\n{desc}\n\n{price}\n\nНажмите 'Записаться' для бронирования"
                if photo:
                    send(user, msg, {"buttons": [[{"action": {"type": "text", "label": "Записаться"}}]]}, photo)
                else:
                    send(user, msg, {"buttons": [[{"action": {"type": "text", "label": "Записаться"}}]]})
            else:
                send(user, "Напишите 'Квесты' чтобы начать", main_menu())