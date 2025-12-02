# config.py
# Настройки робота EV3RSTORM с Gemini API

# Google Gemini API настройки
GEMINI_API_KEY = "your_api_key"
GEMINI_MODEL = "gemma-3-27b-it"  # Модель Gemma 3 27B

# Настройки оборудования
USE_GYRO = True

# Интервалы автономного режима (в секундах)
AUTONOMOUS_INTERVAL_MIN = 10  # 10 секунд минимальный интервал
AUTONOMOUS_INTERVAL_MAX = 30  # 30 секунд максимальный интервал

# Ограничения для безопасности
MAX_MOVE_DURATION = 3.0
MAX_TURN_ANGLE = 180
MAX_ATTACK_DURATION = 2.0
MAX_BLADE_SPEED = 100
MAX_MOTOR_SPEED = 75

# Настройки лимитов запросов
DAILY_REQUEST_LIMIT = 14400  # 14400 запросов в день
ENABLE_REQUEST_LIMIT = True