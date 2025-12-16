import json
import os
import re
from docx import Document
from typing import Dict, Tuple, List
import asyncio
from datetime import datetime, timedelta

# Импортируем необходимые модули для работы с GigaChat
from giga_recomendation import MeetingAnalyzer


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
            "scenario_first_month": "ММ первый месяц",
            "scenario_my_meetings": "ММ мои встречи"
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
        # Экранируем только те символы, которые могут вызвать проблемы с парсингом
        # Не экранируем символы, которые уже правильно используются в разметке
        escape_chars = ['\\', '`', '~']
        for char in escape_chars:
            text = text.replace(char, f'\\{char}')
        return text

    def _clean_telegram_markup(self, text: str) -> str:
        """Очистка текста от проблемных символов разметки для Telegram"""
        import re
        
        # Удаляем одиночные звездочки, которые не являются частью правильной разметки
        # Оставляем только те, которые используются для жирного текста (**текст**)
        text = re.sub(r'(?<!\*)\*(?!\*)', '', text)
        
        # Удаляем одиночные подчеркивания, которые не являются частью правильной разметки
        # Оставляем только те, которые используются для курсива (__текст__)
        text = re.sub(r'(?<!_)_(?!_)', '', text)
        
        # Удаляем одиночные квадратные скобки
        text = re.sub(r'(?<!\[)\[(?!\[)', '', text)
        text = re.sub(r'(?<!\])\](?!\])', '', text)
        
        # Удаляем одиночные круглые скобки, которые не являются частью ссылок
        # Оставляем только те, которые используются в ссылках [текст](url)
        text = re.sub(r'(?<!\()\((?!http)', '', text)
        text = re.sub(r'(?<!http)\)(?!\))', '', text)
        
        return text

    def _parse_meeting_timestamps(self, text: str) -> List[Dict]:
        """Парсинг временных меток из текста встречи"""
        lines = text.split('\n')
        timestamps = []
        
        for line in lines:
            # Ищем строки с временными метками в формате: 2024-01-01 12:00:00 - Спикер:
            # Поддерживаем различные форматы, включая (распознано)
            match = re.search(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) -\s*(.+?)(?:\s*\([^)]+\))?:', line)
            if match:
                timestamp_str = match.group(1)
                speaker = match.group(2).strip()
                
                # Убираем лишние пробелы и скобки из имени спикера
                speaker = re.sub(r'\s*\([^)]+\)', '', speaker).strip()
                
                try:
                    timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
                    timestamps.append({
                        'time': timestamp,
                        'speaker': speaker,
                        'line': line
                    })
                except ValueError:
                    continue
        
        return timestamps

    def _identify_meeting_sections(self, text: str, scenario_type: str) -> Dict[str, List[str]]:
        """Определение разделов встречи по ключевым словам"""
        sections = {}
        
        # Расширенные ключевые слова для разных разделов в зависимости от сценария
        if scenario_type == "scenario_online":
            sections = {
                "contact_format": [
                    "добро пожаловать", "мастермайнд", "встреча", "онлайн торговля", "принято", "сделаем", "собрались",
                    "добро пожаловать", "привет", "здравствуйте", "начинаем", "стартуем", "формат", "сегодня",
                    "торговля", "онлайн", "интернет", "продажи", "бизнес", "работаем", "встречаемся"
                ],
                "org_moments": [
                    "правила", "время", "кейс", "участник", "активность", "конфиденциальность", "подготовились",
                    "организационные", "оргмоменты", "регламент", "тайминг", "структура", "порядок", "процедуры",
                    "согласие", "согласны", "принимаете", "понятно", "вопросы", "уточнения", "начинаем"
                ],
                "introduction": [
                    "знакомство", "разогрев", "совет", "лет назад", "представьтесь", "опыт", "рассказать", "представляет",
                    "представление", "знакомимся", "расскажите", "кто вы", "ваша история", "ваш опыт", "начнем с",
                    "первым", "начну", "расскажу", "меня зовут", "работаю", "занимаюсь", "делаю"
                ],
                "case_work": [
                    "первый кейс", "второй кейс", "третий кейс", "кейс", "запрос", "клиент", "бизнес", "проблема", "ситуация", "разберём",
                    "проработка", "разбор", "анализ", "рассмотрим", "обсудим", "проблема", "задача", "вопрос",
                    "помогите", "совет", "решение", "как быть", "что делать", "ситуация", "случай", "история"
                ],
                "experience_exchange": [
                    "опыт", "поделитесь", "как вы", "обмен", "решение", "расскажите", "обменяться", "доверия",
                    "ваш опыт", "как решали", "что делали", "как справлялись", "похожая ситуация", "аналогичный",
                    "встречались", "сталкивались", "решали", "справлялись", "делали", "работали", "действовали"
                ],
                "feedback": [
                    "обратная связь", "итоги", "ценность", "полезно", "эмоции", "спасибо", "цель", "собрались",
                    "завершаем", "подводим итоги", "что получили", "что взяли", "что полезного", "что ценного",
                    "благодарю", "спасибо", "до свидания", "до встречи", "увидимся", "всего хорошего"
                ]
            }
        elif scenario_type == "scenario_first_meetings":
            sections = {
                "contact_format": [
                    "добро пожаловать", "мастермайнд", "встреча", "первые встречи", "принято", "сделаем", "собрались",
                    "добро пожаловать", "привет", "здравствуйте", "начинаем", "стартуем", "формат", "сегодня",
                    "первые встречи", "новые клиенты", "знакомство", "встречи", "клиенты", "работаем", "встречаемся"
                ],
                "org_moments": [
                    "правила", "время", "кейс", "участник", "активность", "конфиденциальность", "подготовились",
                    "организационные", "оргмоменты", "регламент", "тайминг", "структура", "порядок", "процедуры",
                    "согласие", "согласны", "принимаете", "понятно", "вопросы", "уточнения", "начинаем"
                ],
                "introduction": [
                    "знакомство", "разогрев", "совет", "лет назад", "представьтесь", "опыт", "рассказать", "представляет",
                    "представление", "знакомимся", "расскажите", "кто вы", "ваша история", "ваш опыт", "начнем с",
                    "первым", "начну", "расскажу", "меня зовут", "работаю", "занимаюсь", "делаю"
                ],
                "case_work": [
                    "первый кейс", "второй кейс", "третий кейс", "кейс", "запрос", "клиент", "бизнес", "проблема", "ситуация", "разберём",
                    "проработка", "разбор", "анализ", "рассмотрим", "обсудим", "проблема", "задача", "вопрос",
                    "помогите", "совет", "решение", "как быть", "что делать", "ситуация", "случай", "история"
                ],
                "experience_exchange": [
                    "опыт", "поделитесь", "как вы", "обмен", "решение", "расскажите", "обменяться", "доверия",
                    "ваш опыт", "как решали", "что делали", "как справлялись", "похожая ситуация", "аналогичный",
                    "встречались", "сталкивались", "решали", "справлялись", "делали", "работали", "действовали"
                ],
                "feedback": [
                    "обратная связь", "итоги", "ценность", "полезно", "эмоции", "спасибо", "цель", "собрались",
                    "завершаем", "подводим итоги", "что получили", "что взяли", "что полезного", "что ценного",
                    "благодарю", "спасибо", "до свидания", "до встречи", "увидимся", "всего хорошего"
                ]
            }
        elif scenario_type == "scenario_first_month":
            sections = {
                "contact_format": [
                    "добро пожаловать", "мастермайнд", "встреча", "первый месяц", "принято", "сделаем", "собрались",
                    "добро пожаловать", "привет", "здравствуйте", "начинаем", "стартуем", "формат", "сегодня",
                    "первый месяц", "начало", "старт", "новый", "месяц", "работаем", "встречаемся"
                ],
                "org_moments": [
                    "правила", "время", "кейс", "участник", "активность", "конфиденциальность", "подготовились",
                    "организационные", "оргмоменты", "регламент", "тайминг", "структура", "порядок", "процедуры",
                    "согласие", "согласны", "принимаете", "понятно", "вопросы", "уточнения", "начинаем"
                ],
                "introduction": [
                    "знакомство", "разогрев", "сказка", "первый месяц", "представьтесь", "опыт", "рассказать", "представляет",
                    "представление", "знакомимся", "расскажите", "кто вы", "ваша история", "ваш опыт", "начнем с",
                    "первым", "начну", "расскажу", "меня зовут", "работаю", "занимаюсь", "делаю", "сказка"
                ],
                "case_work": [
                    "первый кейс", "второй кейс", "третий кейс", "кейс", "запрос", "клиент", "бизнес", "проблема", "ситуация", "разберём",
                    "проработка", "разбор", "анализ", "рассмотрим", "обсудим", "проблема", "задача", "вопрос",
                    "помогите", "совет", "решение", "как быть", "что делать", "ситуация", "случай", "история"
                ],
                "experience_exchange": [
                    "опыт", "поделитесь", "как вы", "обмен", "решение", "расскажите", "обменяться", "доверия",
                    "ваш опыт", "как решали", "что делали", "как справлялись", "похожая ситуация", "аналогичный",
                    "встречались", "сталкивались", "решали", "справлялись", "делали", "работали", "действовали"
                ],
                "feedback": [
                    "обратная связь", "итоги", "ценность", "полезно", "эмоции", "спасибо", "цель", "собрались",
                    "завершаем", "подводим итоги", "что получили", "что взяли", "что полезного", "что ценного",
                    "благодарю", "спасибо", "до свидания", "до встречи", "увидимся", "всего хорошего"
                ]
            }
        elif scenario_type == "scenario_my_meetings":
            sections = {
                "contact_format": [
                    "добро пожаловать", "мастермайнд", "встреча", "мои встречи", "принято", "сделаем", "собрались",
                    "добро пожаловать", "привет", "здравствуйте", "начинаем", "стартуем", "формат", "сегодня",
                    "мои встречи", "личные встречи", "встречи", "клиенты", "работаем", "встречаемся"
                ],
                "org_moments": [
                    "правила", "время", "кейс", "участник", "активность", "конфиденциальность", "подготовились",
                    "организационные", "оргмоменты", "регламент", "тайминг", "структура", "порядок", "процедуры",
                    "согласие", "согласны", "принимаете", "понятно", "вопросы", "уточнения", "начинаем"
                ],
                "introduction": [
                    "знакомство", "разогрев", "совет", "лет назад", "представьтесь", "опыт", "рассказать", "представляет",
                    "представление", "знакомимся", "расскажите", "кто вы", "ваша история", "ваш опыт", "начнем с",
                    "первым", "начну", "расскажу", "меня зовут", "работаю", "занимаюсь", "делаю"
                ],
                "case_work": [
                    "первый кейс", "второй кейс", "третий кейс", "кейс", "запрос", "клиент", "бизнес", "проблема", "ситуация", "разберём",
                    "проработка", "разбор", "анализ", "рассмотрим", "обсудим", "проблема", "задача", "вопрос",
                    "помогите", "совет", "решение", "как быть", "что делать", "ситуация", "случай", "история"
                ],
                "experience_exchange": [
                    "опыт", "поделитесь", "как вы", "обмен", "решение", "расскажите", "обменяться", "доверия",
                    "ваш опыт", "как решали", "что делали", "как справлялись", "похожая ситуация", "аналогичный",
                    "встречались", "сталкивались", "решали", "справлялись", "делали", "работали", "действовали"
                ],
                "feedback": [
                    "обратная связь", "итоги", "ценность", "полезно", "эмоции", "спасибо", "цель", "собрались",
                    "завершаем", "подводим итоги", "что получили", "что взяли", "что полезного", "что ценного",
                    "благодарю", "спасибо", "до свидания", "до встречи", "увидимся", "всего хорошего"
                ]
            }
        
        return sections

    def _calculate_section_timing(self, text: str, timestamps: List[Dict], sections: Dict[str, List[str]]) -> Dict[str, Dict]:
        """Расчет времени для каждого раздела встречи"""
        section_timings = {}
        
        if not timestamps:
            return section_timings
        
        # Сортируем временные метки по времени
        sorted_timestamps = sorted(timestamps, key=lambda x: x['time'])
        
        # Определяем границы разделов по порядку
        section_order = ["contact_format", "org_moments", "introduction", "case_work", "experience_exchange", "feedback"]
        
        # Создаем карту разделов с их позициями
        section_positions = {}
        
        for section_name in section_order:
            if section_name not in sections:
                continue
                
            keywords = sections[section_name]
            
            # Ищем все вхождения ключевых слов для этого раздела
            for timestamp in sorted_timestamps:
                line_lower = timestamp['line'].lower()
                if any(keyword in line_lower for keyword in keywords):
                    if section_name not in section_positions:
                        section_positions[section_name] = []
                    section_positions[section_name].append(timestamp['time'])
        
        # Если разделы не найдены по ключевым словам, используем резервный алгоритм
        if not section_positions:
            section_timings = self._fallback_section_timing(sorted_timestamps)
            return section_timings
        
        # Рассчитываем время для каждого раздела
        for i, section_name in enumerate(section_order):
            if section_name not in section_positions:
                continue
            
            # Берем первое вхождение как начало раздела
            section_start = min(section_positions[section_name])
            section_end = None
            
            # Ищем конец раздела
            if i < len(section_order) - 1:
                next_section = section_order[i + 1]
                if next_section in section_positions:
                    # Берем первое вхождение следующего раздела как конец текущего
                    section_end = min(section_positions[next_section])
                else:
                    # Если следующий раздел не найден, ищем в оставшихся разделах
                    for j in range(i + 1, len(section_order)):
                        if section_order[j] in section_positions:
                            section_end = min(section_positions[section_order[j]])
                            break
            
            # Если конец не найден, используем последнюю временную метку
            if not section_end:
                section_end = sorted_timestamps[-1]['time']
            
            # Ограничиваем максимальное время раздела (чтобы избежать аномалий)
            if section_name == "feedback":
                max_duration_minutes = 15  # Максимум 15 минут на обратную связь
            else:
                max_duration_minutes = 60  # Максимум 1 час на раздел
            
            if section_end > section_start:
                duration = section_end - section_start
                duration_minutes = duration.total_seconds() / 60
                
                # Если время раздела слишком большое, ограничиваем его
                if duration_minutes > max_duration_minutes:
                    duration_minutes = max_duration_minutes
                    section_end = section_start + timedelta(minutes=max_duration_minutes)
                
                section_timings[section_name] = {
                    'start': section_start,
                    'end': section_end,
                    'duration_minutes': duration_minutes
                }
        
        return section_timings

    def _fallback_section_timing(self, sorted_timestamps: List[Dict]) -> Dict[str, Dict]:
        """Резервный алгоритм определения разделов по временным меткам"""
        section_timings = {}
        
        if len(sorted_timestamps) < 2:
            return section_timings
        
        # Разделяем встречу на равные части по времени
        total_duration = (sorted_timestamps[-1]['time'] - sorted_timestamps[0]['time']).total_seconds() / 60
        section_duration = total_duration / 6  # 6 разделов
        
        section_order = ["contact_format", "org_moments", "introduction", "case_work", "experience_exchange", "feedback"]
        start_time = sorted_timestamps[0]['time']
        
        for i, section_name in enumerate(section_order):
            section_start = start_time + timedelta(minutes=i * section_duration)
            section_end = start_time + timedelta(minutes=(i + 1) * section_duration)
            
            # Для последнего раздела используем конец встречи
            if i == len(section_order) - 1:
                section_end = sorted_timestamps[-1]['time']
            
            section_timings[section_name] = {
                'start': section_start,
                'end': section_end,
                'duration_minutes': section_duration
            }
        
        return section_timings

    def _count_cases_in_text(self, text: str) -> int:
        """Подсчет количества кейсов в тексте встречи"""
        lines = text.split('\n')
        case_count = 0
        
        # Ищем явные указания на номера кейсов
        explicit_cases = []
        for line in lines:
            line_lower = line.lower()
            if "первый кейс" in line_lower or "первый запрос" in line_lower:
                explicit_cases.append(1)
            elif "второй кейс" in line_lower or "второй запрос" in line_lower:
                explicit_cases.append(2)
            elif "третий кейс" in line_lower or "третий запрос" in line_lower:
                explicit_cases.append(3)
            elif "четвертый кейс" in line_lower or "четвертый запрос" in line_lower:
                explicit_cases.append(4)
            elif "пятый кейс" in line_lower or "пятый запрос" in line_lower:
                explicit_cases.append(5)
        
        if explicit_cases:
            case_count = max(explicit_cases)
        else:
            # Если явных указаний нет, ищем фразы типа "следующий кейс", "новый кейс"
            case_indicators = ["следующий кейс", "новый кейс", "еще один кейс", "другой кейс"]
            for line in lines:
                line_lower = line.lower()
                for indicator in case_indicators:
                    if indicator in line_lower:
                        case_count += 1
            
            # Если все еще не нашли, считаем по количеству участников (обычно 1 кейс на участника)
            if case_count == 0:
                # Ищем упоминания участников
                participant_count = 0
                for line in lines:
                    line_lower = line.lower()
                    if "участник" in line_lower or "участников" in line_lower:
                        # Ищем числа в контексте участников
                        import re
                        numbers = re.findall(r'\d+', line)
                        if numbers:
                            participant_count = max(participant_count, int(numbers[0]))
                
                if participant_count > 0:
                    case_count = min(participant_count, 3)  # Обычно не более 3 кейсов
                else:
                    case_count = 1  # По умолчанию 1 кейс
        
        return max(1, min(case_count, 5))  # От 1 до 5 кейсов

    def _count_participants_in_text(self, text: str) -> int:
        """Подсчет количества участников в тексте встречи"""
        lines = text.split('\n')
        participant_count = 0
        
        # Ищем явные упоминания количества участников
        for line in lines:
            line_lower = line.lower()
            if "участник" in line_lower or "участников" in line_lower:
                # Ищем числа в контексте участников
                import re
                numbers = re.findall(r'\d+', line)
                if numbers:
                    # Берем первое число, которое может быть количеством участников
                    for num in numbers:
                        num_int = int(num)
                        if 1 <= num_int <= 10:  # Разумный диапазон для участников
                            participant_count = max(participant_count, num_int)
                            break
        
        # Если не нашли явных упоминаний, считаем по именам участников
        if participant_count == 0:
            # Ищем строки с именами участников (формат "Имя:")
            names = set()
            for line in lines:
                if ':' in line and len(line.split(':')[0].strip()) < 50:
                    name = line.split(':')[0].strip()
                    if name and not any(word in name.lower() for word in ['модератор', 'ведущий', 'время', 'встреча']):
                        names.add(name)
            
            participant_count = len(names)
        
        # Если все еще не определили, используем количество кейсов как приближение
        if participant_count == 0:
            participant_count = self._count_cases_in_text(text)
        
        return max(1, min(participant_count, 8))  # От 1 до 8 участников

    def _extract_timings_from_prompt(self, scenario_type: str) -> Dict[str, float]:
        """Извлечение эталонных времен из текста промпта"""
        if scenario_type not in self.scenario_prompts:
            return {}
        
        prompt_text = self.scenario_prompts[scenario_type]
        timings = {}
        
        # Паттерны для поиска времен в промптах
        patterns = {
            "contact_format": [
                r"Контакт и рассказ о формате.*?\((\d+)\s*мин\)",
                r"Этап 1: Контакт и рассказ о формате.*?\(~(\d+)\s*мин\)",
                r"Контакт и краткий рассказ о формате.*?\((\d+)\s*мин\)"
            ],
            "org_moments": [
                r"Организационные моменты.*?\((\d+)\s*мин\)",
                r"Оргмоменты и правила.*?\(~(\d+)\s*мин\)",
                r"Организационные моменты.*?\((\d+)\s*мин\)"
            ],
            "introduction": [
                r"Знакомство и разогрев.*?\(до\s*(\d+)\s*мин\)",
                r"Знакомство и разогрев.*?\((\d+)\s*мин/участника\)",
                r"Этап 3: Знакомство и разогрев.*?\((\d+)\s*мин/участника\)"
            ],
            "case_work_base": [
                r"Клиентский кейс.*?\((\d+)\s*мин\)",
                r"Проработка кейса.*?\((\d+)\s*мин на рассказ\)",
                r"Правильные тайминги.*?\((\d+)\s*мин на рассказ\)"
            ],
            "experience_exchange": [
                r"Обмен опытом.*?\((\d+)\s*мин на каждого\)",
                r"Обмен опытом.*?\((\d+)\s*мин/участника на обмен\)",
                r"Правильные тайминги.*?\((\d+)\s*мин/участника на обмен\)"
            ],
            "feedback": [
                r"Итоги мастермайнда.*?\((\d+)-(\d+)\s*мин на каждого\)",
                r"Этап итогов.*?\((\d+)-(\d+)\s*мин/участника\)",
                r"Сбор обратной связи.*?\((\d+)-(\d+)\s*мин/участника\)"
            ]
        }
        
        for section, pattern_list in patterns.items():
            for pattern in pattern_list:
                import re
                match = re.search(pattern, prompt_text, re.IGNORECASE)
                if match:
                    if section == "feedback":
                        # Для обратной связи берем среднее значение диапазона
                        min_time = int(match.group(1))
                        max_time = int(match.group(2))
                        timings[section] = (min_time + max_time) / 2
                    else:
                        timings[section] = float(match.group(1))
                    break
        
        return timings

    def _get_expected_timings(self, scenario_type: str, case_count: int = 1, participant_count: int = 1) -> Dict[str, float]:
        """Получение ожидаемых таймингов для сценария из промптов"""
        # Извлекаем времена из промпта
        extracted_timings = self._extract_timings_from_prompt(scenario_type)
        
        # Формируем итоговые времена
        expected_timings = {}
        
        # Базовые времена
        expected_timings["contact_format"] = extracted_timings.get("contact_format", 5.0)
        expected_timings["org_moments"] = extracted_timings.get("org_moments", 5.0)
        expected_timings["introduction"] = extracted_timings.get("introduction", 8.0)
        
        # Время на проработку кейсов (умножается на количество кейсов)
        case_work_base = extracted_timings.get("case_work_base", 15.0)
        expected_timings["case_work"] = case_work_base * case_count
        
        # Время на обмен опытом (умножается на количество кейсов)
        experience_base = extracted_timings.get("experience_exchange", 10.0)
        expected_timings["experience_exchange"] = experience_base * case_count
        
        # Время на итоги мастермайнда (умножается на количество участников)
        feedback_base = extracted_timings.get("feedback", 2.0)  # 1-2 мин на каждого, берем среднее 1.5
        expected_timings["feedback"] = feedback_base * participant_count
        
        return expected_timings

    def _get_standard_total_time(self, scenario_type: str, case_count: int = 1, participant_count: int = 1) -> float:
        """Получение эталонного общего времени для сценария с учетом количества кейсов и участников"""
        # Вычисляем общее время из извлеченных времен
        extracted_timings = self._extract_timings_from_prompt(scenario_type)
        
        # Суммируем базовые времена (не зависящие от количества кейсов)
        total_time = 0
        total_time += extracted_timings.get("contact_format", 5.0)
        total_time += extracted_timings.get("org_moments", 5.0)
        total_time += extracted_timings.get("introduction", 8.0)
        
        # Добавляем время на проработку кейсов (умножается на количество кейсов)
        case_work_base = extracted_timings.get("case_work_base", 15.0)
        total_time += case_work_base * case_count
        
        # Добавляем время на обмен опытом (умножается на количество кейсов)
        experience_base = extracted_timings.get("experience_exchange", 10.0)
        total_time += experience_base * case_count
        
        # Добавляем время на итоги (умножается на количество участников)
        feedback_base = extracted_timings.get("feedback", 2.0)  # 1-2 мин на каждого, берем среднее 1.5
        total_time += feedback_base * participant_count
        
        return total_time

    def _analyze_timing_compliance(self, section_timings: Dict[str, Dict], expected_timings: Dict[str, float], scenario_type: str, case_count: int = 1, participant_count: int = 1, user_total_time: float = None, timestamps: List[Dict] = None) -> str:
        """Анализ соответствия таймингов ожидаемым значениям"""
        timing_analysis = []
        timing_analysis.append("⏰ **АНАЛИЗ ТАЙМИНГА:**")
        timing_analysis.append("")
        
        # Рассчитываем фактическое общее время как разность между первым и последним временными метками
        if timestamps and len(timestamps) >= 2:
            first_time = timestamps[0]['time']
            last_time = timestamps[-1]['time']
            total_actual = (last_time - first_time).total_seconds() / 60.0
        else:
            # Fallback: сумма времени разделов
            total_actual = sum(timing['duration_minutes'] for timing in section_timings.values())
        
        total_expected = sum(expected_timings.values())
        
        if total_actual < 5.0:  # Если общее время меньше 5 минут
            timing_analysis.append("⚠️ **ВНИМАНИЕ:** Обнаружен короткий отрывок встречи")
            timing_analysis.append(f"   Фактическое время: {total_actual:.1f} мин")
            timing_analysis.append("   Анализ тайминга может быть неточным для полной встречи")
            timing_analysis.append("")
        
        # Показываем информацию о количестве кейсов
        if case_count > 1:
            timing_analysis.append(f"📋 **Обнаружено кейсов:** {case_count}")
            timing_analysis.append("")
        
        section_names = {
            "contact_format": "Контакт и рассказ о формате",
            "org_moments": "Организационные моменты", 
            "introduction": "Знакомство и разогрев",
            "case_work": "Проработка кейса",
            "experience_exchange": "Обмен опытом",
            "feedback": "Обратная связь и итоги"
        }
        
        for section, expected_time in expected_timings.items():
            if section in section_timings:
                actual_time = section_timings[section]['duration_minutes']
                
                # Определяем статус - для feedback сравниваем время на участника
                if section == "feedback" and participant_count > 1:
                    # Для feedback сравниваем время на одного участника
                    actual_per_participant = actual_time / participant_count
                    expected_per_participant = expected_time / participant_count
                    
                    if actual_per_participant < expected_per_participant - 0.5:  # Значительный недостаток времени
                        status = "⚠️"
                    elif actual_per_participant <= expected_per_participant + 1.0:  # В пределах нормы
                        status = "✅"
                    elif actual_per_participant <= expected_per_participant + 2.0:  # Небольшое превышение
                        status = "⚠️"
                    else:  # Значительное превышение
                        status = "❌"
                else:
                    # Для остальных разделов используем общее время
                    if actual_time < expected_time - 1.0:  # Значительный недостаток времени
                        status = "⚠️"
                    elif actual_time <= expected_time + 1.0:  # В пределах нормы
                        status = "✅"
                    elif actual_time <= expected_time + 2.0:  # Небольшое превышение
                        status = "⚠️"
                    else:  # Значительное превышение
                        status = "❌"
                
                timing_analysis.append(f"{status} **{section_names[section]}:**")
                
                # Для разделов, которые умножаются на количество кейсов или участников, показываем информацию с учётом количества
                if section == "case_work" and case_count > 1:
                    base_time = expected_time / case_count
                    timing_analysis.append(f"   Ожидалось: {expected_time:.0f} мин (на {case_count} кейсов)")
                    timing_analysis.append(f"   📊 Время на кейс: {base_time:.0f} мин")
                elif section == "experience_exchange" and case_count > 1:
                    base_time = expected_time / case_count
                    timing_analysis.append(f"   Ожидалось: {expected_time:.0f} мин (на {case_count} кейсов)")
                    timing_analysis.append(f"   📊 Время на кейс: {base_time:.0f} мин")
                elif section == "feedback" and participant_count > 1:
                    base_time = expected_time / participant_count
                    actual_per_participant = actual_time / participant_count
                    timing_analysis.append(f"   Ожидалось: {expected_time:.0f} мин (на {participant_count} участников)")
                    timing_analysis.append(f"   📊 Время на участника: {base_time:.0f} мин")
                    timing_analysis.append(f"   📊 Фактически на участника: {actual_per_participant:.1f} мин")
                else:
                    timing_analysis.append(f"   Ожидалось: {expected_time:.0f} мин")
                
                timing_analysis.append(f"   Фактически: {actual_time:.1f} мин")
                
                # Показываем отклонения при превышении или недостатке времени
                if section == "feedback" and participant_count > 1:
                    # Для feedback показываем отклонение на одного участника
                    actual_per_participant = actual_time / participant_count
                    expected_per_participant = expected_time / participant_count
                    
                    if actual_per_participant > expected_per_participant + 1.0:
                        if status == "❌":
                            timing_analysis.append(f"   ❌ Значительное превышение на {actual_per_participant - expected_per_participant:.1f} мин на участника")
                        elif status == "⚠️":
                            timing_analysis.append(f"   ⚠️ Небольшое превышение на {actual_per_participant - expected_per_participant:.1f} мин на участника")
                    elif actual_per_participant < expected_per_participant - 0.5:
                        timing_analysis.append(f"   ⚠️ Недостаток времени на {expected_per_participant - actual_per_participant:.1f} мин на участника")
                else:
                    # Для остальных разделов используем общее время
                    if actual_time > expected_time + 1.0:
                        if status == "❌":
                            timing_analysis.append(f"   ❌ Значительное превышение на {actual_time - expected_time:.1f} мин")
                        elif status == "⚠️":
                            timing_analysis.append(f"   ⚠️ Небольшое превышение на {actual_time - expected_time:.1f} мин")
                    elif actual_time < expected_time - 1.0:
                        timing_analysis.append(f"   ⚠️ Недостаток времени на {expected_time - actual_time:.1f} мин")
                timing_analysis.append("")
            else:
                # Проверяем, есть ли разделы, определенные резервным алгоритмом
                if section in section_timings:
                    actual_time = section_timings[section]['duration_minutes']
                    timing_analysis.append(f"⚠️ **{section_names[section]}:** (приблизительно)")
                    timing_analysis.append(f"   Ожидалось: {expected_time:.0f} мин")
                    timing_analysis.append(f"   Фактически: {actual_time:.1f} мин (оценка)")
                    if actual_time > expected_time + 1.0:
                        timing_analysis.append(f"   ⚠️ Превышение на {actual_time - expected_time:.1f} мин")
                    elif actual_time < expected_time - 1.0:
                        timing_analysis.append(f"   ⚠️ Недостаток времени на {expected_time - actual_time:.1f} мин")
                    timing_analysis.append("")
                else:
                    timing_analysis.append(f"❌ **{section_names[section]}:** Раздел не обнаружен")
                    timing_analysis.append("")
        
        # Общий тайминг
        timing_analysis.append("📊 **ОБЩИЙ ТАЙМИНГ:**")
        timing_analysis.append(f"   Фактически: {total_actual:.1f} мин")
        
        # Сравнение с эталонным временем
        standard_total = self._get_standard_total_time(scenario_type, case_count, participant_count)
        timing_analysis.append(f"   Эталонное: {standard_total:.0f} мин")
        
        # Сравнение с пользовательским временем, если указано
        if user_total_time:
            timing_analysis.append(f"   Введенное: {user_total_time:.0f} мин")
            
            # Сравниваем с введенным пользователем временем
            deviation = total_actual - user_total_time
            if abs(deviation) <= 5.0:
                timing_analysis.append("   ✅ Соответствие введенному времени")
            elif deviation > 5.0:
                timing_analysis.append(f"   ❌ Превышение введенного времени на {deviation:.1f} мин")
            else:
                timing_analysis.append(f"   ⚠️ Недостаток введенного времени на {abs(deviation):.1f} мин")
            
            # Также показываем сравнение с эталонным временем
            timing_analysis.append(f"   Эталонное: {standard_total:.0f} мин")
            standard_deviation = total_actual - standard_total
            if abs(standard_deviation) <= 5.0:
                timing_analysis.append("   ✅ Соответствие эталонному времени")
            elif standard_deviation > 5.0:
                timing_analysis.append(f"   ❌ Превышение эталонного времени на {standard_deviation:.1f} мин")
            else:
                timing_analysis.append(f"   ⚠️ Недостаток эталонного времени на {abs(standard_deviation):.1f} мин")
        else:
            # Сравниваем с эталонным временем
            if abs(total_actual - standard_total) <= 5.0:
                timing_analysis.append("   ✅ Соответствие эталонному времени")
            elif total_actual > standard_total + 5.0:
                timing_analysis.append(f"   ❌ Превышение эталонного времени на {total_actual - standard_total:.1f} мин")
            else:
                timing_analysis.append(f"   ⚠️ Недостаток эталонного времени на {standard_total - total_actual:.1f} мин")
        
        if total_actual < 5.0:
            timing_analysis.append("   ⚠️ Короткий отрывок - полный анализ невозможен")
        else:
            timing_analysis.append("   ❌ Значительное превышение общего тайминга")
        
        # Добавляем пояснение о необнаруженных разделах
        missing_sections = [section for section in expected_timings.keys() if section not in section_timings]
        if missing_sections:
            timing_analysis.append("")
            timing_analysis.append("💡 **ПОЯСНЕНИЕ:**")
            timing_analysis.append("   Разделы отмеченные как 'не обнаружены' означают, что")
            timing_analysis.append("   алгоритм не смог найти соответствующие ключевые слова")
            timing_analysis.append("   в тексте встречи. Это может быть связано с:")
            timing_analysis.append("   • Использованием нестандартных формулировок")
            timing_analysis.append("   • Отсутствием четких переходов между разделами")
            timing_analysis.append("   • Неполным текстом встречи")
            timing_analysis.append("   • Особенностями ведения встречи модератором")
        
        return "\n".join(timing_analysis)

    def read_docx_file(self, file_path: str) -> str:
        """Чтение текста из DOCX файла"""
        try:
            doc = Document(file_path)
            text = '\n'.join([paragraph.text for paragraph in doc.paragraphs if paragraph.text.strip()])
            return text
        except Exception as e:
            error_msg = f"Ошибка чтения файла: {str(e)}"
            raise Exception(self._escape_telegram_chars(error_msg))

    async def analyze_scenario_with_gigachat(self, text: str, scenario_type: str, user_total_time: float = None) -> str:
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
            return self._format_final_result(analysis_result, scenario_name, text, scenario_type, user_total_time)

        except asyncio.TimeoutError:
            return "⏰ Таймаут при запросе к GigaChat. Попробуйте позже."
        except Exception as e:
            error_msg = f"❌ Неожиданная ошибка: {str(e)}"
            return self._escape_telegram_chars(error_msg)

    def _build_full_prompt(self, meeting_text: str, prompt_template: str, scenario_name: str) -> str:
        """Создание полного промпта для анализа"""
        # Ограничиваем длину текста встречи
        if len(meeting_text) > 8000:
            meeting_text = meeting_text[:8000] + "\n\n[Текст обрезан для анализа]"

        return f"""
{prompt_template}

ТЕКСТ ВСТРЕЧИ ДЛЯ АНАЛИЗА:
{meeting_text}
"""

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

    def _integrate_timing_into_analysis(self, result: str, section_timings: Dict[str, Dict], expected_timings: Dict[str, float], case_count: int, participant_count: int = 1) -> str:
        """Интегрирует информацию о тайминге в текст анализа"""
        
        # Добавляем информацию о количестве кейсов в начало
        if case_count > 1:
            result = f"📋 **Обнаружено кейсов:** {case_count}\n\n" + result
        
        # Словарь соответствия разделов и их названий в анализе
        section_mapping = {
            "contact_format": "Контакт и краткий рассказ о формате",
            "org_moments": "Организационные моменты", 
            "introduction": "Знакомство и разогрев",
            "case_work": "Проработка запросов",
            "experience_exchange": "Обмен опытом",
            "feedback": "Итоги мастермайнда"
        }
        
        # Обрабатываем каждый раздел
        for section_key, section_name in section_mapping.items():
            if section_key in section_timings and section_key in expected_timings:
                actual_time = section_timings[section_key]['duration_minutes']
                expected_time = expected_timings[section_key]
                
                # Определяем статус - крестики только при превышении времени
                if actual_time < expected_time - 1.0:  # Значительный недостаток времени
                    status_icon = "⚠️"
                elif actual_time <= expected_time + 1.0:  # В пределах нормы
                    status_icon = "✅"
                elif actual_time <= expected_time + 2.0:  # Небольшое превышение
                    status_icon = "⚠️"
                else:  # Значительное превышение
                    status_icon = "❌"
                
                # Ищем строки с временными рамками в скобках
                import re
                
                # Паттерн для поиска заголовков с временем в скобках
                patterns = [
                    rf"({re.escape(section_name)}.*?)(\(\d+.*?мин.*?\))",
                    rf"({re.escape(section_name)}.*?)(\(\d+.*?мин\))",
                    rf"({re.escape(section_name)}.*?)(\(\d+ мин\))",
                    rf"({re.escape(section_name)}.*?)(\(\d+ мин на каждого\))",
                    rf"({re.escape(section_name)}.*?)(\(\d+-\d+ мин на каждого\))"
                ]
                
                for pattern in patterns:
                    match = re.search(pattern, result, re.IGNORECASE | re.DOTALL)
                    if match:
                        before = match.group(1)
                        time_bracket = match.group(2)
                        
                        # Формируем новую информацию о времени
                        if actual_time > expected_time + 1.0:
                            time_info = f"{time_bracket.strip('()')} - фактически {actual_time:.1f} мин {status_icon}"
                        else:
                            time_info = f"{time_bracket.strip('()')} - {actual_time:.1f} мин {status_icon}"
                        
                        # Заменяем в тексте
                        new_section = before + "(" + time_info + ")"
                        result = result.replace(match.group(0), new_section)
                        break  # Прерываем, если нашли совпадение
        
        return result

    def _format_final_result(self, result: str, scenario_name: str, text: str = "", scenario_type: str = "", user_total_time: float = None) -> str:
        """Форматирование конечного результата для Telegram"""
        scenario_name_escaped = self._escape_telegram_chars(scenario_name)
        
        # Анализ тайминга, если предоставлен текст встречи
        section_timings = None
        expected_timings = None
        case_count = 1
        
        if text and scenario_type:
            try:
                timestamps = self._parse_meeting_timestamps(text)
                if timestamps:
                    sections = self._identify_meeting_sections(text, scenario_type)
                    section_timings = self._calculate_section_timing(text, timestamps, sections)
                    case_count = self._count_cases_in_text(text)
                    participant_count = self._count_participants_in_text(text)
                    expected_timings = self._get_expected_timings(scenario_type, case_count, participant_count)
                    
                    # Интегрируем тайминг в анализ
                    result = self._integrate_timing_into_analysis(result, section_timings, expected_timings, case_count, participant_count)
                    
                    # Добавляем полный анализ тайминга
                    timing_analysis = self._analyze_timing_compliance(section_timings, expected_timings, scenario_type, case_count, participant_count, user_total_time, timestamps)
                    result += f"\n\n{timing_analysis}"
                    
            except Exception as e:
                # В случае ошибки добавляем предупреждение
                result = f"⚠️ Ошибка анализа тайминга: {str(e)}\n\n{result}"
        
        # Общий тайминг уже добавлен в _analyze_timing_compliance, дублирование не нужно
        
        # Очищаем результат от проблемных символов разметки
        result = self._clean_telegram_markup(result)
        
        # Формируем итоговый результат
        final_result = f"""
🎯 *РЕЗУЛЬТАТ АНАЛИЗА: {scenario_name_escaped}*

{result}
"""
        
        final_result += "\n📋 *Анализ завершен*"
        
        return final_result
    


async def check_meeting_scenario(file_path: str, scenario_type: str, user_total_time: float = None) -> str:
    """Основная функция проверки сценария"""
    try:
        checker = ScenarioChecker()
        text = checker.read_docx_file(file_path)

        if not text.strip():
            return "❌ Файл пуст или содержит нечитаемый текст"

        analysis_result = await checker.analyze_scenario_with_gigachat(text, scenario_type, user_total_time)
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