# success_criteria.py
import os
import logging
from docx import Document

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Импортируем RAG систему для улучшения промптов
try:
    from rag_system import get_rag_system
    RAG_AVAILABLE = True
    logger.info("RAG система доступна для улучшения промптов анализа компетенций")
except ImportError:
    RAG_AVAILABLE = False
    logger.warning("RAG система недоступна. Промпты будут использоваться без улучшения.")


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


def get_success_criteria_prompt(meeting_text, use_rag=True):
    """
    Возвращает промпт для анализа критериев успеха
    
    Что делает:
    1. Создает базовый промпт с текстом встречи
    2. Если RAG доступна - улучшает промпт контекстом из базы знаний
    3. Возвращает финальный промпт для GigaChat
    
    Args:
        meeting_text: текст транскрипции встречи
        use_rag: использовать ли RAG для улучшения промпта (по умолчанию True)
    
    Returns:
        финальный промпт для анализа компетенций
    """
    # Базовый промпт
    base_prompt = f"""
Проанализируй текст встречи и оцени ее по следующим критериям:

🎯 **ПРОЯВЛЕНИЯ КОМПЕТЕНЦИЙ МОДЕРАТОР**:**

Ты — эксперт по коммуникациям и коуч. Проанализируй предоставленную транскрибацию на 3 показателя:
1. Стиль модератора: Модератор проявляет навыки активного слушания (перефразирует, резюмирует, задает уточняющие вопросы, не использует слова-паразиты). Экспертная позиция проявляется уместно, primarily на этапе обмена опытом.
2. Динамика группы: Модератор поддерживает позитивное эмоциональное настроение и обеспечивает вовлеченность каждого участника на протяжении всей сессии.
3. Эмоциональное настроение группы: оцени общее эмоциональное настроение команды: преобладающая эмоция, наличие конфликта/напряжения: Отметь, есть ли признаки разногласий или фрустрации.

Определи преобладающий стиль коммуникации руководителя в тексте. Объясни свой вывод.
Выдели директивные проявления, если они есть (приказы, указания, закрытые вопросы),но [ВАЖНО] не учитывай озвучивание правил проведения встречи и тайминга. Выпиши по 3-5 конкретных примеров фраз из текста.
Для каждой такой фразы предложи альтернативу в поддерживающем или коучинговом стиле, заменив повелительные глаголы на вопросительные или побудительные конструкции.

💡 **ФОРМАТ ОТВЕТА:**
Распиши 3 показателя поочередно, в каждом пункте должен быть детальный разбор по критериям, сильные стороны и рекомендации, чтобы коммуникация модератора стала более коучинговой.
Сгенерируй краткий, практический список из 1-3 ключевых дальнейших шагов развития для ведущего мастермайнда. 
Так же добавь в шаги развития ссылки на прохождение соответствующих курсов: "Развитие талантов: Коучинг как инструмент руководителя - https://hr.sberbank.ru/platform/catalog/fc4756d5-12d8-44bd-be4d-567319cba1bf", 
"Обучение взрослых: секреты успеха - https://hr.sberbank.ru/platform/catalog/2b93ff77-6d6f-4157-8b34-468dc91c081e"
ТЕКСТ ВСТРЕЧИ ДЛЯ АНАЛИЗА:

{meeting_text}
"""
    
    # Улучшаем промпт через RAG (если доступна и включена)
    if use_rag and RAG_AVAILABLE:
        try:
            rag_system = get_rag_system()
            
            # Для анализа компетенций используем универсальный тип сценария
            # или не указываем тип, чтобы получить примеры из всех типов
            enhanced_prompt = rag_system.enhance_prompt(
                base_prompt=base_prompt,
                query_text=meeting_text[:2000],  # Используем первые 2000 символов для поиска
                scenario_type='scenario_universal'  # Универсальный тип для анализа компетенций
            )
            
            logger.info("✅ Промпт анализа компетенций улучшен контекстом из RAG базы знаний")
            return enhanced_prompt
            
        except Exception as e:
            logger.warning(f"Ошибка улучшения промпта через RAG: {e}")
            # Если ошибка - возвращаем базовый промпт
            return base_prompt
    
    # Если RAG недоступна или отключена - возвращаем базовый промпт
    return base_prompt


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

        # Формируем промпт с улучшением через RAG
        prompt = get_success_criteria_prompt(meeting_text, use_rag=True)

        # Импортируем анализатор здесь, чтобы избежать циклических импортов
        from giga_recomendation import MeetingAnalyzer

        # Конфигурация GigaChat (должна совпадать с основной)
        AUTH_KEY = 'ZGMzMGJmZjEtODQwYS00ZjAwLWI2NjgtNGIyNGNiY2ViNmE1OjY1MzcyY2I3LWEwMjUtNDkyYi04ZjJhLTEyNmRkMjM2NDNhYg=='
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
