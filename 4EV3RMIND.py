#!/usr/bin/env python3

import json
import requests
import subprocess
import time
import random
import threading
import sys
import select
from datetime import datetime, timedelta
from ev3dev2.motor import LargeMotor, MediumMotor, OUTPUT_A, OUTPUT_B, OUTPUT_C
from ev3dev2.sensor import INPUT_1, INPUT_2, INPUT_3, INPUT_4
from ev3dev2.sensor.lego import InfraredSensor, ColorSensor, GyroSensor
from ev3dev2.button import Button

# Настройки из config.py
try:
    from config import *
except ImportError:
    # Значения по умолчанию
    GEMINI_API_KEY = "your_api_key"
    GEMINI_MODEL = "gemma-3-27b-it"
    USE_GYRO = True
    AUTONOMOUS_INTERVAL_MIN = 10
    AUTONOMOUS_INTERVAL_MAX = 30
    MAX_MOVE_DURATION = 3.0
    MAX_TURN_ANGLE = 180
    MAX_ATTACK_DURATION = 2.0
    MAX_BLADE_SPEED = 100
    MAX_MOTOR_SPEED = 75
    DAILY_REQUEST_LIMIT = 14400
    ENABLE_REQUEST_LIMIT = True

# Инициализация моторов
left_motor = LargeMotor(OUTPUT_B)
right_motor = LargeMotor(OUTPUT_C)
blade_motor = MediumMotor(OUTPUT_A)

# Инициализация датчиков
ir_sensor = InfraredSensor(INPUT_4)
color_sensor = ColorSensor(INPUT_3)
button = Button()

if USE_GYRO:
    gyro_sensor = GyroSensor(INPUT_2)

# Глобальные переменные для управления
daily_requests = 0
daily_reset_time = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
is_performing_action = False
terminal_input_queue = []

def speak(text):
    """Озвучивание текста через espeak"""
    try:
        subprocess.run(['espeak', '-v', 'ru', '-s', '150', text], check=False)
        print("Робот говорит: " + text)
    except Exception as e:
        print("Ошибка озвучивания: " + str(e))

def get_sensor_data():
    """Получение данных с датчиков"""
    sensor_data = {
        "ir_distance": ir_sensor.proximity,
        "color": color_sensor.color_name,
        "buttons": button.buttons_pressed,
        "gyro_connected": USE_GYRO,
        "timestamp": time.time()
    }
    
    if USE_GYRO:
        sensor_data["gyro_angle"] = gyro_sensor.angle
        sensor_data["gyro_rate"] = gyro_sensor.rate
    
    return sensor_data

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
    """Движение вперед с ограничением времени"""
    duration = min(duration, MAX_MOVE_DURATION)
    speed = min(speed, MAX_MOTOR_SPEED)
    
    left_motor.on(speed)
    right_motor.on(speed)
    time.sleep(duration)
    left_motor.off()
    right_motor.off()

def move_backward(speed=50, duration=1.0):
    """Движение назад с ограничением времени"""
    duration = min(duration, MAX_MOVE_DURATION)
    speed = min(speed, MAX_MOTOR_SPEED)
    
    left_motor.on(-speed)
    right_motor.on(-speed)
    time.sleep(duration)
    left_motor.off()
    right_motor.off()

def turn_left(speed=30, angle=90):
    """Поворот налево с ограничением угла"""
    angle = min(angle, MAX_TURN_ANGLE)
    speed = min(speed, MAX_MOTOR_SPEED)
    
    if USE_GYRO:
        initial_angle = gyro_sensor.angle
        left_motor.on(-speed)
        right_motor.on(speed)
        while gyro_sensor.angle > initial_angle - angle:
            time.sleep(0.01)
    else:
        left_motor.on(-speed)
        right_motor.on(speed)
        time.sleep(angle / 90 * 0.5)
    left_motor.off()
    right_motor.off()

def turn_right(speed=30, angle=90):
    """Поворот направо с ограничением угла"""
    angle = min(angle, MAX_TURN_ANGLE)
    speed = min(speed, MAX_MOTOR_SPEED)
    
    if USE_GYRO:
        initial_angle = gyro_sensor.angle
        left_motor.on(speed)
        right_motor.on(-speed)
        while gyro_sensor.angle < initial_angle + angle:
            time.sleep(0.01)
    else:
        left_motor.on(speed)
        right_motor.on(-speed)
        time.sleep(angle / 90 * 0.5)
    left_motor.off()
    right_motor.off()

def attack_with_blade(speed=100, duration=1.0):
    """Атака лезвием с ограничением времени"""
    duration = min(duration, MAX_ATTACK_DURATION)
    speed = min(speed, MAX_BLADE_SPEED)
    
    blade_motor.on(speed)
    time.sleep(duration)
    blade_motor.off()

def stop_all():
    """Остановка всех моторов"""
    left_motor.off()
    right_motor.off()
    blade_motor.off()

def query_gemini(prompt, sensor_data=None):
    """Запрос к Google Gemini API"""
    global daily_requests
    
    if not check_daily_limit():
        speak("Лимит запросов на сегодня исчерпан")
        return None
    
    if sensor_data is None:
        sensor_data = get_sensor_data()
    
    full_prompt = """Ты - робот EV3RSTORM. Отвечай ТОЛЬКО в JSON формате без каких-либо дополнительных текстов:

{
    "action": "move_forward|move_backward|turn_left|turn_right|attack|speak|stop",
    "speed": число от 0 до 100,
    "duration": число в секундах,
    "angle": число в градусах,
    "speech": "текст для озвучивания на русском"
}

Ограничения: 
- Длительность движения не более 3 секунд
- Угол поворота не более 180 градусов
- Скорость моторов 0-100

Текущие данные с датчиков:
- Расстояние: """ + str(sensor_data['ir_distance']) + """
- Цвет: """ + str(sensor_data['color']) + """
- Кнопки: """ + str(sensor_data['buttons']) + """

""" + prompt
    
    payload = {
        "contents": [{
            "parts": [{
                "text": full_prompt
            }]
        }],
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 200,
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
        
        # Очистка ответа от возможных markdown форматирования
        cleaned_message = assistant_message.strip()
        if cleaned_message.startswith("```json"):
            cleaned_message = cleaned_message[7:]
        if cleaned_message.endswith("```"):
            cleaned_message = cleaned_message[:-3]
        cleaned_message = cleaned_message.strip()
        
        try:
            return json.loads(cleaned_message)
        except json.JSONDecodeError:
            print("Ошибка парсинга JSON: " + cleaned_message)
            # Попытка извлечь JSON из текста
            import re
            json_match = re.search(r'\{[^{}]*\}', cleaned_message)
            if json_match:
                return json.loads(json_match.group())
            else:
                return {"action": "speak", "speech": "Ошибка в формате ответа"}
                
    except Exception as e:
        print("Ошибка запроса к Gemini API: " + str(e))
        return None

def execute_action(action_data):
    """Выполнение действия на основе данных от нейросети"""
    global is_performing_action
    
    is_performing_action = True
    
    action = action_data.get("action", "")
    speech_text = action_data.get("speech", "")
    speed = action_data.get("speed", 50)
    duration = action_data.get("duration", 1.0)
    angle = action_data.get("angle", 90)
    
    print("Действие: " + action)
    
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
            speak("Неизвестная команда")
            
    except Exception as e:
        print("Ошибка выполнения: " + str(e))
        speak("Ошибка выполнения")
    
    is_performing_action = False

def autonomous_behavior():
    """Постоянное автономное поведение"""
    while True:
        try:
            if is_performing_action:
                time.sleep(0.1)
                continue
                
            if not check_daily_limit():
                time.sleep(10)
                continue
            
            # Ждем случайный интервал
            interval = random.randint(AUTONOMOUS_INTERVAL_MIN, AUTONOMOUS_INTERVAL_MAX)
            time.sleep(interval)
            
            print("Автономное действие...")
            sensor_data = get_sensor_data()
            
            # Случайный выбор темы для автономного поведения
            topics = [
                "Что мне сейчас сделать?",
                "Осмотрись вокруг и реши что делать",
                "Прояви инициативу и сделай что-нибудь интересное",
                "Проверь обстановку и действуй соответственно",
                "Расскажи что-нибудь интересное и покажи это действием",
                "Что ты думаешь о текущей ситуации?"
            ]
            
            prompt = random.choice(topics)
            action_data = query_gemini(prompt, sensor_data)
            
            if action_data:
                execute_action(action_data)
                
        except Exception as e:
            print("Ошибка в автономном поведении: " + str(e))
            time.sleep(5)

def terminal_input_handler():
    """Обработчик ввода из терминала"""
    print("\nВведите команду для робота (или 'выход' для завершения):")
    
    while True:
        # Проверяем доступность ввода
        if sys.stdin in select.select([sys.stdin], [], [], 0)[0]:
            user_input = sys.stdin.readline().strip()
            
            if user_input.lower() in ['выход', 'exit', 'quit']:
                print("Завершение работы...")
                stop_all()
                sys.exit(0)
            
            if user_input:
                terminal_input_queue.append(user_input)
                print("Команда добавлена в очередь: " + user_input)
        
        time.sleep(0.1)

def process_terminal_commands():
    """Обработка команд из очереди терминала"""
    while True:
        try:
            if terminal_input_queue and not is_performing_action:
                user_input = terminal_input_queue.pop(0)
                print("Обрабатываю команду: " + user_input)
                
                sensor_data = get_sensor_data()
                action_data = query_gemini(user_input, sensor_data)
                
                if action_data:
                    execute_action(action_data)
            
            time.sleep(0.1)
            
        except Exception as e:
            print("Ошибка обработки команды: " + str(e))
            time.sleep(1)

def main():
    """Основной цикл работы робота"""
    print("=" * 50)
    print("Робот EV3RSTORM запускается...")
    print("Используется Gemini API: " + GEMINI_MODEL)
    print("Дневной лимит запросов: " + str(DAILY_REQUEST_LIMIT))
    print("=" * 50)
    speak("Привет! Я EV3RSTORM. Работаю в автономном режиме!")
    speak("В любой момент вы можете написать мне команду в терминале.")
    
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
            # Обработка нажатий кнопок (быстрое взаимодействие)
            if button.any() and not button.backspace:
                if not is_performing_action:
                    print("Нажата кнопка - быстрое взаимодействие")
                    sensor_data = get_sensor_data()
                    action_data = query_gemini("Реагируй на нажатие кнопки", sensor_data)
                    if action_data:
                        execute_action(action_data)
                time.sleep(0.5)
            
            time.sleep(0.1)
            
    except KeyboardInterrupt:
        print("\nЗавершение работы...")
    finally:
        stop_all()
        speak("Завершаю работу. До свидания!")
        print("Робот остановлен")

if __name__ == "__main__":
    main()