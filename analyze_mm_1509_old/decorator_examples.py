"""
Примеры создания собственных декораторов для начинающих
"""

import time
import logging
from functools import wraps
from datetime import datetime

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ============================================================================
# ПРИМЕР 1: Простейший декоратор - логирование вызова функции
# ============================================================================

def log_function_call(func):
    """
    Простой декоратор, который выводит сообщение при вызове функции
    """
    def wrapper(*args, **kwargs):
        print(f"🔔 Вызвана функция: {func.__name__}")
        result = func(*args, **kwargs)
        print(f"✅ Функция {func.__name__} завершена")
        return result
    return wrapper


# Использование:
@log_function_call
def greet(name):
    print(f"Привет, {name}!")
    return f"Поприветствовали {name}"

# Вызов:
# result = greet("Алексей")
# Выведет:
# 🔔 Вызвана функция: greet
# Привет, Алексей!
# ✅ Функция greet завершена


# ============================================================================
# ПРИМЕР 2: Декоратор с параметрами - измерение времени выполнения
# ============================================================================

def measure_time(func):
    """
    Декоратор, который измеряет время выполнения функции
    """
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        execution_time = end_time - start_time
        print(f"⏱️ Функция {func.__name__} выполнялась {execution_time:.2f} секунд")
        return result
    return wrapper


# Использование:
@measure_time
def slow_function():
    """Функция, которая что-то долго делает"""
    time.sleep(1)  # Имитация долгой работы
    return "Готово!"

# Вызов:
# result = slow_function()
# Выведет: ⏱️ Функция slow_function выполнялась 1.00 секунд


# ============================================================================
# ПРИМЕР 3: Декоратор с @wraps - сохраняет метаданные функции
# ============================================================================

def log_with_metadata(func):
    """
    Декоратор с @wraps - сохраняет имя и документацию оригинальной функции
    """
    @wraps(func)  # Важно! Сохраняет метаданные функции
    def wrapper(*args, **kwargs):
        logger.info(f"Вызов функции: {func.__name__}")
        logger.info(f"Документация: {func.__doc__}")
        result = func(*args, **kwargs)
        return result
    return wrapper


@log_with_metadata
def analyze_text(text):
    """
    Анализирует текст и возвращает результат
    
    Args:
        text: текст для анализа
    
    Returns:
        результат анализа
    """
    return f"Проанализирован текст: {text[:50]}..."


# ============================================================================
# ПРИМЕР 4: Декоратор для обработки ошибок
# ============================================================================

def handle_errors(func):
    """
    Декоратор, который ловит ошибки и логирует их
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            error_msg = f"❌ Ошибка в функции {func.__name__}: {str(e)}"
            logger.error(error_msg)
            return error_msg
    return wrapper


# Использование:
@handle_errors
def risky_function(x, y):
    """Функция, которая может упасть с ошибкой"""
    return x / y  # Может вызвать ZeroDivisionError

# Вызов:
# result = risky_function(10, 0)
# Выведет: ❌ Ошибка в функции risky_function: division by zero


# ============================================================================
# ПРИМЕР 5: Декоратор для логирования в файл (применимо к вашему проекту)
# ============================================================================

def log_to_file(log_file="function_calls.log"):
    """
    Декоратор, который логирует вызовы функций в файл
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            log_message = f"[{timestamp}] Вызвана функция: {func.__name__}"
            
            # Логируем в файл
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write(log_message + "\n")
            
            result = func(*args, **kwargs)
            return result
        return wrapper
    return decorator


# Использование:
@log_to_file("analysis.log")
def analyze_meeting(file_path):
    """Анализирует встречу"""
    return f"Анализ файла: {file_path}"


# ============================================================================
# ПРИМЕР 6: Декоратор для проверки аргументов
# ============================================================================

def validate_file_path(func):
    """
    Декоратор, который проверяет существование файла перед выполнением функции
    """
    @wraps(func)
    def wrapper(file_path, *args, **kwargs):
        import os
        if not os.path.exists(file_path):
            return f"❌ Файл не найден: {file_path}"
        return func(file_path, *args, **kwargs)
    return wrapper


# Использование:
@validate_file_path
def read_meeting_file(file_path):
    """Читает файл встречи"""
    with open(file_path, 'r', encoding='utf-8') as f:
        return f.read()


# ============================================================================
# ПРИМЕР 7: Декоратор для кэширования результатов
# ============================================================================

def cache_result(func):
    """
    Простой декоратор для кэширования результатов функции
    """
    cache = {}
    
    @wraps(func)
    def wrapper(*args, **kwargs):
        # Создаем ключ из аргументов
        cache_key = str(args) + str(kwargs)
        
        # Если результат уже есть в кэше, возвращаем его
        if cache_key in cache:
            print(f"💾 Используем кэш для {func.__name__}")
            return cache[cache_key]
        
        # Иначе вычисляем и сохраняем в кэш
        result = func(*args, **kwargs)
        cache[cache_key] = result
        print(f"💾 Сохранили в кэш результат {func.__name__}")
        return result
    
    return wrapper


# Использование:
@cache_result
def expensive_calculation(n):
    """Дорогая операция"""
    time.sleep(0.5)  # Имитация долгой работы
    return n * 2

# Первый вызов - вычисляется
# result1 = expensive_calculation(5)  # Выведет: 💾 Сохранили в кэш...

# Второй вызов с теми же аргументами - берется из кэша
# result2 = expensive_calculation(5)  # Выведет: 💾 Используем кэш...


# ============================================================================
# ПРИМЕР 8: Комбинирование декораторов (стек декораторов)
# ============================================================================

@handle_errors
@measure_time
@log_function_call
def complex_analysis(file_path):
    """
    Пример функции с несколькими декораторами
    Декораторы применяются снизу вверх!
    """
    print(f"Анализирую файл: {file_path}")
    time.sleep(0.1)
    return "Анализ завершен"


# ============================================================================
# ПРИМЕР 9: Декоратор для асинхронных функций (как в вашем проекте)
# ============================================================================

def async_log_time(func):
    """
    Декоратор для измерения времени выполнения асинхронных функций
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        start_time = time.time()
        result = await func(*args, **kwargs)
        end_time = time.time()
        execution_time = end_time - start_time
        logger.info(f"⏱️ Асинхронная функция {func.__name__} выполнялась {execution_time:.2f} сек")
        return result
    return wrapper


# Использование:
import asyncio

@async_log_time
async def async_analyze(file_path):
    """Асинхронный анализ"""
    await asyncio.sleep(0.1)  # Имитация асинхронной работы
    return f"Проанализирован: {file_path}"


# ============================================================================
# ПРИМЕР 10: Декоратор с параметрами (более сложный)
# ============================================================================

def retry(max_attempts=3, delay=1):
    """
    Декоратор с параметрами - повторяет выполнение функции при ошибке
    
    Args:
        max_attempts: максимальное количество попыток
        delay: задержка между попытками в секундах
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_attempts:
                        raise e
                    print(f"⚠️ Попытка {attempt} не удалась. Повтор через {delay} сек...")
                    time.sleep(delay)
        return wrapper
    return decorator


# Использование:
@retry(max_attempts=3, delay=1)
def unstable_function():
    """Функция, которая может упасть"""
    import random
    if random.random() < 0.7:  # 70% вероятность ошибки
        raise Exception("Случайная ошибка!")
    return "Успех!"


# ============================================================================
# ПРИМЕР 11: Практический пример для вашего проекта
# ============================================================================

def log_analysis(func):
    """
    Декоратор для логирования анализа встреч (можно применить к check_success_criteria)
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        # Логируем начало анализа
        file_path = kwargs.get('file_path') or (args[0] if args else None)
        logger.info(f"🔍 Начало анализа: {func.__name__}")
        logger.info(f"📄 Файл: {file_path}")
        
        start_time = time.time()
        
        try:
            # Выполняем функцию
            result = await func(*args, **kwargs)
            
            # Логируем успешное завершение
            execution_time = time.time() - start_time
            logger.info(f"✅ Анализ завершен за {execution_time:.2f} сек")
            logger.info(f"📊 Длина результата: {len(result)} символов")
            
            return result
            
        except Exception as e:
            # Логируем ошибку
            logger.error(f"❌ Ошибка в {func.__name__}: {str(e)}")
            raise
    
    return wrapper


# Пример применения к вашей функции:
# @log_analysis
# async def check_success_criteria(file_path=None, user_id=None):
#     ... ваш код ...


# ============================================================================
# ТЕСТИРОВАНИЕ ПРИМЕРОВ
# ============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("ТЕСТИРОВАНИЕ ДЕКОРАТОРОВ")
    print("=" * 60)
    
    # Пример 1
    print("\n1. Тест log_function_call:")
    greet("Иван")
    
    # Пример 2
    print("\n2. Тест measure_time:")
    slow_function()
    
    # Пример 3
    print("\n3. Тест handle_errors:")
    risky_function(10, 0)
    
    # Пример 4
    print("\n4. Тест validate_file_path:")
    result = read_meeting_file("несуществующий_файл.txt")
    print(result)
    
    # Пример 5
    print("\n5. Тест cache_result:")
    expensive_calculation(10)
    expensive_calculation(10)  # Второй раз из кэша
    
    # Пример 6
    print("\n6. Тест комбинированных декораторов:")
    complex_analysis("test.docx")
    
    print("\n" + "=" * 60)
    print("✅ Все примеры выполнены!")
    print("=" * 60)
