# success_criteria.py
import os
import logging
from docx import Document

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def read_docx_file(file_path):
    """Чтение текста из файла .docx"""
    try:
        doc = Document(file_path)
        full_text = []
        for paragraph in doc.paragraphs:
            if paragraph.text.strip():
                full_text.append(paragraph.text)
        return '\n'.join(full_text)
    except Exception as e:
        logger.error(f"Ошибка чтения файла {file_path}: {str(e)}")
        return f"Ошибка чтения файла: {str(e)}"


def find_meeting_file(user_id):
    """
    Ищет файл встречи в папке пользователя
    Возвращает путь к файлу или None если не найден
    """
    user_folder = f"temp_files/{user_id}"

    if not os.path.exists(user_folder):
        return None

    # Ищем файлы встречи (trans.docx или другие docx файлы)
    for file_name in os.listdir(user_folder):
        if file_name.endswith('.docx'):
            file_path = os.path.join(user_folder, file_name)
            # Проверяем, что файл не пустой
            if os.path.getsize(file_path) > 0:
                return file_path

    return None


def get_success_criteria_prompt(meeting_text):
    """Возвращает промпт для анализа критериев успеха"""
    # Ограничиваем длину текста встречи
    if len(meeting_text) > 12000:
        meeting_text = meeting_text[:12000] + "\n\n[Текст обрезан для анализа]"

    prompt = f"""
Проанализируй текст встречи и оцени ее по следующим критериям успеха:

🎯 **КРИТЕРИИ УСПЕХА ВСТРЕЧИ:**

Ты — эксперт по коммуникациям и коуч. Проанализируй предоставленную транскрибацию на 4 показателя:
1. Структура: Модератор четко следует сценарию, делает плавные переходы между этапами и гибко управляет таймингом.
2. Стиль: Модератор проявляет навыки активного слушания (перефразирует, резюмирует, задает уточняющие вопросы). Экспертная позиция проявляется уместно, primarily на этапе обмена опытом.
3. Динамика группы: Модератор поддерживает позитивное эмоциональное настроение и обеспечивает вовлеченность каждого участника на протяжении всей сессии.
4. Эмоция: оцени общее эмоциональное настроение команды: преобладающая эмоция, наличие конфликта/напряжения: Отметь, есть ли признаки разногласий или фрустрации.

Определи преобладающий стиль коммуникации руководителя в тексте. Объясни свой вывод.
Выдели директивные проявления, если они есть (приказы, указания, закрытые вопросы). Выпиши по 3-5 конкретных примеров фраз из текста.
Для каждой такой фразы предложи альтернативу в поддерживающем или коучинговом стиле, заменив повелительные глаголы на вопросительные или побудительные конструкции.
Сформулируй итоговые рекомендации: 3 ключевых шага, которые руководитель может сделать, чтобы его коммуникация стала более фасилитационной.

💡 **ФОРМАТ ОТВЕТА:**
Начни с общей оценки эффективности встречи в процентах, затем детальный разбор по критериям, сильные стороны и рекомендации.

ТЕКСТ ВСТРЕЧИ ДЛЯ АНАЛИЗА:

{meeting_text}
"""
    return prompt


async def check_success_criteria(file_path=None, user_id=None):
    """
    Основная функция для проверки критериев успеха
    Возвращает результат анализа в виде текста
    """
    try:
        # Если передан user_id, ищем файл в его папке
        if user_id and not file_path:
            file_path = find_meeting_file(user_id)
            if not file_path:
                return "❌ Файл встречи не найден. Пожалуйста, сначала загрузите файл с текстом встречи через меню 'Анализ компетенций'."

        if not file_path or not os.path.exists(file_path):
            return "❌ Файл встречи не найден или путь неверный."

        # Читаем текст встречи (без фильтрации речи ведущего)
        meeting_text = read_docx_file(file_path)

        if not meeting_text.strip():
            return "❌ Не удалось прочитать текст встречи или файл пуст."

        # Формируем промпт
        prompt = get_success_criteria_prompt(meeting_text)

        # Импортируем анализатор здесь, чтобы избежать циклических импортов
        from giga_recomendation import MeetingAnalyzer

        # Конфигурация GigaChat (должна совпадать с основной)
        AUTH_KEY = 'ZGMzMGJmZjEtODQwYS00ZjAwLWI2NjgtNGIyNGNiY2ViNmE1OjYwNjM3NTU0LWQxMDctNDA5ZS1hZWM3LTAwYjQ5MjZkOGU2OA=='
        SCOPE = 'GIGACHAT_API_PERS'
        API_AUTH_URL = 'https://ngw.devices.sberbank.ru:9443/api/v2/oauth'
        API_CHAT_URL = 'https://gigachat.devices.sberbank.ru/api/v1/chat/completions'

        # Создаем анализатор
        analyzer = MeetingAnalyzer(AUTH_KEY, SCOPE, API_AUTH_URL, API_CHAT_URL)

        # Анализируем
        analysis_result = analyzer.analyze_with_prompt(prompt)

        if analysis_result.startswith("❌"):
            return f"❌ Ошибка при анализе критериев успеха: {analysis_result}"

        return analysis_result

    except Exception as e:
        error_msg = f"❌ Ошибка при анализе критериев успеха: {str(e)}"
        logger.error(error_msg)
        return error_msg