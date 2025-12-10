# config.py
# Настройки робота EV3RSTORM с Algion API

# Algion API настройки
ALGION_API_KEY = "your-algion-api-key"
ALGION_MODEL = "gpt-5.1"  # Или другая модель от algion.dev

# Настройки оборудования
USE_GYRO = True

# Интервалы автономного режима (в секундах)
AUTONOMOUS_INTERVAL_MIN = 10
AUTONOMOUS_INTERVAL_MAX = 300

# Ограничения для безопасности
MAX_MOVE_DURATION = 3.0
MAX_TURN_ANGLE = 180
MAX_TURN_DURATION = 5.0
MAX_ATTACK_DURATION = 2.0
MAX_BLADE_SPEED = 100
MAX_MOTOR_SPEED = 75

# Настройки препятствий
OBSTACLE_DISTANCE = 20
SAFETY_DISTANCE = 30

# Настройки последовательностей
MAX_SEQUENCE_ACTIONS = 5

# Настройки лимитов запросов
DAILY_REQUEST_LIMIT = 14400
ENABLE_REQUEST_LIMIT = False