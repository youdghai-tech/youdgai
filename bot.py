import asyncio
import logging
import os
import re
import subprocess
import cv2
import numpy as np

import aiohttp
import edge_tts
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.types import (
    BotCommand, 
    FSInputFile, 
    InlineKeyboardMarkup, 
    InlineKeyboardButton, 
    CallbackQuery
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiohttp import web
from PIL import Image, ImageEnhance

# Токен берем из переменных окружения или вставляем вручную
BOT_TOKEN = os.getenv("BOT_TOKEN", "8982219315:AAEOfDYPXue_WjtKMs6XDNlH1LGVqL6vWTc")
CHANNEL_URL = "https://t.me/airasleshenia"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Хранилище настроек пользователей (в памяти)
mat_mode = {}  
user_speed = {}  
user_voice = {} 
user_kek_lvl = {}  
user_kek_vol = {}  
user_vid_speed = {}
user_vid_vol = {}

# Доступные голоса
VOICES = {
    "dmitry": ("Дмитрий (Классический 👨)", "ru-RU-DmitryNeural"),
    "svetlana": ("Светлана (Классическая 👩)", "ru-RU-SvetlanaNeural"),
    "andrew": ("Макс (Мультиязычный 👨)", "en-US-AndrewMultilingualNeural"),
    "ava": ("Аня (Мультиязычный 👩)", "en-US-AvaMultilingualNeural"),
}

# --- Вспомогательные функции ---
def is_mat_enabled(user_id: int) -> bool:
    return mat_mode.get(user_id, True)

def get_user_speed(user_id: int) -> str:
    return user_speed.get(user_id, "+0%")

def get_user_voice(user_id: int) -> str:
    return user_voice.get(user_id, "ru-RU-DmitryNeural")

def get_kek_lvl(user_id: int) -> int:
    return user_kek_lvl.get(user_id, 3) 

def get_kek_vol(user_id: int) -> int:
    return user_kek_vol.get(user_id, 1) 

class KekState(StatesGroup):
    wait_for_video = State()

class ShihState(StatesGroup):
    wait_for_photo = State()

class VidSpeedState(StatesGroup):
    wait_for_video = State()

class VidVolState(StatesGroup):
    wait_for_video = State()

# --- КЛАВИАТУРЫ ---

def get_voice_keyboard():
    buttons = []
    for code, (name, voice_id) in VOICES.items():
        buttons.append([InlineKeyboardButton(text=name, callback_data=f"set_voice:{code}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_kek_lvl_keyboard(current: int):
    buttons = []
    row = []
    for lvl in range(1, 6):
        mark = "✅ " if lvl == current else ""
        row.append(InlineKeyboardButton(text=f"{mark}{lvl}", callback_data=f"set_keklvl:{lvl}"))
    buttons.append(row)
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_kek_vol_keyboard(current: int):
    vols = [1, 2, 5, 10, 20]
    row = []
    for v in vols:
        mark = "✅ " if v == current else ""
        row.append(InlineKeyboardButton(text=f"{mark}x{v}", callback_data=f"set_kekvol:{v}"))
    return InlineKeyboardMarkup(inline_keyboard=[row])

def get_vid_speed_keyboard(current: float):
    speeds = [0.5, 1.0, 1.5, 2.0]
    row = []
    for s in speeds:
        mark = "✅ " if s == current else ""
        row.append(InlineKeyboardButton(text=f"{mark}{s}x", callback_data=f"vidspeed:{s}"))
    return InlineKeyboardMarkup(inline_keyboard=[row])

def get_vid_vol_keyboard(current: int):
    vols = [1, 2, 5, 10, 20]
    row = []
    for v in vols:
        mark = "✅ " if v == current else ""
        row.append(InlineKeyboardButton(text=f"{mark}x{v}", callback_data=f"vidvol:{v}"))
    return InlineKeyboardMarkup(inline_keyboard=[row])

def get_settings_keyboard(user_id: int):
    mat = is_mat_enabled(user_id)
    mat_btn_text = "🔞 Маты: ВКЛ" if mat else "🎩 Маты: ВЫКЛ"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎙 Выбрать голос", callback_data="open_voice_menu")],
        [InlineKeyboardButton(text="📉 Шакальность видео", callback_data="open_keklvl_menu")],
        [InlineKeyboardButton(text="🔊 Громкость видео", callback_data="open_kekvol_menu")],
        [InlineKeyboardButton(text=mat_btn_text, callback_data="toggle_mat_mode")]
    ])
    return keyboard

# =============================================================
# 🛠 БАЗОВЫЕ КОМАНДЫ И НАСТРОЙКИ
# =============================================================

@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear() 
    user_id = message.from_user.id
    mat = is_mat_enabled(user_id)

    promo_text = f"📢 **Подпишитесь на наш канал:** {CHANNEL_URL}\n\n"

    if mat:
        text = f"{promo_text}⚠️ **Режим 18+ включен!** ⚠️\nЯ базарю с матом. Пиши `/help`, чтобы посмотреть команды или загляни в `/settings`."
    else:
        text = f"{promo_text}🎩 **Режим культурного общения включен**\n\nНапиши `/help`, чтобы увидеть список команд или настроек `/settings`."

    await message.answer(text, parse_mode="Markdown", disable_web_page_preview=True)


@dp.message(Command("help"))
async def cmd_help(message: types.Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    mat = is_mat_enabled(user_id)

    help_text = (
        "📖 **Справка по командам:**\n\n"
        "🤪 **Жмых и Шакалы:**\n"
        "• `/shih` — Жмыхнуть фото (можно ответом на фото)\n"
        "• `/kek` — Испортить видео (можно ответом на видео)\n"
        "• `/fry` — Перегрузить аудио/голосовое (ответом на аудио)\n"
        "• `/vidspeed` — Изменить скорость видео\n"
        "• `/vidvol` — Изменить громкость видео\n\n"
        "🎙 **Озвучка:**\n"
        "• `/say <текст>` — Озвучить текст (или ответом на текст)\n"
        "• `/voice` — Меню выбора голоса\n"
        "• `/speed <+-X%>` — Настроить скорость (например: `/speed +20%`)\n\n"
        "⚙️ **Параметры:**\n"
        "• `/settings` — Панель всех настроек бота\n"
        "• `/cancel` — Отменить выбор"
    )

    prefix = "Забыл команды? На, смотри 👇\n\n" if mat else "Вот список доступных команд 👇\n\n"
    await message.answer(prefix + help_text, parse_mode="Markdown")


@dp.message(Command("settings"))
async def cmd_settings(message: types.Message):
    user_id = message.from_user.id
    await message.answer("⚙️ **Панель управления настройками:**", reply_markup=get_settings_keyboard(user_id), parse_mode="Markdown")


@dp.message(Command("stopmat"))
async def cmd_stopmat(message: types.Message):
    mat_mode[message.from_user.id] = False
    await message.answer("✅ **Маты отключены!** 🎩")

@dp.message(Command("startmat"))
async def cmd_startmat(message: types.Message):
    mat_mode[message.from_user.id] = True
    await message.answer("⚠️ **Режим 18+ включен!** Погнали! 😈")

# =============================================================
# ⚙️ ОБРАБОТКА ИНТЕРАКТИВНЫХ МЕНЮ (CALLBACKS)
# =============================================================

@dp.callback_query(F.data == "open_voice_menu")
async def cb_open_voice_menu(call: CallbackQuery):
    await call.message.edit_text("🎙 **Выберите голос для озвучки:**", reply_markup=get_voice_keyboard(), parse_mode="Markdown")
    await call.answer()

@dp.callback_query(F.data.startswith("set_voice:"))
async def cb_set_voice(call: CallbackQuery):
    user_id = call.from_user.id
    code = call.data.split(":")[1]
    if code in VOICES:
        user_voice[user_id] = VOICES[code][1]
        name = VOICES[code][0]
        await call.message.edit_text(f"✅ Голос установлен: **{name}**", parse_mode="Markdown")
    await call.answer()

@dp.callback_query(F.data == "open_keklvl_menu")
async def cb_open_keklvl(call: CallbackQuery):
    user_id = call.from_user.id
    curr = get_kek_lvl(user_id)
    await call.message.edit_text("📉 **Выберите уровень уродства видео (1 — слабо, 5 — жестко):**", reply_markup=get_kek_lvl_keyboard(curr), parse_mode="Markdown")
    await call.answer()

@dp.callback_query(F.data.startswith("set_keklvl:"))
async def cb_set_keklvl(call: CallbackQuery):
    user_id = call.from_user.id
    lvl = int(call.data.split(":")[1])
    user_kek_lvl[user_id] = lvl
    await call.message.edit_text(f"✅ Шакальность видео установлена на: `{lvl}`", parse_mode="Markdown")
    await call.answer()

@dp.callback_query(F.data == "open_kekvol_menu")
async def cb_open_kekvol(call: CallbackQuery):
    user_id = call.from_user.id
    curr = get_kek_vol(user_id)
    await call.message.edit_text("🔊 **Выберите уровень громкости видео:**", reply_markup=get_kek_vol_keyboard(curr), parse_mode="Markdown")
    await call.answer()

@dp.callback_query(F.data.startswith("set_kekvol:"))
async def cb_set_kekvol(call: CallbackQuery):
    user_id = call.from_user.id
    vol = int(call.data.split(":")[1])
    user_kek_vol[user_id] = vol
    await call.message.edit_text(f"💥 Громкость видео выкручена на: `x{vol}`", parse_mode="Markdown")
    await call.answer()

@dp.callback_query(F.data == "toggle_mat_mode")
async def cb_toggle_mat(call: CallbackQuery):
    user_id = call.from_user.id
    mat_mode[user_id] = not is_mat_enabled(user_id)
    await call.message.edit_reply_markup(reply_markup=get_settings_keyboard(user_id))
    await call.answer("Режим мата изменен!")

# =============================================================
# 🎙 ГОЛОС И СКОРОСТЬ (ТЕКСТОВЫЕ КОМАНДЫ)
# =============================================================

@dp.message(Command("voice"))
async def cmd_voice(message: types.Message):
    await message.answer("🎙 **Выберите желаемый голос:**", reply_markup=get_voice_keyboard(), parse_mode="Markdown")

@dp.message(Command("speed"))
async def cmd_speed(message: types.Message):
    user_id = message.from_user.id
    args = message.text.split(maxsplit=1)

    if len(args) < 2:
        current = get_user_speed(user_id)
        await message.reply(f"⚙️ **Текущая скорость:** `{current}`\nУкажите значение: `/speed +20%` или `/speed -15%`", parse_mode="Markdown")
        return

    val = args[1].strip()
    if not val.endswith("%"): val += "%"
    if not val.startswith("+") and not val.startswith("-"): val = "+" + val

    match = re.match(r"^([+-]\d+)%$", val)
    if not match:
        await message.reply("Пример корректного ввода: `/speed +15%`")
        return

    num = int(match.group(1))
    if num < -50 or num > 100:
        await message.reply("Допустимый диапазон: от -50% до +100%.")
        return

    user_speed[user_id] = f"{num:+d}%"
    await message.reply(f"👌 Скорость речи установлена на `{user_speed[user_id]}`!")

# =============================================================
# 🥴 ЖМЫХ КАРТИНКИ (/shih)
# =============================================================

async def process_shih_photo(message: types.Message, photo: types.PhotoSize):
    user_id = message.from_user.id
    mat = is_mat_enabled(user_id)
    
    msg = await message.reply("⏳ Искривляю пространство и жмыхаю... Жди!")
    
    input_path = f"input_shih_{user_id}_{message.message_id}.jpg"
    output_path = f"output_shih_{user_id}_{message.message_id}.jpg"
    
    try:
        file_info = await bot.get_file(photo.file_id)
        await bot.download_file(file_info.file_path, destination=input_path)
        
        img = cv2.imread(input_path)
        rows, cols = img.shape[:2]
        
        cx, cy = cols / 2.0, rows / 2.0
        x = np.arange(cols)
        y = np.arange(rows)
        xx, yy = np.meshgrid(x, y)
        
        dx = xx - cx
        dy = yy - cy
        r = np.sqrt(dx**2 + dy**2)
        r[r == 0] = 1 
        
        radius = max(cx, cy)
        amount = 0.4 
        factor = np.where(r < radius, (r / radius) ** amount, 1.0)
        
        map_x = (cx + dx * factor).astype(np.float32)
        map_y = (cy + dy * factor).astype(np.float32)
        
        distorted = cv2.remap(img, map_x, map_y, interpolation=cv2.INTER_LINEAR)
        
        img_rgb = cv2.cvtColor(distorted, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(img_rgb)
        
        w, h = pil_img.size
        pil_img = pil_img.resize((int(w * 0.85), int(h * 1.15)), Image.BICUBIC)
        
        pil_img = ImageEnhance.Color(pil_img).enhance(4.0)
        pil_img = ImageEnhance.Contrast(pil_img).enhance(3.5)
        pil_img = ImageEnhance.Sharpness(pil_img).enhance(6.0)
        
        pil_img.save(output_path, "JPEG", quality=5)
        
        photo_file = FSInputFile(output_path)
        caption_text = "Готово! 🥴" if not mat else "Ебать лицо всосало 🤣"
        
        await bot.send_chat_action(chat_id=message.chat.id, action="upload_photo")
        await message.reply_photo(photo_file, caption=caption_text)
        
    except Exception as e:
        logging.error(f"Ошибка жмыха: {e}")
        await message.reply("Не удалось обработать картинку.")
    finally:
        await msg.delete()
        if os.path.exists(input_path): os.remove(input_path)
        if os.path.exists(output_path): os.remove(output_path)


@dp.message(Command("shih", "zhmyh"))
async def cmd_shih_start(message: types.Message, state: FSMContext):
    if message.reply_to_message and message.reply_to_message.photo:
        await process_shih_photo(message, message.reply_to_message.photo[-1])
        return

    user_id = message.from_user.id
    mat = is_mat_enabled(user_id)
    
    await state.set_state(ShihState.wait_for_photo)
    await message.reply(
        "🖼 **Отправь мне картинку**, которую хочешь исказить!\n\nДля отмены напиши /cancel",
        parse_mode="Markdown"
    )

@dp.message(Command("cancel"), ShihState.wait_for_photo)
async def cmd_cancel_shih(message: types.Message, state: FSMContext):
    await state.clear()
    await message.reply("✅ Действие отменено.")

@dp.message(ShihState.wait_for_photo, F.photo)
async def handle_shih_photo_state(message: types.Message, state: FSMContext):
    await state.clear() 
    await process_shih_photo(message, message.photo[-1])

# =============================================================
# 🤪 ШАКАЛЬНОЕ ВИДЕО (/kek)
# =============================================================

async def process_kek_video(message: types.Message, video: types.Video):
    user_id = message.from_user.id
    mat = is_mat_enabled(user_id)
    
    if video.file_size > 15 * 1024 * 1024:
        await message.reply("Файл слишком большой! Лимит 15 МБ.")
        return

    msg = await message.reply("⏳ Начинаю шакалить качество... Жди!")
    
    input_path = f"input_{user_id}_{message.message_id}.mp4"
    output_path = f"output_{user_id}_{message.message_id}.mp4"
    
    lvl = get_kek_lvl(user_id)
    vol = get_kek_vol(user_id)
    
    quality_presets = {
        1: ("360", "100k", "24"),
        2: ("240", "50k", "15"),
        3: ("144", "20k", "10"),
        4: ("72", "5k", "5"),
        5: ("36", "1k", "2"),
    }
    width, bitrate, fps = quality_presets[lvl]
    
    try:
        file_info = await bot.get_file(video.file_id)
        await bot.download_file(file_info.file_path, destination=input_path)
        
        command = [
            "ffmpeg", "-y", "-i", input_path,
            "-vf", f"scale={width}:-2",
            "-b:v", bitrate,
            "-r", fps,
            "-c:a", "aac",
            "-b:a", "8k",
            "-ar", "8000",
            "-filter:a", f"volume={vol}",
            output_path
        ]
        
        process = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        
        if process.returncode != 0:
            raise Exception("Ошибка сжатия видео")

        video_file = FSInputFile(output_path)
        caption_text = f"Уровень шакала: {lvl} | Громкость: x{vol}\n\n"
        caption_text += "Качество вышло погулять 🤣" if mat else "Твоё видео готово! 🤪"
        
        await bot.send_chat_action(chat_id=message.chat.id, action="upload_video")
        await message.reply_video(video_file, caption=caption_text)
        
    except Exception as e:
        logging.error(f"Ошибка видео: {e}")
        await message.reply("Не получилось обработать видео.")
    finally:
        await msg.delete()
        if os.path.exists(input_path): os.remove(input_path)
        if os.path.exists(output_path): os.remove(output_path)

@dp.message(Command("kek"))
async def cmd_kek_start(message: types.Message, state: FSMContext):
    if message.reply_to_message and message.reply_to_message.video:
        await process_kek_video(message, message.reply_to_message.video)
        return

    await state.set_state(KekState.wait_for_video)
    await message.reply("🎥 **Отправь мне видео**, которое хочешь ухудшить! (до 15 МБ)\n\nДля отмены напиши /cancel", parse_mode="Markdown")

@dp.message(Command("cancel"), KekState.wait_for_video)
async def cmd_cancel_kek(message: types.Message, state: FSMContext):
    await state.clear()
    await message.reply("✅ Действие отменено.")

@dp.message(KekState.wait_for_video, F.video)
async def handle_kek_video_state(message: types.Message, state: FSMContext):
    await state.clear() 
    await process_kek_video(message, message.video)

# =============================================================
# ⏩ СКОРОСТЬ ВИДЕО (/vidspeed)
# =============================================================

@dp.message(Command("vidspeed", "speedvid"))
async def cmd_vidspeed_start(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    current = user_vid_speed.get(user_id, 1.0)
    
    if message.reply_to_message and message.reply_to_message.video:
        await state.update_data(video_file_id=message.reply_to_message.video.file_id)

    keyboard = get_vid_speed_keyboard(current)
    await message.reply(
        "⏩ **Выбери скорость для видео:**\n(Если не ответил на видео, выбери скорость, а затем отправь видео)",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )
    await state.set_state(VidSpeedState.wait_for_video)

@dp.callback_query(F.data.startswith("vidspeed:"))
async def cb_set_vidspeed(call: CallbackQuery, state: FSMContext):
    speed_val = float(call.data.split(":")[1])
    user_id = call.from_user.id
    user_vid_speed[user_id] = speed_val
    
    data = await state.get_data()
    video_file_id = data.get("video_file_id")

    if not video_file_id and call.message.reply_to_message and call.message.reply_to_message.video:
        video_file_id = call.message.reply_to_message.video.file_id

    if not video_file_id:
        await call.message.edit_text(
            f"✅ Скорость установлена на **{speed_val}x**.\n\nТеперь отправь видео или ответь командой `/vidspeed` прямо на нужное видео!",
            parse_mode="Markdown"
        )
        await call.answer()
        return

    await call.message.edit_text(f"⏳ Меняю скорость видео на {speed_val}x... Жди!")
    
    input_path = f"input_vidspeed_{user_id}.mp4"
    output_path = f"output_vidspeed_{user_id}.mp4"

    try:
        file_info = await bot.get_file(video_file_id)
        await bot.download_file(file_info.file_path, destination=input_path)

        v_pts = 1.0 / speed_val
        if speed_val == 0.5:
            a_filter = "atempo=0.5"
        elif speed_val == 1.5:
            a_filter = "atempo=1.5"
        elif speed_val == 2.0:
            a_filter = "atempo=2.0"
        else:
            a_filter = "atempo=1.0"

        command = [
            "ffmpeg", "-y", "-i", input_path,
            "-filter:v", f"setpts={v_pts}*PTS",
            "-filter:a", a_filter,
            output_path
        ]

        process = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if process.returncode != 0:
            raise Exception("Ошибка обработки видео через ffmpeg")

        video_file = FSInputFile(output_path)
        await call.message.delete()
        await call.message.answer_video(video_file, caption=f"🚀 Скорость видео: {speed_val}x")
        await state.clear()

    except Exception as e:
        logging.error(f"Ошибка скорости видео: {e}")
        await call.message.edit_text("❌ Не удалось изменить скорость видео.")
    finally:
        if os.path.exists(input_path): os.remove(input_path)
        if os.path.exists(output_path): os.remove(output_path)

    await call.answer()

@dp.message(VidSpeedState.wait_for_video, F.video)
async def handle_vidspeed_video_state(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    speed_val = user_vid_speed.get(user_id, 1.0)

    msg = await message.reply(f"⏳ Меняю скорость видео на {speed_val}x... Жди!")
    input_path = f"input_vidspeed_{user_id}.mp4"
    output_path = f"output_vidspeed_{user_id}.mp4"

    try:
        file_info = await bot.get_file(message.video.file_id)
        await bot.download_file(file_info.file_path, destination=input_path)

        v_pts = 1.0 / speed_val
        a_filter = "atempo=0.5" if speed_val == 0.5 else ("atempo=1.5" if speed_val == 1.5 else ("atempo=2.0" if speed_val == 2.0 else "atempo=1.0"))

        command = [
            "ffmpeg", "-y", "-i", input_path,
            "-filter:v", f"setpts={v_pts}*PTS",
            "-filter:a", a_filter,
            output_path
        ]

        process = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if process.returncode != 0:
            raise Exception("Ошибка ffmpeg")

        await message.reply_video(FSInputFile(output_path), caption=f"🚀 Скорость видео: {speed_val}x")
        await state.clear()
    except Exception as e:
        logging.error(f"Ошибка состояния скорости видео: {e}")
        await message.reply("❌ Не удалось обработать видео.")
    finally:
        await msg.delete()
        if os.path.exists(input_path): os.remove(input_path)
        if os.path.exists(output_path): os.remove(output_path)

# =============================================================
# 🔊 ГРОМКОСТЬ ВИДЕО (/vidvol)
# =============================================================

@dp.message(Command("vidvol"))
async def cmd_vidvol_start(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    current = user_vid_vol.get(user_id, 1)
    
    if message.reply_to_message and message.reply_to_message.video:
        await state.update_data(video_file_id=message.reply_to_message.video.file_id)

    keyboard = get_vid_vol_keyboard(current)
    await message.reply(
        "🔊 **Выбери громкость для видео:**\n(Если не ответил на видео, выбери уровень, а затем отправь видео)",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )
    await state.set_state(VidVolState.wait_for_video)

@dp.callback_query(F.data.startswith("vidvol:"))
async def cb_set_vidvol(call: CallbackQuery, state: FSMContext):
    vol_val = int(call.data.split(":")[1])
    user_id = call.from_user.id
    user_vid_vol[user_id] = vol_val
    
    data = await state.get_data()
    video_file_id = data.get("video_file_id")

    if not video_file_id and call.message.reply_to_message and call.message.reply_to_message.video:
        video_file_id = call.message.reply_to_message.video.file_id

    if not video_file_id:
        await call.message.edit_text(
            f"✅ Громкость установлена на **x{vol_val}**.\n\nТеперь отправь видео или ответь командой `/vidvol` прямо на нужное видео!",
            parse_mode="Markdown"
        )
        await call.answer()
        return

    await call.message.edit_text(f"⏳ Меняю громкость видео на x{vol_val}... Жди!")
    
    input_path = f"input_vidvol_{user_id}.mp4"
    output_path = f"output_vidvol_{user_id}.mp4"

    try:
        file_info = await bot.get_file(video_file_id)
        await bot.download_file(file_info.file_path, destination=input_path)

        command = [
            "ffmpeg", "-y", "-i", input_path,
            "-filter:a", f"volume={vol_val}",
            "-c:v", "copy",
            output_path
        ]

        process = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if process.returncode != 0:
            raise Exception("Ошибка обработки громкости через ffmpeg")

        video_file = FSInputFile(output_path)
        await call.message.delete()
        await call.message.answer_video(video_file, caption=f"🔊 Громкость видео: x{vol_val}")
        await state.clear()

    except Exception as e:
        logging.error(f"Ошибка громкости видео: {e}")
        await call.message.edit_text("❌ Не удалось изменить громкость видео.")
    finally:
        if os.path.exists(input_path): os.remove(input_path)
        if os.path.exists(output_path): os.remove(output_path)

    await call.answer()

@dp.message(VidVolState.wait_for_video, F.video)
async def handle_vidvol_video_state(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    vol_val = user_vid_vol.get(user_id, 1)

    msg = await message.reply(f"⏳ Меняю громкость видео на x{vol_val}... Жди!")
    input_path = f"input_vidvol_{user_id}.mp4"
    output_path = f"output_vidvol_{user_id}.mp4"

    try:
        file_info = await bot.get_file(message.video.file_id)
        await bot.download_file(file_info.file_path, destination=input_path)

        command = [
            "ffmpeg", "-y", "-i", input_path,
            "-filter:a", f"volume={vol_val}",
            "-c:v", "copy",
            output_path
        ]

        process = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if process.returncode != 0:
            raise Exception("Ошибка ffmpeg")

        await message.reply_video(FSInputFile(output_path), caption=f"🔊 Громкость видео: x{vol_val}")
        await state.clear()
    except Exception as e:
        logging.error(f"Ошибка состояния громкости видео: {e}")
        await message.reply("❌ Не удалось обработать видео.")
    finally:
        await msg.delete()
        if os.path.exists(input_path): os.remove(input_path)
        if os.path.exists(output_path): os.remove(output_path)

# =============================================================
# 💥 УШЕРАЗДИРАТЕЛЬ АУДИО (/fry)
# =============================================================

@dp.message(Command("fry"))
async def cmd_fry_audio(message: types.Message):
    target_msg = message.reply_to_message
    if not target_msg or (not target_msg.voice and not target_msg.audio):
        await message.reply("⚠️ Ответь командой `/fry` на голосовое сообщение или аудиофайл!", parse_mode="Markdown")
        return

    msg = await message.reply("⚡ Перегружаю звуковые каналы...")
    user_id = message.from_user.id
    audio_obj = target_msg.voice or target_msg.audio
    
    input_path = f"input_fry_{user_id}_{message.message_id}.ogg"
    output_path = f"output_fry_{user_id}_{message.message_id}.ogg"

    try:
        file_info = await bot.get_file(audio_obj.file_id)
        await bot.download_file(file_info.file_path, destination=input_path)

        command = [
            "ffmpeg", "-y", "-i", input_path,
            "-af", "volume=15,acrusher=level_in=8:level_out=18:bits=8:mode=log:aa=1",
            "-c:a", "libopus", "-b:a", "16k",
            output_path
        ]
        
        subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        await message.reply_voice(FSInputFile(output_path), caption="💥 Берегите уши!")

    except Exception as e:
        logging.error(f"Ошибка перегруза аудио: {e}")
        await message.reply("Не удалось обработать аудиозапись.")
    finally:
        await msg.delete()
        if os.path.exists(input_path): os.remove(input_path)
        if os.path.exists(output_path): os.remove(output_path)

# =============================================================
# 🎙 ОЗВУЧКА (/say)
# =============================================================

@dp.message(Command("say", "tts"))
async def handle_tts(message: types.Message):
    user_id = message.from_user.id
    args = message.text.split(maxsplit=1)

    text_to_speak = ""
    if len(args) >= 2:
        text_to_speak = args[1]
    elif message.reply_to_message and message.reply_to_message.text:
        text_to_speak = message.reply_to_message.text
    else:
        await message.reply("Напиши текст: `/say Привет` или ответь этой командой на текст!", parse_mode="Markdown")
        return

    speed = get_user_speed(user_id)
    voice = get_user_voice(user_id)
    
    mp3_path = f"tts_{user_id}_{message.message_id}.mp3"
    ogg_path = f"tts_{user_id}_{message.message_id}.ogg"

    await bot.send_chat_action(chat_id=message.chat.id, action="record_voice")

    success = False
    for attempt in range(3):
        try:
            communicate = edge_tts.Communicate(text_to_speak, voice=voice, rate=speed)
            await communicate.save(mp3_path)

            if os.path.exists(mp3_path) and os.path.getsize(mp3_path) > 0:
                success = True
                break 
        except Exception:
            await asyncio.sleep(1) 

    try:
        if not success:
            raise Exception("Не удалось получить аудио от EdgeTTS.")

        process = subprocess.run(
            [
                "ffmpeg", "-y", "-i", mp3_path, 
                "-af", "silenceremove=stop_periods=-1:stop_duration=0.1:stop_threshold=-50dB",
                "-c:a", "libopus", "-b:a", "32k", "-ar", "48000", "-ac", "1", "-vn", ogg_path
            ],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        
        if process.returncode != 0:
            raise Exception("Ошибка конвертации в OGG")

        await message.reply_voice(FSInputFile(ogg_path))

    except Exception as e:
        logging.error(f"TTS Error: {e}")
        await message.reply("Ошибка сервера озвучки. Попробуйте еще раз.")
    finally:
        for path in (mp3_path, ogg_path):
            if os.path.exists(path): os.remove(path)

# =============================================================
# 💬 ОБРАБОТКА ОБЫЧНОГО ТЕКСТА
# =============================================================

@dp.message(F.chat.type == "private", F.text & ~F.text.startswith("/"))
async def handle_chat(message: types.Message):
    user_id = message.from_user.id
    if is_mat_enabled(user_id):
        await message.reply("Я не бот для болтовни! 🤖\nЮзай команды из меню или пиши `/help`.", parse_mode="Markdown")
    else:
        await message.reply("Извини, я умею только выполнять команды! 🤖\nОткрой меню или введи `/help`.", parse_mode="Markdown")

# =============================================================
# 🚀 ЗАПУСК
# =============================================================

async def set_main_menu(bot: Bot):
    await bot.set_my_commands([
        BotCommand(command="start", description="Запустить бота"),
        BotCommand(command="help", description="Список всех команд и помощь"),
        BotCommand(command="settings", description="Панель настроек"),
        BotCommand(command="shih", description="Жмыхнуть картинку"),
        BotCommand(command="kek", description="Сделать шакальное видео"),
        BotCommand(command="vidspeed", description="Скорость видео"),
        BotCommand(command="vidvol", description="Громкость видео"),
        BotCommand(command="fry", description="Перегрузить аудио/голосовое"),
        BotCommand(command="say", description="Озвучить текст"),
        BotCommand(command="voice", description="Выбрать голос"),
        BotCommand(command="speed", description="Скорость речи"),
    ])

async def health_check(request):
    return web.Response(text="Bot is running!")

async def main():
    await set_main_menu(bot)
    await bot.delete_webhook(drop_pending_updates=True)
    
    app = web.Application()
    app.router.add_get('/', health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    
    port = int(os.environ.get('PORT', 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    
    print("🚀 Бот успешно запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())