import json
import os
from docx import Document
from typing import Dict, Tuple
import asyncio
from gigachat import GigaChat
import logging

# Импортируем необходимые модули для работы с GigaChat
from giga_recomendation import MeetingAnalyzer

# Импортируем RAG систему для улучшения промптов
try:
    from rag_system import get_rag_system
    RAG_AVAILABLE = True
    logging.info("RAG система доступна для улучшения промптов")
except ImportError:
    RAG_AVAILABLE = False
    logging.warning("RAG система недоступна. Промпты будут использоваться без улучшения.")


class ScenarioChecker:
    """Класс для проверки соответствия встречи сценарию с использованием GigaChat"""

    def __init__(self, prompts_file='scenario_prompts.json', use_rag=True):
        # Настройки для GigaChat
        AUTH_KEY = 'ZGMzMGJmZjEtODQwYS00ZjAwLWI2NjgtNGIyNGNiY2ViNmE1OjY1MzcyY2I3LWEwMjUtNDkyYi04ZjJhLTEyNmRkMjM2NDNhYg=='
        SCOPE = 'GIGACHAT_API_PERS'
        API_AUTH_URL = 'https://ngw.devices.sberbank.ru:9443/api/v2/oauth'
        API_CHAT_URL = 'https://gigachat.devices.sberbank.ru/api/v1/chat/completions'

        self.analyzer = MeetingAnalyzer(AUTH_KEY, SCOPE, API_AUTH_URL, API_CHAT_URL)

        # Инициализация RAG системы (если доступна)
        self.use_rag = use_rag and RAG_AVAILABLE
        self.rag_system = None
        
        if self.use_rag:
            try:
                self.rag_system = get_rag_system()
                logging.info("✅ RAG система подключена для улучшения промптов")
            except Exception as e:
                logging.warning(f"Не удалось инициализировать RAG: {e}")
                self.use_rag = False
        else:
            logging.info("RAG отключена, используем базовые промпты")

        # Загрузка промптов из файла
        self.prompts_file = prompts_file
        self.scenario_prompts = self._load_prompts()

        # Названия сценариев для отображения
        self.scenario_names = {
            "scenario_online": "ММ онлайн торговля",
            "scenario_first_meetings": "ММ первые встречи",
            "scenario_first_month": "ММ первый месяц",
            "scenario_my_meetings": "ММ мои встречи",
            "scenario_universal": "ММ универсальный сценарий"
        }

    def _load_prompts(self):
        """Загрузка промптов из JSON файла"""
        try:
            with open(self.prompts_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            raise Exception(f"Файл с промптами {self.prompts_file} не найден")
        except json.JSONDecodeError:
            raise Exception(f"Ошибка чтения JSON из файла {self.prompts_file}")

    def _escape_telegram_chars(self, text: str) -> str:
        """Экранирование специальных символов для Telegram"""
        escape_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
        for char in escape_chars:
            text = text.replace(char, f'\\{char}')
        return text

    def read_docx_file(self, file_path: str) -> str:
        """Чтение текста из DOCX файла"""
        try:
            doc = Document(file_path)
            text = '\n'.join([paragraph.text for paragraph in doc.paragraphs if paragraph.text.strip()])
            return text
        except Exception as e:
            error_msg = f"Ошибка чтения файла: {str(e)}"
            raise Exception(self._escape_telegram_chars(error_msg))

    async def analyze_scenario_with_gigachat(self, text: str, scenario_type: str) -> str:
        """Анализ сценария с помощью GigaChat"""
        try:
            if not text.strip():
                return "❌ Текст встречи пуст"

            if scenario_type not in self.scenario_prompts:
                available_scenarios = ", ".join(self.scenario_prompts.keys())
                return f"❌ Неизвестный тип сценария: {scenario_type}. Доступные: {available_scenarios}"

            # Получаем промпт для конкретного сценария
            prompt_template = self.scenario_prompts[scenario_type]
            scenario_name = self.scenario_names.get(scenario_type, "сценарий")

            # Формируем полный промпт с текстом встречи
            full_prompt = self._build_full_prompt(text, prompt_template, scenario_name)

            # Выполняем запрос к GigaChat
            analysis_result = await self._execute_gigachat_request(full_prompt)

            # Форматируем итоговый результат
            return self._format_final_result(analysis_result, scenario_name)

        except asyncio.TimeoutError:
            return "⏰ Таймаут при запросе к GigaChat. Попробуйте позже."
        except Exception as e:
            error_msg = f"❌ Неожиданная ошибка: {str(e)}"
            return self._escape_telegram_chars(error_msg)

    def _build_full_prompt(self, meeting_text: str, prompt_template: str, scenario_name: str) -> str:
        """
        Создание полного промпта для анализа
        
        Что делает:
        1. Создает базовый промпт с текстом встречи
        2. Если RAG доступна - улучшает промпт контекстом из базы знаний
        3. Возвращает финальный промпт для GigaChat
        """
        # Шаг 1: Создаем базовый промпт
        base_prompt = f"""
{prompt_template}

ТЕКСТ ВСТРЕЧИ ДЛЯ АНАЛИЗА:
{meeting_text}
"""
        
        # Шаг 2: Улучшаем промпт через RAG (если доступна)
        if self.use_rag and self.rag_system:
            try:
                # Определяем тип сценария из scenario_name
                scenario_type = None
                for key, name in self.scenario_names.items():
                    if name == scenario_name:
                        scenario_type = key
                        break
                
                # Если тип не найден, используем универсальный
                if not scenario_type:
                    scenario_type = 'scenario_universal'
                
                # Улучшаем промпт контекстом из базы знаний
                enhanced_prompt = self.rag_system.enhance_prompt(
                    base_prompt=base_prompt,
                    query_text=meeting_text[:2000],  # Используем первые 2000 символов для поиска
                    scenario_type=scenario_type
                )
                
                logging.info(f"✅ Промпт улучшен контекстом из RAG базы знаний (тип: {scenario_type})")
                return enhanced_prompt
                
            except Exception as e:
                logging.warning(f"Ошибка улучшения промпта через RAG: {e}")
                # Если ошибка - возвращаем базовый промпт
                return base_prompt
        
        # Если RAG недоступна - возвращаем базовый промпт
        return base_prompt

    async def _execute_gigachat_request(self, prompt: str) -> str:
        """Выполнение запроса к GigaChat"""
        try:
            # Получаем токен доступа
            if not self.analyzer.is_token_valid() and not self.analyzer.get_access_token():
                return "Ошибка: не удалось получить токен доступа"

            # Отправляем запрос напрямую с нашим промптом
            result = self.analyzer._send_request(prompt)

            return result

        except Exception as e:
            error_msg = f"Ошибка GigaChat API: {str(e)}"
            raise Exception(error_msg)

    def _format_final_result(self, result: str, scenario_name: str) -> str:
        """Форматирование конечного результата для Telegram"""
        scenario_name_escaped = self._escape_telegram_chars(scenario_name)

        # Возвращаем результат как есть, без принудительного форматирования
        return f"""
🎯 *РЕЗУЛЬТАТ АНАЛИЗА: {scenario_name_escaped}*

{result}

📋 *Анализ завершен*
        """


async def check_meeting_scenario(file_path: str, scenario_type: str) -> str:
    """Основная функция проверки сценария"""
    try:
        checker = ScenarioChecker()
        text = checker.read_docx_file(file_path)

        if not text.strip():
            return "❌ Файл пуст или содержит нечитаемый текст"

        analysis_result = await checker.analyze_scenario_with_gigachat(text, scenario_type)
        return analysis_result

    except Exception as e:
        error_msg = f"❌ Ошибка при проверке сценария: {str(e)}"
        checker = ScenarioChecker()
        return checker._escape_telegram_chars(error_msg)


def safe_telegram_message(text: str, max_length: int = 4096) -> list:
    """Подготавливает сообщение для безопасной отправки в Telegram"""
    # Минимальное экранирование для сохранения Markdown от GigaChat
    problem_chars = ['`', '>', '#', '+', '-', '=', '|', '{', '}']
    for char in problem_chars:
        text = text.replace(char, f'\\{char}')

    if len(text) <= max_length:
        return [text]

    parts = []
    while text:
        if len(text) <= max_length:
            parts.append(text)
            break
        else:
            break_index = text.rfind('\n', 0, max_length)
            if break_index == -1:
                break_index = text.rfind('. ', 0, max_length)
            if break_index == -1:
                break_index = max_length

            parts.append(text[:break_index].strip())
            text = text[break_index:].strip()

    return parts
