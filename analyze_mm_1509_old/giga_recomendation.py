import requests
import json
from datetime import datetime
import os
from docx import Document
import pandas as pd
from gigachat import GigaChat, models


class MeetingAnalyzer:
    def __init__(self, auth_key, scope, api_auth_url, api_chat_url):
        self.auth_key = auth_key
        self.scope = scope
        self.api_auth_url = api_auth_url
        self.api_chat_url = api_chat_url
        # self.model = models.GigaChat
        self.access_token = None
        self.token_expires = 0

    def get_access_token(self):
        headers = {
            'Authorization': f'Bearer {self.auth_key}',
            'RqUID': '6f0b1291-c7f3-43c6-bb2e-9f3efb2dc98e',
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        data = {'scope': self.scope}

        response = requests.post(self.api_auth_url, headers=headers, data=data, verify=False)
        if response.status_code == 200:
            token_data = response.json()
            self.access_token = token_data['access_token']
            self.token_expires = datetime.now().timestamp() + int(token_data['expires_at'])
            return True
        else:
            print(f"Ошибка получения токена: {response.status_code} - {response.text}")
            return False

    def is_token_valid(self):
        return self.access_token and datetime.now().timestamp() < self.token_expires

    def read_docx(self, file_path):
        """Чтение текста из файла .docx"""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Файл {file_path} не найден")

        doc = Document(file_path)
        full_text = []
        for para in doc.paragraphs:
            full_text.append(para.text)
        return '\n'.join(full_text)

    def _load_triggers_courses(self, triggers_file_path):
        """Загружает курсы из файла триггеров"""
        try:
            df = pd.read_excel(triggers_file_path)
            df = df.fillna('')

            courses_dict = {}
            for _, row in df.iterrows():
                comp = row.get('компетенция', '')
                indicator = row.get('Поведенческие проявления (индикаторы)', '')
                courses = row.get('курсы', '')

                if comp and courses:
                    key = f"{comp} - {indicator}" if indicator else comp
                    course_list = [c.strip() for c in str(courses).split(',') if c.strip()]
                    if course_list:
                        courses_dict[key] = course_list

            return courses_dict
        except Exception as e:
            print(f"Ошибка загрузки курсов из триггеров: {e}")
            return {}

    def _extract_competencies_from_report(self, report_text):
        """Извлекает компетенции с низкими баллами из отчета"""
        low_score_competencies = []
        lines = report_text.split('\n')

        for line in lines:
            if ('🔴' in line or '🟡' in line or '🟢' in line) and '**' in line:
                comp_name = line.split('**')[1].split('**')[0]
                low_score_competencies.append(comp_name)
            elif '🏆' in line and ' - средний балл' in line:
                comp_name = line.split('🏆')[1].split(' - средний балл')[0].strip()
                low_score_competencies.append(comp_name)

        return low_score_competencies

    def analyze_meeting(self):
        if not self.is_token_valid() and not self.get_access_token():
            return "Ошибка: не удалось получить токен доступа"

        try:
            trans = self.read_docx('./trans.docx')
        except Exception as e:
            return f"Ошибка чтения файла: {str(e)}"

        prompt = f"""Проанализируй текст встречи и сформируй рекомендации:

Итоги ММ

Твой голос и речь были [позитивны/нейтральны/негативны], [доброжелательны/формальны/холодны]. 
Ты вовлёк в обсуждение [N] из [M] присутствующих ММК. 
Ты [пропустил/не пропустил] важный этап.
[Соблюдён тайминг/Не соблюдён].
[Один/Несколько/Никто] из [M] участников ММК погрузился в бизнес клиента.
При этом [не погрузился/погрузился] в клиента.
Уточняющие вопросы о клиенте задавали [N] из [M] ММК. 
Ты [не предложил/предложил] команде поиск решения.
При этом тобой [использовались слова паразиты/не использовал слова паразиты]. 
Ты [перебивал/не перебивал] речь.
В итоге [ребята не сформулировали свою идею/сформулировали свои идеи]. 
[Были/Не было] признаков активного слушания. 
По итогам ММ [N] из [M] ребят не сформулировали ценность встречи.

Рекомендации РМ

Тебе необходимо:

1. [Рекомендация 1]
2. [Рекомендация 2]
3. [Рекомендация 3]
4. [Рекомендация 4]

Текст встречи для анализа:
{trans}"""

        return self._send_request(prompt)

    def _compress_text(self, text, max_length=500):
        """Сжимает текст, убирая лишние пробелы, но НЕ обрезает содержимое"""
        compressed = ' '.join(text.split())
        # УБРАНО ОБРЕЗАНИЕ ТЕКСТА
        return compressed

    def _send_request(self, prompt):
        # ДОБАВЛЕНА ОТЛАДОЧНАЯ ПЕЧАТЬ
        print(f"\n" + "=" * 80)
        print("DEBUG MeetingAnalyzer: ОТПРАВКА ЗАПРОСА В GIGACHAT")
        print("=" * 80)
        print(f"URL API: {self.api_chat_url}")
        print(f"Модель: GigaChat-2-Pro")
        print(f"Общая длина промпта: {len(prompt)} символов")
        print(f"Токен доступа: {'ЕСТЬ' if self.access_token else 'ОТСУТСТВУЕТ'}")

        # Анализируем структуру промпта
        lines = prompt.split('\n')
        print(f"Количество строк в промпте: {len(lines)}")

        # Находим где начинается текст встречи
        meeting_text_start = None
        for i, line in enumerate(lines):
            if "ТЕКСТ ВСТРЕЧИ ДЛЯ АНАЛИЗА:" in line or "Текст встречи:" in line:
                meeting_text_start = i
                break

        if meeting_text_start is not None:
            meeting_text = '\n'.join(lines[meeting_text_start:])
            print(f"Длина текста встречи: {len(meeting_text)} символов")
            print(f"Первые 500 символов текста встречи:")
            print("-" * 40)
            print(meeting_text[:500] + "..." if len(meeting_text) > 500 else meeting_text)
            print("-" * 40)

        print(f"Последние 300 символов промпта:")
        print("-" * 40)
        print("..." + prompt[-300:] if len(prompt) > 300 else prompt)
        print("-" * 40)
        print("=" * 80 + "\n")

        headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json'
        }

        payload = {
            "model": "GigaChat-2-Pro",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7,
            "top_p": 0.9,
            "n": 1,
            "stream": False,
            "max_tokens": 200000,
            "repetition_penalty": 1.0
        }

        print(f"DEBUG: Отправка запроса к GigaChat API...")

        try:
            response = requests.post(self.api_chat_url, headers=headers, json=payload, verify=False)

            print(f"DEBUG: Получен ответ от API. Статус: {response.status_code}")

            if response.status_code == 200:
                result = response.json()
                response_text = result['choices'][0]['message']['content']
                print(f"DEBUG: Успешный ответ от GigaChat")
                print(f"DEBUG: Длина ответа: {len(response_text)} символов")
                print(f"DEBUG: Первые 300 символов ответа:")
                print("-" * 40)
                print(response_text[:300] + "..." if len(response_text) > 300 else response_text)
                print("-" * 40)
                return response_text
            else:
                error_msg = f"Ошибка анализа встречи: {response.status_code} - {response.text}"
                print(f"DEBUG: Ошибка от GigaChat: {error_msg}")
                return error_msg

        except Exception as e:
            error_msg = f"Исключение при запросе к GigaChat: {str(e)}"
            print(f"DEBUG: Исключение: {error_msg}")
            return error_msg

    def _extract_competencies_with_scores(self, report_text):
        competencies_with_scores = {}
        lines = report_text.split('\n')

        for i, line in enumerate(lines):
            if '🏆' in line and ' - средний балл' in line:
                comp_name = line.split('🏆')[1].split(' - средний балл')[0].strip()
                score_match = line.split('средний балл')[1].split()[0]
                try:
                    score = float(score_match)
                    competencies_with_scores[comp_name] = score
                except:
                    pass

        return competencies_with_scores

    def analyze_meeting_with_file(self, file_path=None, user_id=None):
        if file_path is None:
            if user_id is None:
                return "❌ Ошибка: Не указан путь к файлу и user_id."
            file_path = f"temp_files/{user_id}/trans.docx"

        if not self.is_token_valid() and not self.get_access_token():
            return "Ошибка: не удалось получить токен доступа"

        try:
            trans = self.read_docx(file_path)
            print(f"DEBUG: Прочитан текст встречи из {file_path}, длина: {len(trans)} символов")
        except Exception as e:
            return f"Ошибка чтения файла: {str(e)}"

        competency_report = ""
        try:
            if os.path.exists('REPORT.txt'):
                with open('REPORT.txt', 'r', encoding='utf-8') as f:
                    full_report = f.read()
                    # УБРАНО ОБРЕЗАНИЕ ОТЧЕТА - используем полный текст
                    competency_report = full_report
                print(f"DEBUG: Прочитан отчет компетенций, длина: {len(competency_report)} символов")
            else:
                return "❌ Ошибка: Файл REPORT.txt не найден."
        except Exception as e:
            return f"❌ Ошибка чтения отчета компетенций: {str(e)}"

        triggers_file_path = 'triggers.xlsx'
        if not os.path.exists(triggers_file_path):
            return "❌ Ошибка: Файл triggers.xlsx не найден."

        courses_dict = self._load_triggers_courses(triggers_file_path)
        problem_competencies = self._extract_competencies_from_report(competency_report)
        competencies_with_scores = self._extract_competencies_with_scores(competency_report)

        # УБРАНО СЖАТИЕ ТЕКСТА - используем полный отчет
        # competency_report = self._compress_text(competency_report, 600)

        courses_text = ""
        if courses_dict and problem_competencies:
            courses_text = "\n\n📚 ДОСТУПНЫЕ КУРСЫ ДЛЯ РЕКОМЕНДАЦИЙ:\n"
            for comp in problem_competencies:
                for key, courses in courses_dict.items():
                    if comp.lower() in key.lower():
                        courses_text += f"- {comp}:\n"
                        for course in courses:
                            courses_text += f"  • {course}\n"
                        break

        scores_text = ""
        if competencies_with_scores:
            scores_text = "\n\n📊 ТОЧНЫЕ БАЛЛЫ ИЗ ОТЧЁТА:\n"
            for comp, score in competencies_with_scores.items():
                scores_text += f"- {comp}: {score}/10\n"

        prompt = f"""Проанализируй текст встречи и отчет по компетенциям, затем сформируй детальные рекомендации:

# ДЕТАЛЬНЫЕ РЕКОМЕНДАЦИИ ПО РАЗВИТИЮ

## Анализ встречи и компетенций

[Проанализируй стиль общения, структуру встречи, вовлеченность участников]

## РЕКОМЕНДАЦИИ ПО КОМПЕТЕНЦИЯМ

### Приоритетные компетенции для развития:

{courses_text}

{scores_text}

КРИТИЧЕСКИ ВАЖНО: Используй ТОЛЬКО курсы из списка выше для рекомендаций. НЕ придумывай новые курсы.

ВАЖНО: Используй ТОЧНЫЕ БАЛЛЫ из списка выше. НЕ придумывай баллы.

ДЛЯ КАЖДОЙ КОМПЕТЕНЦИИ ДОБАВЬ РАЗДЕЛ "💬 КОНСТРУКТИВНЫЕ АЛЬТЕРНАТИВЫ":
- Проанализируй негативные фразы из отчёта
- Предложи конструктивные альтернативы
- Формат: "Вместо: [негативная фраза] → Мог бы сказать: [конструктивная альтернатива]"

СОЗДАЙ РЕКОМЕНДАЦИИ ДЛЯ ВСЕХ КОМПЕТЕНЦИЙ ИЗ СПИСКА ВЫШЕ:

ВАЖНО: Создай отдельный блок рекомендаций для КАЖДОЙ компетенции из списка баллов выше.

[Для каждой компетенции из списка создай блок в формате:]

**[Название компетенции]** - [ТОЧНЫЙ БАЛЛ из списка выше]
- 📊 **Текущий уровень:** [Описание текущего состояния]
- 📚 **Курсы для изучения:**
  - [Используй ТОЛЬКО курсы из списка выше, если они есть]
- 💡 **Практические рекомендации:**
  - [Конкретная рекомендация 1]
  - [Конкретная рекомендация 2]
- 💬 **Конструктивные альтернативы:**
  - Вместо: [негативная фраза] → Мог бы сказать: [конструктивная альтернатива]
  - Вместо: [негативная фраза] → Мог бы сказать: [конструктивная альтернатива]
- 🎯 **Ожидаемый результат:** [Что изменится после развития]

## ОБЩИЕ РЕКОМЕНДАЦИИ ПО ВСТРЕЧЕ

### Что улучшить в проведении встреч:

1. [Рекомендация по структуре встречи]
2. [Рекомендация по коммуникации]
3. [Рекомендация по вовлечению участников]

## ПЛАН РАЗВИТИЯ НА БЛИЖАЙШИЙ МЕСЯЦ

### Неделя 1: [Фокус на конкретную компетенцию]
- [Конкретные действия]
- [Практические задания]

### Неделя 2: [Фокус на конкретную компетенцию]
- [Конкретные действия]
- [Практические задания]

---

Текст встречи:
{trans}

Отчет по компетенциям:
{competency_report}
"""

        return self._send_request(prompt)

    def analyze_with_prompt(self, prompt_text):
        """Анализирует текст с использованием кастомного промпта"""
        if not self.is_token_valid() and not self.get_access_token():
            return "❌ Ошибка: не удалось получить токен доступа"
        return self._send_request(prompt_text)


# Пример использования
if __name__ == "__main__":
    AUTH_KEY = 'ZGMzMGJmZjEtODQwYS00ZjAwLWI2NjgtNGIyNGNiY2ViNmE1OjY1MzcyY2I3LWEwMjUtNDkyYi04ZjJhLTEyNmRkMjM2NDNhYg=='
    SCOPE = 'GIGACHAT_API_PERS'
    API_AUTH_URL = 'https://ngw.devices.sberbank.ru:9443/api/v2/oauth'
    API_CHAT_URL = 'https://gigachat.devices.sberbank.ru/api/v1/chat/completions'

    analyzer = MeetingAnalyzer(AUTH_KEY, SCOPE, API_AUTH_URL, API_CHAT_URL)

    try:
        analysis_result = analyzer.analyze_meeting()
        print("Результат анализа встречи:")
        print(analysis_result)

        with open('meeting_analysis.txt', 'w', encoding='utf-8') as f:
            f.write(analysis_result)
        print("\nРезультат сохранён в файл meeting_analysis.txt")

    except Exception as e:
        print(f"Произошла ошибка: {str(e)}")