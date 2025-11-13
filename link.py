import asyncio
import logging
import random
import string
import json
import os
from aiogram import Bot, Dispatcher, types
from aiogram import F
from aiogram.filters import Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage

from Database.database import db

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Токен бота
BOT_TOKEN = "7962335034:AAE5qGHa1TUvwy5XjYwrg5GMzwcQ6eoIQMY"

# ID администратора (замените на ваш Telegram ID)
ADMIN_IDS = [7249489180]  # Замените на ваш ID

# Инициализация бота
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Фильтр для проверки администратора
def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

# Состояния
class BindStates(StatesGroup):
    waiting_for_code = State()
    confirm_unbind = State()

class OfferStates(StatesGroup):
    waiting_for_offer_data = State()

class ExchangeStates(StatesGroup):
    waiting_for_exchange_choice = State()
    confirming_exchange = State()

# Генерация кода загрузки
def generate_load_code():
    """Генерация 8-значного кода из цифр и букв"""
    characters = string.ascii_uppercase + string.digits
    return ''.join(random.choices(characters, k=8))

# Команда /start
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    existing_bind = db.get_bind_by_telegram_id(message.from_user.id)
    
    if existing_bind:
        await message.answer(
            f"✅ Ваш аккаунт уже привязан!\n"
            f"👤 Игрок: {existing_bind['player_name']}\n"
            f"🎮 ID: {existing_bind['game_low_id']}\n\n"
            f"Используйте /load для загрузки аккаунта в игре"
        )
    else:
        await message.answer(
            "👋 Добро пожаловать! Используйте /bind для привязки аккаунта."
        )

# Команда /bind
@dp.message(Command("bind"))
async def cmd_bind(message: types.Message, state: FSMContext):
    existing_bind = db.get_bind_by_telegram_id(message.from_user.id)
    
    if existing_bind:
        await message.answer("❌ У вас уже есть привязанный аккаунт!")
        return
    
    await message.answer(
        "🔗 Введите 5-значный код привязки из игры:\n\n"
        "📝 *Как получить код:*\n"
        "1. Зайдите в игру\n"
        "2. Откройте чат клуба\n"
        "3. Введите команду /code\n"
        "4. Скопируйте полученный код и пришлите его сюда\n\n")
    await state.set_state(BindStates.waiting_for_code)

# Обработка кода
@dp.message(BindStates.waiting_for_code)
async def process_code(message: types.Message, state: FSMContext):
    code = message.text.strip()
    
    if not code.isdigit() or len(code) != 5:
        await message.answer("❌ Неверный формат! Введите 5 цифр:")
        return
    
    if code == "00000" or code == "0":
        await message.answer("❌ Этот код недействителен!")
        await state.clear()
        return
    
    account = db.get_account_by_code(code)
    if not account:
        await message.answer("❌ Аккаунт не найден!")
        await state.clear()
        return
    
    # Проверяем, есть ли поле lowID в аккаунте
    if 'lowID' not in account:
        await message.answer("❌ Ошибка: у аккаунта нет ID!")
        await state.clear()
        return
    
    # Создаем привязку
    db.create_bind(
        message.from_user.id,
        account['lowID'],
        account.get('name', 'Unknown'),
        code
    )
    db.update_account_code(account['lowID'], "00000")
    
    await message.answer(
        f"✅ Аккаунт {account.get('name', 'Unknown')} привязан!\n"
        f"/profile - посмотреть профиль\n"
        f"/load - загрузить аккаунт в игре"
    )
    await state.clear()

@dp.message(Command("profile"))
async def cmd_profile(message: types.Message):
    existing_bind = db.get_bind_by_telegram_id(message.from_user.id)
    
    if not existing_bind:
        await message.answer("❌ Нет привязанного аккаунта!")
        return
    
    account = db.get_account_by_low_id(existing_bind['game_low_id'])
    event_profile = db.get_event_profile(message.from_user.id)
    
    if account:
        # Получаем данные о трофеях
        current_trophies = account.get('trophies', 0)
        highest_trophies = account.get('highesttrophies', 0)
        
        # Рассчитываем сброс сезона
        season_reset_data = calculate_season_reset(account)
        
        # Информация о конфетах
        candies_info = ""
        if event_profile:
            candies_info = f"🍬 Конфеты: {event_profile['candies']}\n"
        
        text = (
            f"👤 Профиль:\n"
            f"Имя: {account.get('name', 'Unknown')}\n"
            f"ID: {account.get('lowID', 'N/A')}\n"
            f"{candies_info}"
            f"🏆 Трофеи: {current_trophies}\n"
            f"🏆 Макс. трофеев: {highest_trophies}\n"
            f"⭐ Звездные очки: {account.get('starpoints', 0)}\n"
            f"💎 Гемы: {account.get('gems', 0)}\n"
            f"🪙 Золото: {account.get('gold', 0)}\n"
            f"🎫 Билеты: {account.get('tickets', 0)}\n\n"
            f"🔄 Сброс сезона:\n"
            f"• Сбросится трофеев: {season_reset_data['trophies_reset']}\n"
            f"• Получите звездных очков: {season_reset_data['starpoints_gained']}\n"
            f"• Новое кол-во трофеев: {season_reset_data['new_total_trophies']}\n\n"
            f"🎃 /event_profile - профиль события\n"
            f"💎 /exchange_candies - обмен конфет\n"
            f"Используйте /load для загрузки аккаунта в игре"
        )
    else:
        text = "❌ Ошибка загрузки данных"
    
    await message.answer(text)

def calculate_season_reset(account):
    """
    Функция для расчета сброса сезона
    Возвращает словарь с данными о сбросе
    """
    starpoints = 0
    new_all_trophies = 0
    brawler_trophies = account.get("brawlersTrophies", {})
    
    for brawler_id, trophies in brawler_trophies.items():
        if 550 <= trophies <= 599:
            new_brawler_trophies = 549
            starpoints_gained = 70
        elif 600 <= trophies <= 649:
            new_brawler_trophies = 599
            starpoints_gained = 90
        elif 650 <= trophies <= 699:
            new_brawler_trophies = 649
            starpoints_gained = 110
        elif 700 <= trophies <= 749:
            new_brawler_trophies = 699
            starpoints_gained = 130
        elif 750 <= trophies <= 799:
            new_brawler_trophies = 749
            starpoints_gained = 150
        elif 800 <= trophies <= 849:
            new_brawler_trophies = 799
            starpoints_gained = 170
        elif 850 <= trophies <= 899:
            new_brawler_trophies = 849
            starpoints_gained = 190
        elif 900 <= trophies <= 949:
            new_brawler_trophies = 899
            starpoints_gained = 210
        elif 950 <= trophies <= 999:
            new_brawler_trophies = 949
            starpoints_gained = 230
        elif 1000 <= trophies <= 1049:
            new_brawler_trophies = 999
            starpoints_gained = 250
        elif 1050 <= trophies <= 1099:
            new_brawler_trophies = 1049
            starpoints_gained = 260
        elif 1100 <= trophies <= 1149:
            new_brawler_trophies = 1099
            starpoints_gained = 270
        elif 1150 <= trophies <= 1199:
            new_brawler_trophies = 1149
            starpoints_gained = 280
        elif trophies >= 1200:
            new_brawler_trophies = 1199
            starpoints_gained = 300
        else:
            new_brawler_trophies = trophies
            starpoints_gained = 0
        
        new_all_trophies += new_brawler_trophies
        starpoints += starpoints_gained
    
    current_total_trophies = account.get('trophies', 0)
    trophies_reset = current_total_trophies - new_all_trophies
    
    return {
        'trophies_reset': trophies_reset,
        'starpoints_gained': starpoints,
        'new_total_trophies': new_all_trophies
    }

# Команда /load
@dp.message(Command("load"))
async def cmd_load(message: types.Message):
    existing_bind = db.get_bind_by_telegram_id(message.from_user.id)
    
    if not existing_bind:
        await message.answer("❌ Нет привязанного аккаунта!")
        return
    
    # Очищаем старые коды
    db.cleanup_expired_codes()
    
    # Генерируем код загрузки
    load_code = generate_load_code()
    
    # Сохраняем код в БАЗЕ ДАННЫХ вместо памяти
    db.create_load_code(
        load_code=load_code,
        telegram_id=message.from_user.id,
        game_low_id=existing_bind['game_low_id'],
        player_name=existing_bind['player_name']
    )
    
    await message.answer(
        f"🔑 Код для загрузки аккаунта:\n\n"
        f"`{load_code}`\n\n"
        f"📝 *Как использовать:*\n"
        f"1. Зайдите в игру\n"
        f"2. Откройте чат клуба\n"
        f"3. Введите команду:\n"
        f"`/load {load_code}`\n\n"
        f"⚠️ *Внимание:*\n"
        f"• Код действителен 10 минут\n"
        f"• После использования код станет недействительным\n"
        f"• Текущий игровой аккаунт будет заменен на привязанный"
    )

@dp.message(Command("unbind"))
async def cmd_unbind(message: types.Message, state: FSMContext):
    existing_bind = db.get_bind_by_telegram_id(message.from_user.id)
    
    if not existing_bind:
        await message.answer("❌ Нет привязанного аккаунта!")
        return
    
    await message.answer(
        f"⚠️ Вы уверены, что хотите отвязать и УДАЛИТЬ аккаунт?\n\n"
        f"👤 Игрок: {existing_bind['player_name']}\n"
        f"🎮 ID: {existing_bind['game_low_id']}\n\n"
        f"❌ Это действие НЕОБРАТИМО - аккаунт будет полностью удален!\n\n"
        f"Для подтверждения введите 'ДА' или /cancel для отмены:"
    )
    await state.set_state(BindStates.confirm_unbind)

# Подтверждение отвязки
@dp.message(BindStates.confirm_unbind)
async def process_unbind(message: types.Message, state: FSMContext):
    if message.text.upper() == 'ДА':
        existing_bind = db.get_bind_by_telegram_id(message.from_user.id)
        
        if existing_bind:
            # УДАЛЯЕМ АККАУНТ ИЗ БАЗЫ ДАННЫХ
            from pymongo import MongoClient
            client = MongoClient("localhost")
            db_client = client['jevilv24']
            accounts_collection = db_client['acc']
            
            # Удаляем аккаунт по lowID
            delete_result = accounts_collection.delete_one({'lowID': existing_bind['game_low_id']})
            
            # Удаляем привязку
            db.delete_bind(message.from_user.id)
            
            if delete_result.deleted_count > 0:
                await message.answer(
                    "✅ Аккаунт успешно отвязан и УДАЛЕН!\n"
                    "Вы можете привязать новый аккаунт командой /bind"
                )
            else:
                await message.answer(
                    "⚠️ Аккаунт отвязан, но не удален (не найден в базе)!\n"
                    "Вы можете привязать новый аккаунт командой /bind"
                )
        else:
            await message.answer("❌ Аккаунт не найден!")
    else:
        await message.answer("❌ Отвязка отменена")
    
    await state.clear()

# Команда /new_offer для администратора
@dp.message(Command("new_offer"))
async def cmd_new_offer(message: types.Message, state: FSMContext):
    # Проверка прав администратора
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав для выполнения этой команды!")
        return
    
    if len(message.text.split()) < 2:
        await message.answer(
            '📝 Используйте команду /new_offer с аргументами в формате:\n'
            '<code>/new_offer ID OfferTitle Cost Multiplier BrawlerID SkinID OfferBGR ShopType ShopDisplay</code>\n\n'
            'Или просто отправьте /new_offer для ввода данных пошагово',
            parse_mode='HTML'
        )
        return
    
    try:
        offer_data = message.text.split()
        
        # Проверяем количество аргументов
        if len(offer_data) != 10:
            await message.answer(
                '❌ Неверное количество аргументов! Должно быть 9 параметров:\n'
                'ID, OfferTitle, Cost, Multiplier, BrawlerID, SkinID, OfferBGR, ShopType, ShopDisplay'
            )
            return
        
        new_offer = {
            'ID': [int(offer_data[1]), 0, 0, 0],
            'OfferTitle': offer_data[2],
            'Cost': int(offer_data[3]),
            'OldCost': 0,
            'Multiplier': [int(offer_data[4]), 0, 0, 0],
            'BrawlerID': [int(offer_data[5]), 0, 0, 0],
            'SkinID': [int(offer_data[6]), 0, 0, 0],
            'WhoBuyed': [],
            'Timer': 86400,
            'OfferBGR': offer_data[7],
            'ShopType': int(offer_data[8]),
            'ShopDisplay': int(offer_data[9])
        }
        
        # Проверяем существование файла
        if not os.path.exists('JSON/offers.json'):
            # Создаем директорию если не существует
            os.makedirs('JSON', exist_ok=True)
            offers = {}
        else:
            with open('JSON/offers.json', 'r', encoding='utf-8') as f:
                offers = json.load(f)
        
        # Добавляем новое предложение
        offers[str(len(offers))] = new_offer
        
        # Сохраняем в файл
        with open('JSON/offers.json', 'w', encoding='utf-8') as f:
            json.dump(offers, f, indent=4, ensure_ascii=False)
        
        await message.answer('✅ Новая акция успешно добавлена!')
        
    except ValueError as e:
        await message.answer(f'❌ Ошибка в числовых значениях: {e}')
    except Exception as e:
        await message.answer(f'❌ Произошла ошибка: {e}')

# Альтернативная версия с пошаговым вводом
@dp.message(Command("new_offer_step"))
async def cmd_new_offer_step(message: types.Message, state: FSMContext):
    # Проверка прав администратора
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав для выполнения этой команды!")
        return
    
    await message.answer(
        "📝 Давайте создадим новую акцию пошагово!\n\n"
        "Введите ID акции (число):"
    )
    await state.set_state(OfferStates.waiting_for_offer_data)
    await state.update_data(step=1)

# Обработчик пошагового ввода данных акции
@dp.message(OfferStates.waiting_for_offer_data)
async def process_offer_data(message: types.Message, state: FSMContext):
    data = await state.get_data()
    step = data.get('step', 1)
    offer_data = data.get('offer_data', {})
    
    try:
        if step == 1:
            offer_data['ID'] = [int(message.text), 0, 0]
            await message.answer("Введите название акции:")
            await state.update_data(step=2, offer_data=offer_data)
            
        elif step == 2:
            offer_data['OfferTitle'] = message.text
            await message.answer("Введите стоимость (число):")
            await state.update_data(step=3, offer_data=offer_data)
            
        elif step == 3:
            offer_data['Cost'] = int(message.text)
            offer_data['OldCost'] = 0
            await message.answer("Введите множитель (число):")
            await state.update_data(step=4, offer_data=offer_data)
            
        elif step == 4:
            offer_data['Multiplier'] = [int(message.text), 0, 0]
            await message.answer("Введите ID бравлера (число):")
            await state.update_data(step=5, offer_data=offer_data)
            
        elif step == 5:
            offer_data['BrawlerID'] = [int(message.text), 0, 0]
            await message.answer("Введите ID скина (число):")
            await state.update_data(step=6, offer_data=offer_data)
            
        elif step == 6:
            offer_data['SkinID'] = [int(message.text), 0, 0]
            offer_data['WhoBuyed'] = []
            offer_data['Timer'] = 86400
            await message.answer("Введите фон акции:")
            await state.update_data(step=7, offer_data=offer_data)
            
        elif step == 7:
            offer_data['OfferBGR'] = message.text
            await message.answer("Введите тип магазина (число):")
            await state.update_data(step=8, offer_data=offer_data)
            
        elif step == 8:
            offer_data['ShopType'] = int(message.text)
            await message.answer("Введите отображение в магазине (число):")
            await state.update_data(step=9, offer_data=offer_data)
            
        elif step == 9:
            offer_data['ShopDisplay'] = int(message.text)
            
            # Сохраняем акцию
            if not os.path.exists('JSON/offers.json'):
                os.makedirs('JSON', exist_ok=True)
                offers = {}
            else:
                with open('JSON/offers.json', 'r', encoding='utf-8') as f:
                    offers = json.load(f)
            
            offers[str(len(offers))] = offer_data
            
            with open('JSON/offers.json', 'w', encoding='utf-8') as f:
                json.dump(offers, f, indent=4, ensure_ascii=False)
            
            await message.answer('✅ Новая акция успешно добавлена через пошаговый ввод!')
            await state.clear()
            
    except ValueError:
        await message.answer("❌ Пожалуйста, введите корректное число!")
    except Exception as e:
        await message.answer(f'❌ Произошла ошибка: {e}')
        await state.clear()

# Команда для просмотра всех акций (только для админа)
@dp.message(Command("show_offers"))
async def cmd_show_offers(message: types.Message):
    # Проверка прав администратора
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав для выполнения этой команды!")
        return
    
    try:
        if not os.path.exists('JSON/offers.json'):
            await message.answer("📭 Файл с акциями не найден!")
            return
        
        with open('JSON/offers.json', 'r', encoding='utf-8') as f:
            offers = json.load(f)
        
        if not offers:
            await message.answer("📭 Акций нет!")
            return
        
        response = "📋 Список акций:\n\n"
        for key, offer in offers.items():
            response += f"🔹 Акция {key}:\n"
            response += f"   ID: {offer['ID'][0]}\n"
            response += f"   Название: {offer['OfferTitle']}\n"
            response += f"   Стоимость: {offer['Cost']}\n"
            response += f"   Множитель: {offer['Multiplier'][0]}\n"
            response += f"   ID бравлера: {offer['BrawlerID'][0]}\n"
            response += f"   ID скина: {offer['SkinID'][0]}\n"
            response += f"   Тип магазина: {offer['ShopType']}\n\n"
        
        # Разбиваем сообщение если оно слишком длинное
        if len(response) > 4000:
            parts = [response[i:i+4000] for i in range(0, len(response), 4000)]
            for part in parts:
                await message.answer(part)
        else:
            await message.answer(response)
            
    except Exception as e:
        await message.answer(f'❌ Ошибка при чтении акций: {e}')

# Команда для удаления акции (только для админа)
@dp.message(Command("delete_offer"))
async def cmd_delete_offer(message: types.Message):
    # Проверка прав администратора
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав для выполнения этой команды!")
        return
    
    try:
        if not os.path.exists('JSON/offers.json'):
            await message.answer("📭 Файл с акциями не найден!")
            return
        
        args = message.text.split()
        if len(args) != 2:
            await message.answer("❌ Используйте: /delete_offer <номер_акции>")
            return
        
        offer_key = args[1]
        
        with open('JSON/offers.json', 'r', encoding='utf-8') as f:
            offers = json.load(f)
        
        if offer_key not in offers:
            await message.answer(f"❌ Акция с номером {offer_key} не найдена!")
            return
        
        # Удаляем акцию
        del offers[offer_key]
        
        # Переиндексируем ключи
        new_offers = {}
        for i, (key, offer) in enumerate(offers.items()):
            new_offers[str(i)] = offer
        
        with open('JSON/offers.json', 'w', encoding='utf-8') as f:
            json.dump(new_offers, f, indent=4, ensure_ascii=False)
        
        await message.answer(f"✅ Акция {offer_key} успешно удалена!")
        
    except Exception as e:
        await message.answer(f'❌ Ошибка при удалении акции: {e}')

# СИСТЕМА СОБЫТИЙ С КОНФЕТАМИ

# Команда /event_profile
@dp.message(Command("event_profile"))
async def cmd_event_profile(message: types.Message):
    """Профиль события с конфетами"""
    event_profile = db.get_event_profile(message.from_user.id)
    
    if not event_profile:
        db.create_event_profile(message.from_user.id)
        event_profile = db.get_event_profile(message.from_user.id)
    
    # Получаем привязанный аккаунт для отображения имени
    bind_info = db.get_bind_by_telegram_id(message.from_user.id)
    player_name = bind_info['player_name'] if bind_info else "Неизвестный игрок"
    
    text = (
        f"🎃 **Профиль события** 🎃\n"
        f"👤 Игрок: {player_name}\n"
        f"🍬 Текущие конфеты: {event_profile['candies']}\n"
        f"🏆 Максимум было: {event_profile['max_candies']}\n"
        f"💰 Всего собрано: {event_profile['total_earned_candies']}\n\n"
        f"💎 **Обмен конфет:**\n"
        f"• /exchange_candies - обменять конфеты на награды\n"
        f"• /add_candies - добавить конфеты (админ)\n\n"
        f"📊 Всего обменов: {len(event_profile.get('exchange_history', []))}"
    )
    
    await message.answer(text)

# Команда /exchange_candies
@dp.message(Command("exchange_candies"))
async def cmd_exchange_candies(message: types.Message, state: FSMContext):
    """Обмен конфет на награды"""
    event_profile = db.get_event_profile(message.from_user.id)
    
    if not event_profile or event_profile['candies'] == 0:
        await message.answer("❌ У вас нет конфет для обмена!")
        return
    
    text = (
        f"🍬 **Обмен конфет** 🍬\n"
        f"Ваш баланс: {event_profile['candies']} конфет\n\n"
        f"🎁 **Доступные награды:**\n"
        f"1. 💎 170 гемов - 70 конфет\n"
        f"2. 👑 VIP статус - 150 конфет\n"
        f"3. 💎 360 гемов - 150 конфет (если VIP уже есть)\n"
        f"4. 🎫 50 билетов - 40 конфет\n"
        f"5. 🪙 1000 золота - 30 конфет\n"
        f"6. ⭐ 50 звездных очков - 60 конфет\n\n"
        f"Выберите номер награды (1-6):"
    )
    
    await message.answer(text)
    await state.set_state(ExchangeStates.waiting_for_exchange_choice)

# Обработка выбора обмена
@dp.message(ExchangeStates.waiting_for_exchange_choice)
async def process_exchange_choice(message: types.Message, state: FSMContext):
    try:
        choice = int(message.text.strip())
        if choice < 1 or choice > 6:
            await message.answer("❌ Выберите номер от 1 до 6!")
            return
        
        event_profile = db.get_event_profile(message.from_user.id)
        if not event_profile:
            await message.answer("❌ Ошибка профиля!")
            await state.clear()
            return
        
        # Определяем награды и стоимость
        rewards = {
            1: {"type": "gems", "amount": 170, "cost": 70, "name": "170 гемов"},
            2: {"type": "vip", "amount": 1, "cost": 150, "name": "VIP статус"},
            3: {"type": "gems", "amount": 360, "cost": 150, "name": "360 гемов"},
            4: {"type": "tickets", "amount": 50, "cost": 40, "name": "50 билетов"},
            5: {"type": "gold", "amount": 1000, "cost": 30, "name": "1000 золота"},
            6: {"type": "starpoints", "amount": 2500, "cost": 70, "name": "2500 звездных очков"}
        }
        
        selected_reward = rewards[choice]
        
        # Проверяем достаточно ли конфет
        if event_profile['candies'] < selected_reward['cost']:
            await message.answer(f"❌ Недостаточно конфет! Нужно {selected_reward['cost']}, у вас {event_profile['candies']}")
            await state.clear()
            return
        
        # Особые проверки для VIP
        if choice == 2:
            bind_info = db.get_bind_by_telegram_id(message.from_user.id)
            if bind_info:
                account = db.get_account_by_low_id(bind_info['game_low_id'])
                if account and account.get('vip', 0) > 0:
                    await message.answer(
                        "❌ У вас уже есть VIP статус! Выберите вместо этого награду №3 (360 гемов)"
                    )
                    return
        
        # Сохраняем данные в состоянии
        await state.update_data(
            reward_choice=choice,
            reward_data=selected_reward
        )
        
        # Запрос подтверждения
        confirm_text = (
            f"✅ **Подтверждение обмена**\n"
            f"🍬 Вы отдаете: {selected_reward['cost']} конфет\n"
            f"🎁 Вы получаете: {selected_reward['name']}\n\n"
            f"Для подтверждения введите 'ДА', для отмены - 'НЕТ'"
        )
        
        await message.answer(confirm_text)
        await state.set_state(ExchangeStates.confirming_exchange)
        
    except ValueError:
        await message.answer("❌ Пожалуйста, введите число от 1 до 6!")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")
        await state.clear()

# Подтверждение обмена
@dp.message(ExchangeStates.confirming_exchange)
async def process_exchange_confirm(message: types.Message, state: FSMContext):
    user_input = message.text.upper().strip()
    
    if user_input == 'ДА':
        data = await state.get_data()
        reward_choice = data['reward_choice']
        reward_data = data['reward_data']
        
        event_profile = db.get_event_profile(message.from_user.id)
        bind_info = db.get_bind_by_telegram_id(message.from_user.id)
        
        if not event_profile or not bind_info:
            await message.answer("❌ Ошибка: профиль или привязка не найдены!")
            await state.clear()
            return
        
        # Проверяем еще раз достаточно ли конфет
        if event_profile['candies'] < reward_data['cost']:
            await message.answer("❌ Недостаточно конфет!")
            await state.clear()
            return
        
        # Обновляем аккаунт в зависимости от типа награды
        account = db.get_account_by_low_id(bind_info['game_low_id'])
        if not account:
            await message.answer("❌ Игровой аккаунт не найден!")
            await state.clear()
            return
        
        success = False
        reward_description = ""
        
        if reward_data['type'] == 'gems':
            new_gems = account.get('gems', 0) + reward_data['amount']
            db.accounts.update_one(
                {'lowID': bind_info['game_low_id']},
                {'$set': {'gems': new_gems}}
            )
            success = True
            reward_description = f"💎 {reward_data['amount']} гемов"
            
        elif reward_data['type'] == 'vip':
            # Проверяем что VIP еще нет
            if account.get('vip', 0) == 0:
                db.accounts.update_one(
                    {'lowID': bind_info['game_low_id']},
                    {'$set': {'vip': 1}}
                )
                success = True
                reward_description = "👑 VIP статус"
            else:
                await message.answer("❌ У вас уже есть VIP статус!")
                await state.clear()
                return
                
        elif reward_data['type'] == 'tickets':
            new_tickets = account.get('tickets', 0) + reward_data['amount']
            db.accounts.update_one(
                {'lowID': bind_info['game_low_id']},
                {'$set': {'tickets': new_tickets}}
            )
            success = True
            reward_description = f"🎫 {reward_data['amount']} билетов"
            
        elif reward_data['type'] == 'gold':
            new_gold = account.get('gold', 0) + reward_data['amount']
            db.accounts.update_one(
                {'lowID': bind_info['game_low_id']},
                {'$set': {'gold': new_gold}}
            )
            success = True
            reward_description = f"🪙 {reward_data['amount']} золота"
            
        elif reward_data['type'] == 'starpoints':
            new_starpoints = account.get('starpoints', 0) + reward_data['amount']
            db.accounts.update_one(
                {'lowID': bind_info['game_low_id']},
                {'$set': {'starpoints': new_starpoints}}
            )
            success = True
            reward_description = f"⭐ {reward_data['amount']} звездных очков"
        
        if success:
            # Списание конфет и запись в историю
            db.update_event_candies(
                message.from_user.id, 
                event_profile['candies'] - reward_data['cost']
            )
            db.add_exchange_record(
                message.from_user.id,
                reward_data['type'],
                reward_data['cost'],
                reward_description
            )
            
            await message.answer(
                f"🎉 **Обмен успешно выполнен!**\n"
                f"🍬 Списано: {reward_data['cost']} конфет\n"
                f"🎁 Получено: {reward_description}\n\n"
                f"Остаток конфет: {event_profile['candies'] - reward_data['cost']}"
            )
        else:
            await message.answer("❌ Ошибка при выполнении обмена!")
            
    elif user_input == 'НЕТ':
        await message.answer("❌ Обмен отменен.")
    else:
                await message.answer("❌ Введите 'ДА' или 'НЕТ' для подтверждения.")
    return
    
    await state.clear()

# Команда для добавления конфет (только для админа)
@dp.message(Command("add_candies"))
async def cmd_add_candies(message: types.Message):
    """Добавить конфеты пользователю (админ)"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав для выполнения этой команды!")
        return
    
    try:
        args = message.text.split()
        if len(args) != 3:
            await message.answer(
                "❌ Используйте: /add_candies <user_id> <amount>\n"
                "Пример: /add_candies 123456789 50"
            )
            return
        
        target_user_id = int(args[1])
        amount = int(args[2])
        
        if amount <= 0:
            await message.answer("❌ Количество должно быть положительным!")
            return
        
        db.add_event_candies(target_user_id, amount)
        
        # Получаем обновленный профиль для отображения
        profile = db.get_event_profile(target_user_id)
        
        await message.answer(
            f"✅ Добавлено {amount} конфет пользователю {target_user_id}\n"
            f"🍬 Новый баланс: {profile['candies']} конфет\n"
            f"🏆 Максимум: {profile['max_candies']} конфет"
        )
        
    except ValueError:
        await message.answer("❌ Неверный формат! user_id и amount должны быть числами.")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")

# Команда для просмотра истории обменов
@dp.message(Command("exchange_history"))
async def cmd_exchange_history(message: types.Message):
    """История обменов конфет"""
    event_profile = db.get_event_profile(message.from_user.id)
    
    if not event_profile or not event_profile.get('exchange_history'):
        await message.answer("📭 У вас еще не было обменов!")
        return
    
    history = event_profile['exchange_history'][-10:]  # Последние 10 обменов
    
    text = "📊 **История обменов:**\n\n"
    for i, record in enumerate(reversed(history), 1):
        date = record['date'].strftime("%d.%m.%Y %H:%M")
        text += f"{i}. {date}\n"
        text += f"   🍬 -{record['cost']} | 🎁 {record['reward']}\n\n"
    
    await message.answer(text)

# Команда для просмотра топа по конфетам
@dp.message(Command("candies_top"))
async def cmd_candies_top(message: types.Message):
    """Топ пользователей по конфетам"""
    top_users = db.get_top_candies(limit=10)
    
    if not top_users:
        await message.answer("📭 Пока нет данных о конфетах!")
        return
    
    text = "🏆 **Топ по конфетам:**\n\n"
    
    for i, user in enumerate(top_users, 1):
        # Получаем имя игрока из привязки
        bind_info = db.get_bind_by_telegram_id(user['telegram_id'])
        player_name = bind_info['player_name'] if bind_info else f"ID: {user['telegram_id']}"
        
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
        text += f"{medal} {player_name} - {user['candies']} 🍬\n"
    
    # Добавляем статистику
    stats = db.get_total_candies_statistics()
    text += f"\n📊 Всего конфет в системе: {stats['total_candies']}"
    text += f"\n👥 Игроков с конфетами: {stats['total_users']}"
    
    await message.answer(text)

# Команда для сброса конфет (только для админа)
@dp.message(Command("reset_candies"))
async def cmd_reset_candies(message: types.Message):
    """Сбросить конфеты пользователю (админ)"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав для выполнения этой команды!")
        return
    
    try:
        args = message.text.split()
        if len(args) != 2:
            await message.answer("❌ Используйте: /reset_candies <user_id>")
            return
        
        target_user_id = int(args[1])
        
        # Сбрасываем конфеты к 0
        db.update_event_candies(target_user_id, 0)
        
        await message.answer(f"✅ Конфеты пользователя {target_user_id} сброшены к 0")
        
    except ValueError:
        await message.answer("❌ Неверный формат! user_id должен быть числом.")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")

# Команда для просмотра статистики конфет (админ)
@dp.message(Command("candies_stats"))
async def cmd_candies_stats(message: types.Message):
    """Статистика по конфетам (админ)"""
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав для выполнения этой команды!")
        return
    
    try:
        stats = db.get_total_candies_statistics()
        
        text = (
            "📊 **Статистика конфет:**\n\n"
            f"🍬 Всего конфет в системе: {stats['total_candies']}\n"
            f"👥 Игроков с конфетами: {stats['total_users']}\n"
            f"📈 Среднее на игрока: {stats['average_candies']:.1f}\n\n"
            f"💎 **Команды управления:**\n"
            f"/add_candies - добавить конфеты\n"
            f"/reset_candies - сбросить конфеты\n"
            f"/candies_top - топ игроков"
        )
        
        await message.answer(text)
        
    except Exception as e:
        await message.answer(f"❌ Ошибка при получении статистики: {e}")

# Команда помощи по системе событий
@dp.message(Command("event_help"))
async def cmd_event_help(message: types.Message, state: FSMContext):
    """Помощь по системе событий"""
    # Сбрасываем состояние на всякий случай
    await state.clear()
    
    text = (
        "🎃 **Система событий с конфетами** 🎃\n\n"
        "🍬 **Основные команды:**\n"
        "/event_profile - ваш профиль события\n"
        "/exchange_candies - обменять конфеты на награды\n"
        "/exchange_history - история обменов\n"
        "/candies_top - топ игроков по конфетам\n\n"
        "💎 **Доступные награды:**\n"
        "• 70 конфет → 170 гемов 💎\n"
        "• 150 конфет → VIP статус 👑\n"
        "• 150 конфет → 360 гемов 💎 (если VIP есть)\n"
        "• 40 конфет → 50 билетов 🎫\n"
        "• 30 конфет → 1000 золота 🪙\n"
        "• 60 конфет → 50 звездных очков ⭐\n\n"
        "⚡ Конфеты можно получать за участие в событиях!"
    )
    
    await message.answer(text)

# Обработка команды /cancel для отмены любых состояний
@dp.message(Command("cancel"))
async def cmd_cancel(message: types.Message, state: FSMContext):
    """Отмена текущего действия"""
    current_state = await state.get_state()
    if current_state is None:
        await message.answer("❌ Нечего отменять!")
        return
    
    # Получаем информацию о текущем состоянии для более информативного сообщения
    state_info = {
        "ExchangeStates:waiting_for_exchange_choice": "выбора награды",
        "ExchangeStates:confirming_exchange": "подтверждения обмена", 
        "BindStates:waiting_for_code": "ввода кода привязки",
        "BindStates:confirm_unbind": "подтверждения отвязки",
        "OfferStates:waiting_for_offer_data": "создания акции"
    }
    
    state_name = state_info.get(str(current_state), "текущего действия")
    
    await state.clear()
    await message.answer(f"✅ {state_name.capitalize()} отменено!")

# Обработка неизвестных команд
@dp.message()
async def unknown_command(message: types.Message):
    """Обработка неизвестных команд"""
    await message.answer(
        "❌ Неизвестная команда!\n"
        "Используйте /start для начала работы\n"
        "/help для списка команд"
    )

# Запуск бота
async def main():
    print("Бот запущен...")
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())