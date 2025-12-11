# config_openrouter.py
# Настройки робота EV3RSTORM с OpenRouter API

# OpenRouter API настройки
OPENROUTER_API_KEY = "your-openrouter-api-key"
OPENROUTER_MODEL = "nousresearch/hermes-3-llama-3.1-405b:free"  # Модель

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
DAILY_REQUEST_LIMIT = 1000
ENABLE_REQUEST_LIMIT = True