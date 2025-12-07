#!/usr/bin/env python3

import json
import requests
import subprocess
import time
import random
import threading
import sys
import select
import os
from datetime import datetime, timedelta
from ev3dev2.motor import LargeMotor, MediumMotor, OUTPUT_A, OUTPUT_B, OUTPUT_C
from ev3dev2.sensor import INPUT_1, INPUT_2, INPUT_3, INPUT_4
from ev3dev2.sensor.lego import TouchSensor, InfraredSensor, ColorSensor, GyroSensor
from ev3dev2.button import Button
from ev3dev2.led import Leds

# Настройки из config.py
from config import *

# Инициализация моторов
left_motor = LargeMotor(OUTPUT_B)
right_motor = LargeMotor(OUTPUT_C)
blade_motor = MediumMotor(OUTPUT_A)

# Инициализация датчиков
try:
    touchs = TouchSensor(INPUT_1)
    touchs.mode = 'TOUCH'
except Exception as e:
    print("Ошибка инициализации датчика касания (кнопки): " + str(e))
    touchs = None

try:
    ir_sensor = InfraredSensor(INPUT_4)
    # Устанавливаем только один режим и не меняем его
    ir_sensor.mode = 'IR-PROX'
except Exception as e:
    print("Ошибка инициализации ИК датчика: " + str(e))
    ir_sensor = None

try:
    color_sensor = ColorSensor(INPUT_3)
    color_sensor.mode = 'COL-COLOR'
except Exception as e:
    print("Ошибка инициализации датчика цвета: " + str(e))
    color_sensor = None

button = Button()

if USE_GYRO:
    try:
        gyro_sensor = GyroSensor(INPUT_2)
        gyro_sensor.mode = 'GYRO-ANG'
    except Exception as e:
        print("Ошибка инициализации гироскопа: " + str(e))
        gyro_sensor = None
        USE_GYRO = False

leds = Leds()
leds.all_off()

# Глобальные переменные для управления
daily_requests = 0
daily_reset_time = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
is_performing_action = False
terminal_input_queue = []
last_action_time = time.time()
action_history = []
obstacle_detected = False
last_obstacle_time = 0

# Блокировка для синхронизации доступа к датчикам
sensor_lock = threading.Lock()
# Кэш для значений датчиков
sensor_cache = {
    'ir_distance': 100,
    'color': 'NoColor',
    'color_description': 'нет цвета',
    'last_update': 0
}
# Время жизни кэша (секунды)
CACHE_TTL = 0.1

def safe_get_ir_distance():
    """Безопасное получение расстояния с ИК датчика с кэшированием"""
    global sensor_cache
    
    current_time = time.time()
    
    # Возвращаем кэшированное значение, если оно актуально
    if current_time - sensor_cache['last_update'] < CACHE_TTL:
        return sensor_cache['ir_distance']
    
    # Используем блокировку для безопасного доступа к датчику
    with sensor_lock:
        if ir_sensor is None:
            return 100  # Значение по умолчанию
        
        try:
            # Читаем значение несколько раз для надежности
            values = []
            for _ in range(3):
                try:
                    # Используем mode для гарантированного получения правильного типа данных
                    distance = ir_sensor.proximity
                    if isinstance(distance, (int, float)):
                        values.append(int(distance))
                    time.sleep(0.01)
                except (ValueError, AttributeError) as e:
                    continue
            
            if values:
                # Берем медиану значений для фильтрации выбросов
                values.sort()
                median_distance = values[len(values)//2]
                # Ограничиваем разумными пределами
                median_distance = max(0, min(median_distance, 100))
                
                # Обновляем кэш
                sensor_cache['ir_distance'] = median_distance
                sensor_cache['last_update'] = current_time
                return median_distance
            else:
                # Если все попытки неудачны, возвращаем кэшированное значение
                return sensor_cache['ir_distance']
                
        except Exception as e:
            print("Критическая ошибка ИК датчика: " + str(e))
            return sensor_cache['ir_distance']  # Возвращаем последнее известное значение

def safe_get_color():
    """Безопасное получение цвета с датчика цвета"""
    global sensor_cache
    
    current_time = time.time()
    
    # Возвращаем кэшированное значение, если оно актуально
    if current_time - sensor_cache['last_update'] < CACHE_TTL:
        return sensor_cache['color'], sensor_cache['color_description']
    
    with sensor_lock:
        if color_sensor is None:
            return 'NoColor', 'нет цвета'
        
        try:
            color_name = color_sensor.color_name
            if not color_name:
                color_name = 'NoColor'
            
            # Обновляем кэш
            sensor_cache['color'] = color_name
            sensor_cache['color_description'] = color_descriptions.get(color_name, color_name)
            sensor_cache['last_update'] = current_time
            
            return color_name, sensor_cache['color_description']
                
        except Exception as e:
            print("Ошибка датчика цвета: " + str(e))
            return 'NoColor', 'нет цвета'

# Описания цветов для лучшего понимания
color_descriptions = {
    'NoColor': 'нет цвета',
    'Black': 'черный',
    'Blue': 'синий',
    'Green': 'зеленый',
    'Yellow': 'желтый',
    'Red': 'красный',
    'White': 'белый',
    'Brown': 'коричневый'
}

def speak(text):
    """Озвучивание текста через espeak без вывода ALSA ошибок"""
    try:
        with open(os.devnull, 'w') as devnull:
            subprocess.run(
                ['espeak', '-v', 'ru', '-s', '100', text],
                check=False,
                stdout=devnull,
                stderr=devnull
            )
        print("Робот говорит: " + text)
    except Exception as e:
        print("Ошибка озвучивания: " + str(e))

def get_sensor_data():
    """Получение данных с датчиков (потокобезопасное)"""
    global obstacle_detected, sensor_cache
    
    # Получаем данные с датчиков через безопасные функции
    ir_distance = safe_get_ir_distance()
    color, color_desc = safe_get_color()
    
    sensor_data = {
        "ir_distance": ir_distance,
        "color": color,
        "color_description": color_desc,
        "buttons": touchs.is_pressed,
        "gyro_connected": USE_GYRO,
        "timestamp": time.time(),
        "time_of_day": datetime.now().strftime('%H:%M'),
        "obstacle_detected": obstacle_detected
    }
    
    if USE_GYRO and gyro_sensor is not None:
        try:
            with sensor_lock:
                sensor_data["gyro_angle"] = gyro_sensor.angle
                sensor_data["gyro_rate"] = gyro_sensor.rate
        except Exception as e:
            print("Ошибка чтения гироскопа: " + str(e))
            sensor_data["gyro_angle"] = 0
            sensor_data["gyro_rate"] = 0
    
    # Проверка на препятствие
    if ir_distance < OBSTACLE_DISTANCE and not is_performing_action:
        obstacle_detected = True
        sensor_data["obstacle_detected"] = True
        sensor_data["obstacle_distance"] = ir_distance
    else:
        obstacle_detected = False
        sensor_data["obstacle_detected"] = False
    
    return sensor_data

def check_obstacle():
    """Проверка наличия препятствия и реакция на него"""
    global obstacle_detected, last_obstacle_time, is_performing_action
    
    current_distance = safe_get_ir_distance()
    current_time = time.time()
    
    # Если обнаружено препятствие близко и прошло достаточно времени с последней реакции
    if (current_distance < OBSTACLE_DISTANCE and 
        not is_performing_action and
        current_time - last_obstacle_time > 10):
        
        obstacle_detected = True
        last_obstacle_time = current_time
        
        # Останавливаем все моторы
        stop_all()
        
        print("\n" + "!"*50)
        print("ОБНАРУЖЕНО ПРЕПЯТСТВИЕ!")
        print("Расстояние: " + str(current_distance) + " см")
        print("!"*50)
        
        # Запрашиваем реакцию у нейросети
        sensor_data = get_sensor_data()
        reaction_data = query_gemini_obstacle(sensor_data)
        
        if reaction_data:
            is_performing_action = True
            execute_action_sequence(reaction_data)
            is_performing_action = False
        
        return True
    
    obstacle_detected = False
    return False

def check_daily_limit():
    """Проверка дневного лимита запросов"""
    global daily_requests, daily_reset_time
    
    if not ENABLE_REQUEST_LIMIT:
        return True
        
    now = datetime.now()
    if now >= daily_reset_time:
        daily_requests = 0
        daily_reset_time = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        print("Сброс дневного лимита запросов")
    
    return daily_requests < DAILY_REQUEST_LIMIT

def get_remaining_requests():
    """Получение количества оставшихся запросов"""
    if not ENABLE_REQUEST_LIMIT:
        return "не ограничено"
    remaining = DAILY_REQUEST_LIMIT - daily_requests
    return str(remaining)

def move_forward(speed=50, duration=1.0):
    """Движение вперед с проверкой препятствий"""
    global obstacle_detected
    
    duration = min(duration, MAX_MOVE_DURATION)
    speed = min(speed, MAX_MOTOR_SPEED)
    
    print("Движение вперед: скорость " + str(speed) + ", время " + str(duration) + " сек")
    
    start_time = time.time()
    while time.time() - start_time < duration:
        # Проверяем препятствие каждые 0.1 секунды
        if check_obstacle():
            print("Прервано из-за препятствия")
            return
        
        left_motor.on(speed)
        right_motor.on(speed)
        time.sleep(0.1)
    
    left_motor.off()
    right_motor.off()

def move_backward(speed=50, duration=1.0):
    """Движение назад с ограничением времени"""
    duration = min(duration, MAX_MOVE_DURATION)
    speed = min(speed, MAX_MOTOR_SPEED)
    
    print("Движение назад: скорость " + str(speed) + ", время " + str(duration) + " сек")
    
    left_motor.on(-speed)
    right_motor.on(-speed)
    time.sleep(duration)
    left_motor.off()
    right_motor.off()

def turn_left(speed=30, angle=90):
    """Поворот налево с ограничением угла и времени"""
    angle = min(angle, MAX_TURN_ANGLE)
    speed = min(speed, MAX_MOTOR_SPEED)
    
    print("Поворот налево: скорость " + str(speed) + ", угол " + str(angle) + " градусов")
    
    if USE_GYRO and gyro_sensor is not None:
        try:
            with sensor_lock:
                initial_angle = gyro_sensor.angle
            target_angle = initial_angle - angle
            left_motor.on(-speed)
            right_motor.on(speed)
            
            start_time = time.time()
            while True:
                with sensor_lock:
                    current_angle = gyro_sensor.angle
                if current_angle <= target_angle:
                    break
                if time.time() - start_time > MAX_TURN_DURATION:
                    print("Превышено максимальное время поворота")
                    break
                time.sleep(0.01)
        except Exception as e:
            print("Ошибка при повороте с гироскопом: " + str(e))
            # Резервный вариант без гироскопа
            left_motor.on(-speed)
            right_motor.on(speed)
            time.sleep(angle / 90 * 0.8)
    else:
        left_motor.on(-speed)
        right_motor.on(speed)
        time.sleep(angle / 90 * 0.8)
    
    left_motor.off()
    right_motor.off()

def turn_right(speed=30, angle=90):
    """Поворот направо с ограничением угла и времени"""
    angle = min(angle, MAX_TURN_ANGLE)
    speed = min(speed, MAX_MOTOR_SPEED)
    
    print("Поворот направо: скорость " + str(speed) + ", угол " + str(angle) + " градусов")
    
    if USE_GYRO and gyro_sensor is not None:
        try:
            with sensor_lock:
                initial_angle = gyro_sensor.angle
            target_angle = initial_angle + angle
            left_motor.on(speed)
            right_motor.on(-speed)
            
            start_time = time.time()
            while True:
                with sensor_lock:
                    current_angle = gyro_sensor.angle
                if current_angle >= target_angle:
                    break
                if time.time() - start_time > MAX_TURN_DURATION:
                    print("Превышено максимальное время поворота")
                    break
                time.sleep(0.01)
        except Exception as e:
            print("Ошибка при повороте с гироскопом: " + str(e))
            # Резервный вариант без гироскопа
            left_motor.on(speed)
            right_motor.on(-speed)
            time.sleep(angle / 90 * 0.8)
    else:
        left_motor.on(speed)
        right_motor.on(-speed)
        time.sleep(angle / 90 * 0.8)
    
    left_motor.off()
    right_motor.off()

def attack_with_blade(speed=100, duration=1.0):
    """Атака лезвием с ограничением времени"""
    leds.set_color('LEFT', 'RED')
    leds.set_color('RIGHT', 'RED')

    duration = min(duration, MAX_ATTACK_DURATION)
    speed = min(speed, MAX_BLADE_SPEED)
    
    print("Атака лезвием: скорость " + str(speed) + ", время " + str(duration) + " сек")
    
    blade_motor.on(speed)
    time.sleep(duration)
    blade_motor.off()
    leds.set_color('LEFT', 'AMBER')
    leds.set_color('RIGHT', 'AMBER')

def stop_all():
    """Остановка всех моторов"""
    print("Остановка всех моторов")
    left_motor.off()
    right_motor.off()
    blade_motor.off()

def get_random_mood():
    """Возвращает случайное настроение для разнообразия"""
    moods = [
        "веселый",
        "задумчивый",
        "любопытный",
        "энергичный",
        "спокойный",
        "игривый",
        "саркастичный",
        "дружелюбный"
    ]
    return random.choice(moods)

def get_situation_description(sensor_data):
    """Генерирует описание ситуации на основе данных датчиков"""
    distance = sensor_data['ir_distance']
    color_desc = sensor_data['color_description']
    
    # Описание расстояния
    if distance < 33:
        distance_desc = "очень близко"
    elif distance < 66:
        distance_desc = "на среднем расстоянии"
    elif distance < 100:
        distance_desc = "далеко"
    else:
        distance_desc = "далеко"
    
    # Описание цвета
    if color_desc in ['черный', 'нет цвета']:
        color_desc_text = "нет распознаваемого цвета"
    # elif color_desc in ['белый']:
    #     color_desc_text = "светло"
    else:
        color_desc_text = "вижу " + color_desc + " цвет"
    
    if distance > 99:
        return "Впереди ничего нет, " + color_desc + "."
    else:
        return "Объект " + distance_desc + " (" + str(distance) + " единиц), " + color_desc_text + "."

def get_context_prompt():
    """Создает контекстный промпт с разнообразными вариантами"""
    moods = [
        "Будь {mood} и {action}",
        "Прояви {mood} характер и {action}",
        "Сегодня ты {mood}, поэтому {action}",
        "Как {mood} робот, ты должен {action}"
    ]
    
    actions = [
        "сделай что-нибудь интересное",
        "прояви инициативу",
        "покажи свои возможности",
        "расскажи что-нибудь и покажи действие",
        "реагируй на окружающую обстановку",
        "сделай выразительное движение",
        "поделись мыслями и действуй",
        "будь креативным в своих действиях"
    ]
    
    mood = get_random_mood()
    mood_template = random.choice(moods)
    action = random.choice(actions)
    
    # Заменяем шаблонные переменные
    result = mood_template.replace("{mood}", mood).replace("{action}", action)
    return result

def extract_json_from_text(text):
    """Извлекает JSON из текста, поддерживает массивы и одиночные объекты"""
    import re
    
    # Убираем markdown коды
    text = text.strip()
    text = text.replace('```json', '').replace('```', '')
    
    # Ищем JSON (массив или объект)
    # Паттерн для массива JSON объектов
    array_pattern = r'\[\s*\{[^{}]*\}\s*(?:,\s*\{[^{}]*\}\s*)*\]'
    # Паттерн для одиночного JSON объекта
    object_pattern = r'\{[^{}]*\}'
    
    # Сначала пробуем найти массив
    array_match = re.search(array_pattern, text, re.DOTALL)
    if array_match:
        try:
            return json.loads(array_match.group())
        except json.JSONDecodeError:
            pass
    
    # Если массив не найден или не распарсился, ищем одиночный объект
    object_match = re.search(object_pattern, text, re.DOTALL)
    if object_match:
        try:
            # Возвращаем как массив с одним элементом
            single_obj = json.loads(object_match.group())
            return [single_obj]
        except json.JSONDecodeError:
            pass
    
    return None

def query_gemini_obstacle(sensor_data):
    """Специальный запрос к нейросети при обнаружении препятствия"""
    global daily_requests
    
    if not check_daily_limit():
        return None
    
    distance = sensor_data['ir_distance']
    
    prompt = """Ты - робот EV3RSTORM. Перед тобой препятствие на расстоянии """ + str(distance) + """ сантиметров.
    
Ты должен отреагировать на препятствие. Ты можешь отправить ОДИН JSON объект или МАССИВ JSON объектов.
Каждый JSON объект должен иметь формат:
{
    "action": "move_forward|move_backward|turn_left|turn_right|attack|speak|stop",
    "speed": число от 0 до 100,
    "duration": число в секундах,
    "angle": число в градусах,
    "speech": "текст для озвучивания на русском языке"
}

Пример массива (несколько действий):
[
  {
    "action": "speak",
    "speed": 0,
    "duration": 0,
    "angle": 0,
    "speech": "Обнаружено препятствие! Отступаю."
  },
  {
    "action": "move_backward",
    "speed": 40,
    "duration": 1.5,
    "angle": 0,
    "speech": ""
  },
  {
    "action": "turn_left",
    "speed": 30,
    "duration": 0,
    "angle": 45,
    "speech": "Поворачиваю, чтобы объехать."
  }
]

Отправь реакцию на препятствие. Не добавляй никаких дополнительных текстов, только JSON."""
    
    payload = {
        "contents": [{
            "parts": [{
                "text": prompt
            }]
        }],
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 500,
            "topP": 0.9
        }
    }
    
    headers = {
        "Content-Type": "application/json"
    }
    
    url = "https://generativelanguage.googleapis.com/v1beta/models/" + GEMINI_MODEL + ":generateContent?key=" + GEMINI_API_KEY
    
    try:
        response = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=30
        )
        
        if response.status_code == 429:
            print("Слишком много запросов к Gemini API. Пропускаю.")
            return None
        
        response.raise_for_status()
        
        result = response.json()
        
        if "candidates" not in result or len(result["candidates"]) == 0:
            print("Пустой ответ от Gemini API")
            return None
            
        assistant_message = result["candidates"][0]["content"]["parts"][0]["text"]
        
        daily_requests += 1
        print("Запрос о препятствии (осталось: " + get_remaining_requests() + ")")
        
        # Извлекаем JSON (массив или объект)
        actions_data = extract_json_from_text(assistant_message)
        
        if actions_data is None:
            print("Не удалось извлечь JSON из ответа о препятствии")
            # Стандартная реакция на препятствие
            return [{
                "action": "move_backward",
                "speed": 40,
                "duration": 1.5,
                "angle": 0,
                "speech": "Обнаружено препятствие! Отступаю."
            }]
        
        # Если это не список, делаем его списком
        if not isinstance(actions_data, list):
            actions_data = [actions_data]
        
        # Ограничиваем количество действий
        if len(actions_data) > MAX_SEQUENCE_ACTIONS:
            actions_data = actions_data[:MAX_SEQUENCE_ACTIONS]
            print("Ограничено количество действий до " + str(MAX_SEQUENCE_ACTIONS))
        
        # Валидация каждого действия
        validated_actions = []
        for action_data in actions_data:
            # Валидация полученного JSON
            if "action" not in action_data:
                action_data["action"] = "speak"
            if "speed" not in action_data:
                action_data["speed"] = 40
            if "duration" not in action_data:
                action_data["duration"] = 1.0
            if "angle" not in action_data:
                action_data["angle"] = 90
            if "speech" not in action_data:
                action_data["speech"] = ""
            
            # Ограничиваем значения для безопасности
            action_data["speed"] = min(max(int(action_data["speed"]), 0), 100)
            action_data["duration"] = min(max(float(action_data["duration"]), 0.1), MAX_MOVE_DURATION)
            action_data["angle"] = min(max(int(action_data["angle"]), 0), MAX_TURN_ANGLE)
            
            validated_actions.append(action_data)
        
        return validated_actions
                
    except Exception as e:
        print("Ошибка запроса о препятствии: " + str(e))
        # Стандартная реакция при ошибке
        return [{
            "action": "move_backward",
            "speed": 40,
            "duration": 1.5,
            "angle": 0,
            "speech": "Что-то впереди. Лучше отступить."
        }]

def query_gemini(prompt, sensor_data=None, context_type="autonomous"):
    """Запрос к Google Gemini API с поддержкой последовательностей действий"""
    global daily_requests, action_history
    
    if not check_daily_limit():
        return None
    
    if sensor_data is None:
        sensor_data = get_sensor_data()
    
    # Разные системные промпты для разных контекстов
    if context_type == "autonomous":
        system_context = get_context_prompt()
    elif context_type == "button":
        system_context = "Пользователь нажал кнопку. Реагируй быстро и выразительно!"
    elif context_type == "terminal":
        system_context = "Пользователь дал команду: " + prompt
        prompt = "Выполни команду пользователя"
    else:
        system_context = "Что мне сделать?"
    
    situation = get_situation_description(sensor_data)
    
    # Добавляем историю действий для контекста
    history_context = ""
    if action_history:
        recent_actions = action_history[-3:]
        history_context = "\n\nНедавние действия: " + ", ".join(recent_actions)
    
    # Промпт с поддержкой последовательностей
    full_prompt = """Ты - робот EV3RSTORM. Ты можешь отправить ОДИН JSON объект или МАССИВ JSON объектов для последовательности действий.

Формат одного действия:
{
    "action": "move_forward|move_backward|turn_left|turn_right|attack|speak|stop",
    "speed": число от 0 до 100,
    "duration": число в секундах,
    "angle": число в градусах,
    "speech": "текст для озвучивания на русском языке"
}

Формат последовательности действий (массив):
[
  {
    "action": "speak",
    "speed": 0,
    "duration": 0,
    "angle": 0,
    "speech": "Привет! Я собираюсь выполнить несколько действий."
  },
  {
    "action": "move_forward",
    "speed": 50,
    "duration": 2,
    "angle": 0,
    "speech": ""
  },
  {
    "action": "turn_right",
    "speed": 30,
    "duration": 0,
    "angle": 90,
    "speech": "Поворачиваю направо."
  }
]

Ситуация: """ + situation + """
Время: """ + sensor_data['time_of_day'] + history_context + """
Контекст: """ + system_context + """
Запрос: """ + prompt + """

Ограничения:
- Длительность движения не более 3 секунд
- Угол поворота не более 180 градусов
- Скорость моторов от 0 до 100
- Максимум """ + str(MAX_SEQUENCE_ACTIONS) + """ действий в последовательности

Отправь JSON (объект или массив) без каких-либо дополнительных текстов."""
    
    payload = {
        "contents": [{
            "parts": [{
                "text": full_prompt
            }]
        }],
        "generationConfig": {
            "temperature": 0.8,
            "maxOutputTokens": 800,
            "topP": 0.9
        }
    }
    
    headers = {
        "Content-Type": "application/json"
    }
    
    url = "https://generativelanguage.googleapis.com/v1beta/models/" + GEMINI_MODEL + ":generateContent?key=" + GEMINI_API_KEY
    
    try:
        response = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=30
        )
        
        if response.status_code == 429:
            print("Слишком много запросов к Gemini API. Пропускаю.")
            return None
        
        response.raise_for_status()
        
        result = response.json()
        
        if "candidates" not in result or len(result["candidates"]) == 0:
            print("Пустой ответ от Gemini API")
            return None
            
        assistant_message = result["candidates"][0]["content"]["parts"][0]["text"]
        
        daily_requests += 1
        print("Запрос к Gemini (осталось: " + get_remaining_requests() + ")")
        
        # Извлекаем JSON (массив или объект)
        actions_data = extract_json_from_text(assistant_message)
        
        if actions_data is None:
            print("Не удалось извлечь JSON из ответа: " + assistant_message[:100] + "...")
            return None
        
        # Если это не список, делаем его списком
        if not isinstance(actions_data, list):
            actions_data = [actions_data]
        
        # Ограничиваем количество действий
        if len(actions_data) > MAX_SEQUENCE_ACTIONS:
            actions_data = actions_data[:MAX_SEQUENCE_ACTIONS]
            print("Ограничено количество действий до " + str(MAX_SEQUENCE_ACTIONS))
        
        # Валидация каждого действия
        validated_actions = []
        for action_data in actions_data:
            # Валидация полученного JSON
            if "action" not in action_data:
                action_data["action"] = "speak"
            if "speed" not in action_data:
                action_data["speed"] = 50
            if "duration" not in action_data:
                action_data["duration"] = 1.0
            if "angle" not in action_data:
                action_data["angle"] = 90
            if "speech" not in action_data:
                action_data["speech"] = ""
            
            # Ограничиваем значения для безопасности
            action_data["speed"] = min(max(int(action_data["speed"]), 0), 100)
            action_data["duration"] = min(max(float(action_data["duration"]), 0.1), MAX_MOVE_DURATION)
            action_data["angle"] = min(max(int(action_data["angle"]), 0), MAX_TURN_ANGLE)
            
            validated_actions.append(action_data)
        
        # Сохраняем действия в историю
        for action_data in validated_actions:
            action_text = action_data.get("speech", action_data.get("action", "действие"))
            if len(action_text) > 20:
                action_text = action_text[:20] + "..."
            action_history.append(action_text)
            if len(action_history) > 15:
                action_history.pop(0)
        
        return validated_actions
                
    except Exception as e:
        print("Ошибка запроса к Gemini API: " + str(e))
        return None

def execute_single_action(action_data):
    """Выполнение одного действия"""
    action = action_data.get("action", "")
    speech_text = action_data.get("speech", "")
    speed = action_data.get("speed", 50)
    duration = action_data.get("duration", 1.0)
    angle = action_data.get("angle", 90)
    
    print("Действие: " + action)
    if speech_text:
        print("Речь: " + speech_text)
    
    if speech_text:
        speak(speech_text)
    
    try:
        if action == "move_forward":
            move_forward(speed, duration)
        elif action == "move_backward":
            move_backward(speed, duration)
        elif action == "turn_left":
            turn_left(speed, angle)
        elif action == "turn_right":
            turn_right(speed, angle)
        elif action == "attack":
            attack_with_blade(speed, duration)
        elif action == "stop":
            stop_all()
        elif action == "speak":
            pass
        else:
            speak("Хм, интересная команда...")
            
    except Exception as e:
        print("Ошибка выполнения: " + str(e))

def execute_action_sequence(actions_data):
    """Выполнение последовательности действий"""
    global is_performing_action, last_action_time
    
    is_performing_action = True
    
    print("\n" + "="*50)
    print("ВЫПОЛНЕНИЕ ПОСЛЕДОВАТЕЛЬНОСТИ ИЗ " + str(len(actions_data)) + " ДЕЙСТВИЙ")
    print("="*50)
    
    for i, action_data in enumerate(actions_data, 1):
        print("\n--- Действие " + str(i) + " из " + str(len(actions_data)) + " ---")
        execute_single_action(action_data)
        
        # Небольшая пауза между действиями (кроме последнего)
        if i < len(actions_data):
            time.sleep(0.5)
    
    print("\n" + "="*50)
    print("ПОСЛЕДОВАТЕЛЬНОСТЬ ЗАВЕРШЕНА")
    print("="*50)
    
    last_action_time = time.time()
    is_performing_action = False

def autonomous_behavior():
    """Постоянное автономное поведение"""
    while True:
        try:
            # Проверяем препятствие перед любым действием
            if check_obstacle():
                time.sleep(2)
                continue
                
            if is_performing_action:
                time.sleep(0.1)
                continue
                
            if not check_daily_limit():
                time.sleep(10)
                continue
            
            # Ждем случайный интервал
            interval = random.randint(AUTONOMOUS_INTERVAL_MIN, AUTONOMOUS_INTERVAL_MAX)
            time.sleep(interval)
            
            print("\n" + "="*40)
            print("АВТОНОМНОЕ ДЕЙСТВИЕ")
            print("="*40)
            
            sensor_data = get_sensor_data()
            
            # Проверяем, нет ли препятствия перед запросом
            if sensor_data['ir_distance'] < SAFETY_DISTANCE:
                print("Препятствие близко, пропускаю автономное действие")
                time.sleep(2)
                continue
            
            # Случайный выбор типа автономного поведения
            behavior_types = [
                ("autonomous", "Что мне сейчас сделать интересного?"),
                ("autonomous", "Осмотрись вокруг и придумай что-нибудь"),
                ("autonomous", "Прояви свою индивидуальность"),
                ("autonomous", "Покажи, на что ты способен"),
                ("autonomous", "Сделай что-нибудь неожиданное"),
                ("autonomous", "Как ты себя чувствуешь?"),
                ("autonomous", "Что нового вокруг?"),
                ("autonomous", "Расскажи историю и покажи ее")
            ]
            
            context_type, prompt = random.choice(behavior_types)
            actions_data = query_gemini(prompt, sensor_data, context_type)
            
            if actions_data:
                execute_action_sequence(actions_data)
                
        except Exception as e:
            print("Ошибка в автономном поведении: " + str(e))
            time.sleep(5)

def terminal_input_handler():
    """Обработчик ввода из терминала"""
    print("\n" + "="*60)
    print("КОМАНДЫ ДЛЯ РОБОТА:")
    print("- Напишите любую команду и нажмите Enter")
    print("- Примеры: 'поехали вперед', 'расскажи шутку', 'что видишь?'")
    print("- Для выхода: 'выход', 'exit' или 'quit'")
    print("="*60)
    
    while True:
        # Проверяем доступность ввода
        if sys.stdin in select.select([sys.stdin], [], [], 0)[0]:
            user_input = sys.stdin.readline().strip()
            
            if user_input.lower() in ['выход', 'exit', 'quit']:
                print("\n" + "="*50)
                print("ЗАВЕРШЕНИЕ РАБОТЫ")
                print("="*50)
                stop_all()
                os._exit(0)
            
            if user_input:
                terminal_input_queue.append(user_input)
                print("\n[Терминал] Команда добавлена: " + user_input)
        
        time.sleep(0.1)

def process_terminal_commands():
    """Обработка команд из очереди терминала"""
    while True:
        try:
            if terminal_input_queue and not is_performing_action:
                user_input = terminal_input_queue.pop(0)
                print("\n" + "="*40)
                print("ОБРАБОТКА КОМАНДЫ: " + user_input)
                print("="*40)
                
                sensor_data = get_sensor_data()
                
                # Проверяем препятствие перед выполнением команды
                if sensor_data['ir_distance'] < SAFETY_DISTANCE:
                    print("Внимание! Препятствие близко. Сначала нужно его обойти.")
                    actions_data = query_gemini_obstacle(sensor_data)
                    if actions_data:
                        execute_action_sequence(actions_data)
                    continue
                
                actions_data = query_gemini(user_input, sensor_data, "terminal")
                
                if actions_data:
                    execute_action_sequence(actions_data)
            
            time.sleep(0.1)
            
        except Exception as e:
            print("Ошибка обработки команды: " + str(e))
            time.sleep(1)

def main():
    """Основной цикл работы робота"""
    # Очистка экрана при запуске
    os.system('clear' if os.name == 'posix' else 'cls')
    
    print("=" * 60)
    print("РОБОТ EV3RSTORM ЗАПУСКАЕТСЯ")
    print("=" * 60)
    
    # Проверка датчиков
    print("Проверка датчиков:")
    print("- Датчик касания (кнопка): " + ("OK" if touchs else "ОШИБКА"))
    print("- ИК датчик: " + ("OK" if ir_sensor else "ОШИБКА"))
    print("- Датчик цвета: " + ("OK" if color_sensor else "ОШИБКА"))
    if USE_GYRO:
        print("- Гироскоп: " + ("OK" if gyro_sensor else "ОШИБКА"))
    
    print("Используется Gemini API: " + GEMINI_MODEL)
    print("Дневной лимит запросов: " + str(DAILY_REQUEST_LIMIT))
    print("Автономный интервал: " + str(AUTONOMOUS_INTERVAL_MIN) + "-" + str(AUTONOMOUS_INTERVAL_MAX) + " сек")
    print("Расстояние до препятствия: " + str(OBSTACLE_DISTANCE) + " см")
    print("Максимум действий в последовательности: " + str(MAX_SEQUENCE_ACTIONS))
    print("=" * 60)

    speak("Системы активированы. Датчики проверены. Готов к работе!")

    leds.set_color('LEFT', 'AMBER')
    leds.set_color('RIGHT', 'AMBER')
    
    # Запуск автономного поведения
    autonomous_thread = threading.Thread(target=autonomous_behavior, daemon=True)
    autonomous_thread.start()
    
    # Запуск обработчика терминального ввода
    terminal_thread = threading.Thread(target=terminal_input_handler, daemon=True)
    terminal_thread.start()
    
    # Запуск обработчика команд
    command_thread = threading.Thread(target=process_terminal_commands, daemon=True)
    command_thread.start()
    
    try:
        while not button.backspace:
            # Постоянно проверяем препятствия
            check_obstacle()
            
            # Обработка нажатий кнопок (быстрое взаимодействие)
            if touchs.is_pressed:
                if not is_performing_action:
                    print("\n" + "="*30)
                    print("НАЖАТИЕ КНОПКИ")
                    print("="*30)
                    
                    # Проверяем препятствие перед реакцией на кнопку
                    if check_obstacle():
                        time.sleep(1)
                        continue
                    
                    sensor_data = get_sensor_data()
                    actions_data = query_gemini("Реагируй на нажатие кнопки", sensor_data, "button")
                    if actions_data:
                        execute_action_sequence(actions_data)
                time.sleep(0.5)
            
            time.sleep(0.1)
            
    except KeyboardInterrupt:
        print("\n" + "="*50)
        print("ЗАВЕРШЕНИЕ РАБОТЫ")
        print("="*50)
    finally:
        stop_all()
        speak("Завершаю работу. До новых встреч!")
        leds.set_color('LEFT', 'GREEN')
        leds.set_color('RIGHT', 'GREEN')
        print("\nРобот остановлен. Для выхода закройте терминал. Рекомендуется перезапустить систему: sudo reboot")

if __name__ == "__main__":
    main()