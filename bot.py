import asyncio
import logging
import os
import re
import subprocess
import cv2
import numpy as np
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
from PIL import Image, ImageEnhance, ImageOps

# --- НАСТРОЙКИ ---
BOT_TOKEN = os.getenv("BOT_TOKEN", "8982219315:AAEOfDYPXue_WjtKMs6XDNlH1LGVqL6vWTc")
CHANNEL_URL = "https://t.me/airasleshenia"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Конфигурация голосов edge-tts
VOICES_CONFIG = {
    "dmitry": {
        "name": "Дмитрий (Мужской)",
        "voice": "ru-RU-DmitryNeural",
    },
    "anya": {
        "name": "Аня (Женский)",
        "voice": "ru-RU-SvetlanaNeural",
    },
    "max": {
        "name": "Макс (Мужской)",
        "voice": "ru-RU-DmitryNeural",
    }
}

# Хранилище настроек пользователей
mat_mode = {}  
user_speed = {}  
user_kek_lvl = {}  
user_kek_vol = {}  
user_vid_speed = {}
user_vid_vol = {}

# --- Вспомогательные функции ---
def is_mat_enabled(user_id: int) -> bool:
    return mat_mode.get(user_id, True)

def get_user_speed(user_id: int) -> str:
    return user_speed.get(user_id, "+0%")

def get_kek_lvl(user_id: int) -> int:
    return user_kek_lvl.get(user_id, 3) 

def get_kek_vol(user_id: int) -> int:
    return user_kek_vol.get(user_id, 1) 

# --- КЛАВИАТУРЫ ---

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

    promo_text = f"Подпишитесь на наш канал: {CHANNEL_URL}\n\n"

    if mat:
        text = f"{promo_text}Режим 18+ включен.\nЯ базарю с матом. Пиши /help, чтобы посмотреть команды или загляни в /settings."
    else:
        text = f"{promo_text}Режим культурного общения включен.\n\nНапиши /help, чтобы увидеть список команд или настроек /settings."

    await message.answer(text, disable_web_page_preview=True)


@dp.message(Command("help"))
async def cmd_help(message: types.Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    mat = is_mat_enabled(user_id)

    help_text = (
        "Справка по командам:\n\n"
        "Быстрая озвучка по командам:\n"
        "• /dmitry <текст> — Дмитрий (Мужской)\n"
        "• /anya <текст> — Аня (Женский)\n"
        "• /max <текст> — Макс (Мужской)\n\n"
        "Медиа-обработка (ответом на медиа или с текстом в подписи):\n"
        "• /grid — Наложить чёрную сетку на фото/видео\n"
        "• /shih — Жмыхнуть фото\n"
        "• /kek — Испортить видео\n"
        "• /vidspeed — Изменить скорость видео\n"
        "• /vidvol — Изменить громкость видео\n"
        "• /fry — Перегрузить аудио\n\n"
        "Параметры:\n"
        "• /settings — Панель настроек\n"
        "• /cancel — Отменить текущее действие"
    )

    prefix = "Забыл команды? Смотри список:\n\n" if mat else "Вот список доступных команд:\n\n"
    await message.answer(prefix + help_text)


@dp.message(Command("settings"))
async def cmd_settings(message: types.Message):
    user_id = message.from_user.id
    await message.answer("Панель управления настройками:", reply_markup=get_settings_keyboard(user_id))


@dp.message(Command("stopmat"))
async def cmd_stopmat(message: types.Message):
    mat_mode[message.from_user.id] = False
    await message.answer("Маты отключены.")

@dp.message(Command("startmat"))
async def cmd_startmat(message: types.Message):
    mat_mode[message.from_user.id] = True
    await message.answer("Режим 18+ включен.")

# =============================================================
# ⚙️ ОБРАБОТКА CALLBACKS
# =============================================================

@dp.callback_query(F.data == "open_keklvl_menu")
async def cb_open_keklvl(call: CallbackQuery):
    user_id = call.from_user.id
    curr = get_kek_lvl(user_id)
    await call.message.edit_text("Выберите уровень уродства видео (1 — слабо, 5 — жестко):", reply_markup=get_kek_lvl_keyboard(curr))
    await call.answer()

@dp.callback_query(F.data.startswith("set_keklvl:"))
async def cb_set_keklvl(call: CallbackQuery):
    user_id = call.from_user.id
    lvl = int(call.data.split(":")[1])
    user_kek_lvl[user_id] = lvl
    await call.message.edit_text(f"Шакальность видео установлена на: {lvl}")
    await call.answer()

@dp.callback_query(F.data == "open_kekvol_menu")
async def cb_open_kekvol(call: CallbackQuery):
    user_id = call.from_user.id
    curr = get_kek_vol(user_id)
    await call.message.edit_text("Выберите уровень громкости видео:", reply_markup=get_kek_vol_keyboard(curr))
    await call.answer()

@dp.callback_query(F.data.startswith("set_kekvol:"))
async def cb_set_kekvol(call: CallbackQuery):
    user_id = call.from_user.id
    vol = int(call.data.split(":")[1])
    user_kek_vol[user_id] = vol
    await call.message.edit_text(f"Громкость видео выкручена на: x{vol}")
    await call.answer()

@dp.callback_query(F.data == "toggle_mat_mode")
async def cb_toggle_mat(call: CallbackQuery):
    user_id = call.from_user.id
    mat_mode[user_id] = not is_mat_enabled(user_id)
    await call.message.edit_reply_markup(reply_markup=get_settings_keyboard(user_id))
    await call.answer("Режим мата изменен.")

# =============================================================
# 🗣 БЫСТРАЯ ОЗВУЧКА (/dmitry, /anya, /max)
# =============================================================

async def process_tts_generation(message: types.Message, voice_key: str):
    user_id = message.from_user.id
    args = message.text.split(maxsplit=1)

    text_to_speak = ""
    if len(args) >= 2:
        text_to_speak = args[1].strip()
    elif message.reply_to_message and message.reply_to_message.text:
        text_to_speak = message.reply_to_message.text.strip()
    
    if not text_to_speak:
        await message.reply(f"Напиши текст после команды, например:\n/{voice_key} Привет\nИли ответь этой командой на текст.")
        return

    text_to_speak = re.sub(r'[^А-Яа-яЁёA-Za-z0-9\s.,!?-]', '', text_to_speak).strip()
    if not text_to_speak:
        text_to_speak = "Тест."
    
    if not text_to_speak.endswith(('.', '!', '?', '...')):
        text_to_speak += '.'

    v_conf = VOICES_CONFIG[voice_key]
    user_sp = get_user_speed(user_id)
    
    mp3_path = f"tts_{user_id}_{message.message_id}.mp3"
    chunk_path = f"chunk_{user_id}_{message.message_id}.wav"
    silence_path = f"silence_{user_id}.wav"
    list_path = f"list_{user_id}_{message.message_id}.txt"
    ogg_path = f"tts_{user_id}_{message.message_id}.ogg"

    await bot.send_chat_action(chat_id=message.chat.id, action="record_voice")

    success = False
    for attempt in range(3):
        try:
            communicate = edge_tts.Communicate(text_to_speak, voice=v_conf["voice"], rate=user_sp)
            await communicate.save(mp3_path)

            if os.path.exists(mp3_path) and os.path.getsize(mp3_path) > 0:
                success = True
                break
        except Exception as e:
            logging.warning(f"Попытка озвучки {attempt+1} не удалась: {e}")
            await asyncio.sleep(1)

    if not success:
        await message.reply("Не удалось получить аудио от сервера. Попробуй еще раз через пару секунд.")
        return

    try:
        # 1. Конвертируем mp3 в стандартный wav с частотой 48000 Гц
        subprocess.run([
            "ffmpeg", "-y", "-i", mp3_path, 
            "-ar", "48000", "-ac", "1", chunk_path
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)

        # 2. Генерируем 1.2 секунды чистой тишины
        subprocess.run([
            "ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=mono", "-t", "1.2",
            "-ar", "48000", "-ac", "1", silence_path
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)

        # 3. Создаем список для надежного объединения файлов
        with open(list_path, "w", encoding="utf-8") as f:
            f.write(f"file '{os.path.abspath(chunk_path)}'\n")
            f.write(f"file '{os.path.abspath(silence_path)}'\n")

        # 4. Склеиваем и кодируем в Opus для голосового сообщения
        process = subprocess.run(
            [
                "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_path,
                "-c:a", "libopus", "-b:a", "32k", "-ar", "48000", "-ac", "1", ogg_path
            ],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        
        if process.returncode != 0 or not os.path.exists(ogg_path):
            raise Exception(f"Ошибка конвертации FFmpeg: {process.stderr}")

        await message.reply_voice(FSInputFile(ogg_path))

    except Exception as e:
        logging.error(f"TTS Error: {e}")
        await message.reply("Не удалось обработать аудиофайл.")
    finally:
        for path in (mp3_path, chunk_path, silence_path, list_path, ogg_path):
            if os.path.exists(path): 
                try:
                    os.remove(path)
                except:
                    pass

@dp.message(Command("dmitry"))
async def cmd_dmitry(message: types.Message):
    await process_tts_generation(message, "dmitry")

@dp.message(Command("anya"))
async def cmd_anya(message: types.Message):
    await process_tts_generation(message, "anya")

@dp.message(Command("max"))
async def cmd_max(message: types.Message):
    await process_tts_generation(message, "max")

# =============================================================
# 📐 НАЛОЖЕНИЕ ЧЁРНОЙ СЕТКИ НА ФОТО И ВИДЕО (/grid)
# =============================================================

async def process_grid_photo(message: types.Message, photo: types.PhotoSize):
    user_id = message.from_user.id
    msg = await message.reply("Накладываю чёрную сетку на фото...")
    
    input_path = f"input_grid_{user_id}_{message.message_id}.jpg"
    output_path = f"output_grid_{user_id}_{message.message_id}.jpg"
    
    try:
        file_info = await bot.get_file(photo.file_id)
        await bot.download_file(file_info.file_path, destination=input_path)
        
        img = cv2.imread(input_path)
        h, w = img.shape[:2]
        
        step_x = max(w // 10, 30)
        step_y = max(h // 10, 30)
        
        for x in range(0, w, step_x):
            cv2.line(img, (x, 0), (x, h), (0, 0, 0), 2)
        for y in range(0, h, step_y):
            cv2.line(img, (0, y), (w, y), (0, 0, 0), 2)
            
        cv2.imwrite(output_path, img)
        
        await bot.send_chat_action(chat_id=message.chat.id, action="upload_photo")
        await message.reply_photo(FSInputFile(output_path), caption="Готово! Чёрная сетка наложена на фото.")
    except Exception as e:
        logging.error(f"Ошибка grid фото: {e}")
        await message.reply("Не удалось обработать картинку.")
    finally:
        await msg.delete()
        if os.path.exists(input_path): os.remove(input_path)
        if os.path.exists(output_path): os.remove(output_path)

async def process_grid_video(message: types.Message, video: types.Video):
    user_id = message.from_user.id
    if video.file_size > 20 * 1024 * 1024:
        await message.reply("Файл слишком большой! Лимит 20 МБ.")
        return

    msg = await message.reply("Накладываю чёрную сетку на видео...")
    input_path = f"input_grid_vid_{user_id}_{message.message_id}.mp4"
    output_path = f"output_grid_vid_{user_id}_{message.message_id}.mp4"
    
    try:
        file_info = await bot.get_file(video.file_id)
        await bot.download_file(file_info.file_path, destination=input_path)
        
        command = [
            "ffmpeg", "-y", "-i", input_path,
            "-vf", "drawgrid=w=100:h=100:t=2:c=black@0.8",
            "-c:a", "copy",
            output_path
        ]
        
        process = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if process.returncode != 0:
            raise Exception(f"Ошибка FFmpeg grid video: {process.stderr}")

        await bot.send_chat_action(chat_id=message.chat.id, action="upload_video")
        await message.reply_video(FSInputFile(output_path), caption="Готово! Чёрная сетка наложена на видео.")
    except Exception as e:
        logging.error(f"Ошибка grid видео: {e}")
        await message.reply("Не удалось обработать видео.")
    finally:
        await msg.delete()
        if os.path.exists(input_path): os.remove(input_path)
        if os.path.exists(output_path): os.remove(output_path)

@dp.message(Command("grid"))
async def cmd_grid_handler(message: types.Message):
    target = message.reply_to_message
    if not target:
        await message.reply("Ответь этой командой (/grid) на фото или видео, либо отправь файл с подписью /grid!")
        return

    if target.photo:
        await process_grid_photo(message, target.photo[-1])
    elif target.video:
        await process_grid_video(message, target.video)
    else:
        await message.reply("Нужно ответить именно на фото или видео!")

@dp.message(F.photo, F.caption & F.caption.startswith("/grid"))
async def caption_grid_photo(message: types.Message):
    await process_grid_photo(message, message.photo[-1])

@dp.message(F.video, F.caption & F.caption.startswith("/grid"))
async def caption_grid_video(message: types.Message):
    await process_grid_video(message, message.video)


# =============================================================
# 🥴 ЖМЫХ КАРТИНКИ (/shih)
# =============================================================

@dp.message(Command("shih", "zhmyh"))
async def cmd_shih_handler(message: types.Message):
    target = message.reply_to_message
    if not target or not target.photo:
        await message.reply("Ответь этой командой (/shih) на фотографию!")
        return
    await process_shih_photo(message, target.photo[-1])

async def process_shih_photo(message: types.Message, photo: types.PhotoSize):
    user_id = message.from_user.id
    mat = is_mat_enabled(user_id)
    msg = await message.reply("Искривляю пространство и жмыхаю...")
    
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
        caption_text = "Готово!" if not mat else "Ебать лицо всосало"
        
        await bot.send_chat_action(chat_id=message.chat.id, action="upload_photo")
        await message.reply_photo(photo_file, caption=caption_text)
        
    except Exception as e:
        logging.error(f"Ошибка жмыха: {e}")
        await message.reply("Не удалось обработать картинку.")
    finally:
        await msg.delete()
        if os.path.exists(input_path): os.remove(input_path)
        if os.path.exists(output_path): os.remove(output_path)

@dp.message(F.photo, F.caption & (F.caption.startswith("/shih") | F.caption.startswith("/zhmyh")))
async def caption_shih_photo(message: types.Message):
    await process_shih_photo(message, message.photo[-1])


# =============================================================
# 🤪 ШАКАЛЬНОЕ ВИДЕО (/kek)
# =============================================================

@dp.message(Command("kek"))
async def cmd_kek_handler(message: types.Message):
    target = message.reply_to_message
    if not target or not target.video:
        await message.reply("Ответь этой командой (/kek) на видеозапись!")
        return
    await process_kek_video(message, target.video)

async def process_kek_video(message: types.Message, video: types.Video):
    user_id = message.from_user.id
    mat = is_mat_enabled(user_id)
    
    if video.file_size > 15 * 1024 * 1024:
        await message.reply("Файл слишком большой! Лимит 15 МБ.")
        return

    msg = await message.reply("Начинаю шакалить качество...")
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
        caption_text += "Качество вышло погулять" if mat else "Твоё видео готово!"
        
        await bot.send_chat_action(chat_id=message.chat.id, action="upload_video")
        await message.reply_video(video_file, caption=caption_text)
        
    except Exception as e:
        logging.error(f"Ошибка видео: {e}")
        await message.reply("Не получилось обработать видео.")
    finally:
        await msg.delete()
        if os.path.exists(input_path): os.remove(input_path)
        if os.path.exists(output_path): os.remove(output_path)

@dp.message(F.video, F.caption & F.caption.startswith("/kek"))
async def caption_kek_video(message: types.Message):
    await process_kek_video(message, message.video)


# =============================================================
# ⏩ СКОРОСТЬ И 🔊 ГРОМКОСТЬ ВИДЕО (/vidspeed, /vidvol)
# =============================================================

@dp.message(Command("vidspeed", "speedvid"))
async def cmd_vidspeed_start(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    current = user_vid_speed.get(user_id, 1.0)
    
    if message.reply_to_message and message.reply_to_message.video:
        await state.update_data(video_file_id=message.reply_to_message.video.file_id)

    keyboard = get_vid_speed_keyboard(current)
    await message.reply("Выбери скорость для видео:", reply_markup=keyboard)

@dp.callback_query(F.data.startswith("vidspeed:"))
async def cb_set_vidspeed(call: CallbackQuery, state: FSMContext):
    speed_val = float(call.data.split(":")[1])
    user_id = call.from_user.id
    user_vid_speed[user_id] = speed_val
    await call.message.edit_text(f"Скорость установлена на {speed_val}x.")
    await call.answer()

@dp.message(Command("vidvol"))
async def cmd_vidvol_start(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    current = user_vid_vol.get(user_id, 1)
    
    if message.reply_to_message and message.reply_to_message.video:
        await state.update_data(video_file_id=message.reply_to_message.video.file_id)

    keyboard = get_vid_vol_keyboard(current)
    await message.reply("Выбери громкость для видео:", reply_markup=keyboard)

@dp.callback_query(F.data.startswith("vidvol:"))
async def cb_set_vidvol(call: CallbackQuery, state: FSMContext):
    vol_val = int(call.data.split(":")[1])
    user_id = call.from_user.id
    user_vid_vol[user_id] = vol_val
    await call.message.edit_text(f"Громкость установлена на x{vol_val}.")
    await call.answer()

# =============================================================
# 💥 УШЕРАЗДИРАТЕЛЬ АУДИО (/fry)
# =============================================================

@dp.message(Command("fry"))
async def cmd_fry_audio(message: types.Message):
    target_msg = message.reply_to_message
    if not target_msg or (not target_msg.voice and not target_msg.audio):
        await message.reply("Ответь командой /fry на голосовое сообщение или аудиофайл!")
        return

    msg = await message.reply("Перегружаю звуковые каналы...")
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
        await message.reply_voice(FSInputFile(output_path), caption="Берегите уши!")

    except Exception as e:
        logging.error(f"Ошибка перегруза аудио: {e}")
        await message.reply("Не удалось обработать аудиозапись.")
    finally:
        await msg.delete()
        if os.path.exists(input_path): os.remove(input_path)
        if os.path.exists(output_path): os.remove(output_path)

# =============================================================
# 💬 ОБРАБОТКА ОБЫЧНОГО ТЕКСТА
# =============================================================

@dp.message(F.chat.type == "private", F.text & ~F.text.startswith("/"))
async def handle_chat(message: types.Message):
    user_id = message.from_user.id
    if is_mat_enabled(user_id):
        await message.reply("Я не бот для болтовни. Используй команды из меню или пиши /help.")
    else:
        await message.reply("Извини, я умею только выполнять команды. Введи /help.")

# =============================================================
# 🚀 ЗАПУСК
# =============================================================

async def set_main_menu(bot: Bot):
    await bot.set_my_commands([
        BotCommand(command="start", description="Запустить бота"),
        BotCommand(command="help", description="Список всех команд и помощь"),
        BotCommand(command="dmitry", description="Голос Дмитрий"),
        BotCommand(command="anya", description="Голос Аня"),
        BotCommand(command="max", description="Голос Макс"),
        BotCommand(command="grid", description="Наложить чёрную сетку на фото/видео"),
        BotCommand(command="shih", description="Жмыхнуть картинку"),
        BotCommand(command="kek", description="Сделать шакальное видео"),
        BotCommand(command="vidspeed", description="Скорость видео"),
        BotCommand(command="vidvol", description="Громкость видео"),
        BotCommand(command="fry", description="Перегрузить аудио"),
        BotCommand(command="settings", description="Панель настроек"),
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
    
    print("Бот успешно запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())