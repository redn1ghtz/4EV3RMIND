# config.py
# Настройки робота EV3RSTORM с Gemini API

# Google Gemini API настройки
GEMINI_API_KEY = "your-google-api-key"
GEMINI_MODEL = "gemma-3-27b-it"  # Модель Gemma 3 27B

# Настройки оборудования
USE_GYRO = True

# Интервалы автономного режима (в секундах)
AUTONOMOUS_INTERVAL_MIN = 10
AUTONOMOUS_INTERVAL_MAX = 300

# Ограничения для безопасности
MAX_MOVE_DURATION = 3.0
MAX_TURN_ANGLE = 180
MAX_TURN_DURATION = 5.0  # Максимальное время поворота
MAX_ATTACK_DURATION = 2.0
MAX_BLADE_SPEED = 100
MAX_MOTOR_SPEED = 75

# Настройки препятствий
OBSTACLE_DISTANCE = 20  # Расстояние до препятствия в сантиметрах
SAFETY_DISTANCE = 30    # Безопасное расстояние для остановки

# Настройки последовательностей
MAX_SEQUENCE_ACTIONS = 5  # Максимальное количество действий в последовательности

# Настройки лимитов запросов
DAILY_REQUEST_LIMIT = 14400
ENABLE_REQUEST_LIMIT = True