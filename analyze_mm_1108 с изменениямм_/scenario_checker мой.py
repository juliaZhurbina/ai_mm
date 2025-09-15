import json
import os
from docx import Document
from typing import Dict, Tuple
import asyncio

# Импортируем необходимые модули для работы с GigaChat
from gigachat_recomendation import MeetingAnalyzer


class ScenarioChecker:
    """Класс для проверки соответствия встречи сценарию с использованием GigaChat"""

    def __init__(self, prompts_file='scenario_prompts.json'):
        # Настройки для GigaChat
        AUTH_KEY = 'ZGMzMGJmZjEtODQwYS00ZjAwLWI2NjgtNGIyNGNiY2ViNmE1OjYwNjM3NTU0LWQxMDctNDA5ZS1hZWM3LTAwYjQ5MjZkOGU2OA=='
        SCOPE = 'GIGACHAT_API_PERS'
        API_AUTH_URL = 'https://ngw.devices.sberbank.ru:9443/api/v2/oauth'
        API_CHAT_URL = 'https://gigachat.devices.sberbank.ru/api/v1/chat/completions'

        self.analyzer = MeetingAnalyzer(AUTH_KEY, SCOPE, API_AUTH_URL, API_CHAT_URL)

        # Загрузка промптов из файла
        self.prompts_file = prompts_file
        self.scenario_prompts = self._load_prompts()

        # Названия сценариев для отображения
        self.scenario_names = {
            "scenario_online": "ММ онлайн торговля",
            "scenario_first_meetings": "ММ первые встречи",
            "scenario_first_month": "ММ первый месяц"
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

            # Возвращаем результат как есть, без форматирования
            return self._format_final_result(analysis_result, scenario_name)

        except asyncio.TimeoutError:
            return "⏰ Таймаут при запросе к GigaChat. Попробуйте позже."
        except Exception as e:
            error_msg = f"❌ Неожиданная ошибка: {str(e)}"
            return self._escape_telegram_chars(error_msg)

    def _build_full_prompt(self, meeting_text: str, prompt_template: str, scenario_name: str) -> str:
        """Создание полного промпта для анализа"""
        # Ограничиваем длину текста встречи
        if len(meeting_text) > 18000:
            meeting_text = meeting_text[:18000] + "\n\n[Текст обрезан для анализа]"

        return f"""
{prompt_template}

ТЕКСТ ВСТРЕЧИ ДЛЯ АНАЛИЗА:
{meeting_text}

КРИТИЧЕСКИ ВАЖНО: Ты должен ответить ТОЛЬКО в указанном ниже формате. НЕ ИЗМЕНЯЙ структуру, ОТВЕЧАЙ на вопросы в промпте по каждому пункту, особенно с пометкой [ВАЖНО] 
Если общая оценка не соответствует или соответствует частично - дай подробное объяснение в соответствии с критериями проверки. 
ТВОЙ ОТВЕТ ДОЛЖЕН НАЧИНАТЬСЯ ТОЧНО ТАК:

## Анализ соответствия сценарию "{scenario_name}"

### 📊 Общая оценка: 
[✅Соответствует/⚠️Частично соответствует/❌Не соответствует]

1. Подготовка и состав участников
**Оценка:** [✅Выполнено/⚠️Частично выполнено/❌Не выполнено]
💡 **Анализ:**
   - Количество участников (4-8 чел.): [Да/Нет/Не указано]
   - Запросы подготовлены: [Да/Нет/Неясно]
   - Модератор ссылается на запросы: [Да/Нет/Не указано]

2. Контакт и краткий рассказ о формате (5 мин)
**Оценка:** [✅Выполнено/⚠️Частично выполнено/❌Не выполнено]
💡 **Анализ:**
   - Приветствие и тема: [Да/Нет]
   - Обозначена роль модератора [ВАЖНО]: [Да/Нет]
   - Актуализирован формат ММ [ВАЖНО]: [Да/Нет/Для новичков/Для бывалых]
   - Пояснен состав группы [ВАЖНО]: [Да/Нет]
   - Обозначена цель ММ [ВАЖНО]: [Да/Нет]

3. Организационные моменты (5 мин)
**Оценка:** [✅Выполнено/⚠️Частично выполнено/❌Не выполнено]
💡 **Анализ:**
   - Озвучены время и кол-во кейсов: [Да/Нет]
   - Озвучены правила [ВАЖНО]: [Активность, Конфиденциальность, Тайминг, Поддержка]
   - Получено явное согласие на правила [ВАЖНО]: [Да/Нет/Не указано]

4. Знакомство и разогрев (до 10 мин)
**Оценка:** [✅Выполнено/⚠️Частично выполнено/❌Не выполнено]
💡 **Анализ:**
   - Модератор начал первым: [Да/Нет]
   - Контроль времени (макс 1 мин) [ВАЖНО]: [Да/Нет/Указание на превышение]
   - Этап резюмирован: [Да/Нет/Не указано]
   - Смысловой мостик к работе [ВАЖНО]: [Да/Нет]

5. Проработка запросов
**Оценка:** [✅Выполнено/⚠️Частично выполнено/❌Не выполнено]
💡 *Общая оценка этапа*

5.1. Клиентский кейс (4 мин)
**Оценка:** [✅Выполнено/⚠️Частично выполнено/❌Не выполнено]
💡 **Анализ:**
   - Фокус на 5 пунктах (бизнес, клиент...) [ВАЖНО]: [Полностью/Частично/Нет]
   - Контроль времени (макс 3 мин) [ВАЖНО]: [Да/Нет/Не применимо]
   - Проведено голосование: [Да/Нет/Не указано]

5.2. От рассказа к запросу (3 мин)
**Оценка:** [✅Выполнено/⚠️Частично выполнено/❌Не выполнено]
💡 **Анализ:**
   - Заданы 4 ключевых вопроса [ВАЖНО]: [Все/Часть/Нет] ([1.Вопрос, 2.Важность, 3.Предпринятое, 4.Варианты])

5.3. Уточнение запроса (до 10 мин)
**Оценка:** [✅Выполнено/⚠️Частично выполнено/❌Не выполнено]
💡 **Анализ:**
   - Участники задают уточняющие вопросы (1-2 на чел.) [ВАЖНО]: [Да/Нет/Не все]
   - Вопросы на прояснение, а не советы [ВАЖНО]: [Да/Нет/Есть советы]
   - Модератор задал вопросы при необходимости [ВАЖНО]: [Да/Нет/Не требовалось]

5.4. Правила для автора (2 мин)
**Оценка:** [✅Выполнено/⚠️Частично выполнено/❌Не выполнено]
💡 **Анализ:**
   - Правила озвучены (не показывать реакцию, фиксировать) [ВАЖНО]: [Да/Нет]

5.5. Окончательная формулировка запроса
**Оценка:** [✅Выполнено/⚠️Частично выполнено/❌Не выполнено]
💡 **Анализ:**
   - Запрос сформулирован как «Поделитесь опытом, как вы...» [ВАЖНО]: [Да/Нет/Частично]
   - Запрос практико-ориентированный: [Да/Нет]

5.6. Обмен опытом (2 мин на каждого)
**Оценка:** [✅Выполнено/⚠️Частично выполнено/❌Не выполнено]
💡 **Анализ:**
   - Правила озвучены (делиться опытом, а не советовать) [ВАЖНО]: [Да/Нет]
   - Вовлечены все участники [ВАЖНО]: [Да/Нет]
   - Контроль времени и содержания: [Да/Нет]
   - Модератор поделился опытом последним [ВАЖНО]: [Да/Нет/Не участвовал]

5.7. ОС от автора запроса (3 мин)
**Оценка:** [✅Выполнено/⚠️Частично выполнено/❌Не выполнено]
💡 **Анализ:**
   - Заданы 3 ключевых вопроса [ВАЖНО]: [Все/Часть/Нет] ([1.Ценные идеи, 2.3 действия, 3.К кому обратиться])
   - Помощь в формировании действий: [Да/Нет/Не требовалось]

6. Итоги мастермайнда (1-2 мин на каждого)
**Оценка:** [✅Выполнено/⚠️Частично выполнено/❌Не выполнено]
💡 **Анализ:**
   - Собрана ОС по 3 вопросам [ВАЖНО]: [Все/Часть/Нет] ([1.Что полезно, 2.Эмоции, 3.Конкретные действия])
   - Модератор подвел итоги (наблюдения, итоги, мотивация) [ВАЖНО]: [Да/Нет/Частично]

### 🎯 Итоговый вывод:
*Краткое резюме: сильные стороны и основные области для улучшения. Дайте рекомендации на будущее, основанные на выявленных отклонениях.*
"""

    async def _execute_gigachat_request(self, prompt: str) -> str:
        """Выполнение запроса к GigaChat"""
        try:
            # Временная установка промпта через прямое присваивание
            # (предполагая, что в MeetingAnalyzer есть атрибут prompt)
            original_prompt = getattr(self.analyzer, 'prompt', None)

            # Устанавливаем новый промпт
            if hasattr(self.analyzer, 'prompt'):
                self.analyzer.prompt = prompt
            elif hasattr(self.analyzer, 'set_prompt'):
                self.analyzer.set_prompt(prompt)
            else:
                # Если нет стандартного способа, используем monkey patching
                self.analyzer.prompt = prompt

            # Вызываем analyze_meeting БЕЗ параметров
            result = self.analyzer.analyze_meeting()

            # Если результат - корутина, ждем ее завершения
            if asyncio.iscoroutine(result):
                result = await result

            # Восстанавливаем оригинальный промпт если нужно
            if original_prompt is not None and hasattr(self.analyzer, 'prompt'):
                self.analyzer.prompt = original_prompt

            return result

        except Exception as e:
            error_msg = f"Ошибка GigaChat API: {str(e)}"
            raise Exception(error_msg)

    def _format_final_result(self, result: str, scenario_name: str) -> str:
        """Форматирование конечного результата для Telegram"""
        scenario_name_escaped = self._escape_telegram_chars(scenario_name)

        # Просто возвращаем результат как есть, добавляя только заголовок
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