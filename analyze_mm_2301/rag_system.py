"""
RAG (Retrieval-Augmented Generation) система для анализа мастермайндов

Что это делает:
1. Хранит примеры успешных сценариев и результаты хороших анализов
2. Ищет похожие примеры сценариев и результатов для новой транскрипции
3. Добавляет найденные примеры в промпт для GigaChat

Почему это нужно:
- GigaChat будет анализировать с учетом реальных примеров сценариев и результатов из вашей практики
- Проверка станет более точной и соответствующей вашей предметной области
"""

import os
import logging
from typing import List, Dict, Optional
from docx import Document  # Для чтения .docx файлов
from difflib import SequenceMatcher  # Для простого сравнения текстов

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Импорт для чтения PDF (опционально, если библиотека установлена)
try:
    import PyPDF2
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False
    logger.warning("PyPDF2 не установлен. PDF файлы не будут обрабатываться. Установите: pip install PyPDF2")


class RAGSystem:
    """
    Простая RAG система для хранения и поиска знаний о мастермайндах
    
    Пока что это базовая версия - хранит данные в памяти.
    Позже добавим векторный поиск для более умного поиска.
    """
    
    def __init__(self, knowledge_base_path: str = "транскрибации, промпты"):
        """
        Инициализация RAG системы
        
        Args:
            knowledge_base_path: путь к папке с транскрипциями и промптами
        """
        self.knowledge_base_path = knowledge_base_path
        
        # Хранилище знаний (пока в памяти, позже добавим векторную БД)
        self.examples = []  # Список примеров успешных сценариев
        self.instructions = {}  # Инструкции по этапам
        
        # Структурированное хранилище загруженных данных
        self.loaded_scenarios = []  # Загруженные сценарии (промпты для модераторов)
        self.loaded_results = []  # Загруженные результаты анализов (примеры хороших проверок)
        self.base_knowledge = ""  # Базовая информация из PDF (общая информация про мастермайнды)
        
        logger.info(f"RAG система инициализирована. База знаний: {knowledge_base_path}")
    
    def _read_docx_file(self, file_path: str) -> str:
        """
        Читает текст из .docx файла
        
        Что делает:
        1. Открывает файл .docx
        2. Читает все параграфы
        3. Объединяет их в один текст
        
        Args:
            file_path: путь к файлу .docx
        
        Returns:
            текст из файла
        """
        try:
            doc = Document(file_path)
            # Читаем все параграфы и объединяем их
            text_parts = []
            for paragraph in doc.paragraphs:
                if paragraph.text.strip():  # Пропускаем пустые строки
                    text_parts.append(paragraph.text.strip())
            
            full_text = '\n'.join(text_parts)
            return full_text
        except Exception as e:
            logger.error(f"Ошибка чтения файла {file_path}: {e}")
            return ""
    
    def _read_txt_file(self, file_path: str) -> str:
        """
        Читает текст из .txt файла
        
        Args:
            file_path: путь к файлу .txt
        
        Returns:
            текст из файла
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            logger.error(f"Ошибка чтения файла {file_path}: {e}")
            return ""
    
    def _read_pdf_file(self, file_path: str) -> str:
        """
        Читает текст из .pdf файла
        
        Что делает:
        1. Открывает PDF файл
        2. Читает текст со всех страниц
        3. Объединяет их в один текст
        
        Args:
            file_path: путь к файлу .pdf
        
        Returns:
            текст из файла
        """
        if not PDF_AVAILABLE:
            logger.warning(f"PyPDF2 не установлен. Не могу прочитать PDF файл: {file_path}")
            return ""
        
        try:
            text_parts = []
            with open(file_path, 'rb') as f:
                pdf_reader = PyPDF2.PdfReader(f)
                
                # Читаем текст со всех страниц
                for page_num, page in enumerate(pdf_reader.pages, 1):
                    try:
                        page_text = page.extract_text()
                        if page_text.strip():
                            text_parts.append(page_text.strip())
                    except Exception as e:
                        logger.warning(f"Ошибка чтения страницы {page_num} в файле {file_path}: {e}")
                        continue
            
            full_text = '\n\n'.join(text_parts)
            return full_text
        except Exception as e:
            logger.error(f"Ошибка чтения PDF файла {file_path}: {e}")
            return ""
    
    def load_knowledge_base(self):
        """
        Загружает базу знаний из папки со сценариями и результатами анализов
        
        Что делает:
        1. Находит файлы сценариев в папке "промпты" (форматы: .docx, .txt, .pdf)
        2. Находит файлы результатов анализов (с "результат" в названии, форматы: .docx, .pdf)
        3. Читает содержимое каждого файла
        4. Сохраняет текст в структурированном виде
        
        Поддерживаемые форматы:
        - Сценарии: .docx, .txt, .pdf
        - Результаты: .docx, .pdf
        
        Теперь опираемся на сценарии и результаты, а не на транскрипции!
        """
        if not os.path.exists(self.knowledge_base_path):
            logger.warning(f"Папка {self.knowledge_base_path} не найдена")
            return
        
        # Шаг 1: Находим папку "промпты" и файлы результатов
        prompts_folder = os.path.join(self.knowledge_base_path, "промпты")
        scenario_files = []
        result_files = []
        base_knowledge_files = []  # PDF файлы с базовой информацией
        
        # Загружаем сценарии из папки "промпты"
        if os.path.exists(prompts_folder):
            logger.info(f"Ищем сценарии в папке: {prompts_folder}")
            for file_name in os.listdir(prompts_folder):
                file_path = os.path.join(prompts_folder, file_name)
                
                # Пропускаем папки и временные файлы
                if os.path.isdir(file_path) or file_name.startswith('~$'):
                    continue
                
                # Пропускаем файлы результатов и Excel
                if 'результат' in file_name.lower() or file_name.endswith('.xlsx'):
                    continue
                
                # PDF файлы с общей информацией (не содержат специфических названий сценариев)
                if file_name.endswith('.pdf'):
                    file_lower = file_name.lower()
                    # Если PDF не содержит специфических названий сценариев, это базовая информация
                    if not any(keyword in file_lower for keyword in ['онлайн', 'e-com', 'еком', 'первые', 'нович', 
                                                                      'месяц', 'мои встречи', 'встреч', 'сценарий']):
                        base_knowledge_files.append(file_path)
                    else:
                        # Иначе это специфический сценарий
                        scenario_files.append(file_path)
                # Загружаем docx и txt файлы со сценариями
                elif file_name.endswith('.docx') or file_name.endswith('.txt'):
                    scenario_files.append(file_path)
        
        # Загружаем результаты анализов из основной папки и из папки "промпты"
        for folder_path in [self.knowledge_base_path, prompts_folder]:
            if not os.path.exists(folder_path):
                continue
            
            for file_name in os.listdir(folder_path):
                file_path = os.path.join(folder_path, file_name)
                
                # Пропускаем папки и временные файлы
                if os.path.isdir(file_path) or file_name.startswith('~$'):
                    continue
                
                # Ищем файлы с "результат" в названии (docx и pdf)
                if ('результат' in file_name.lower() or 'результ' in file_name.lower()) and \
                   (file_name.endswith('.docx') or file_name.endswith('.pdf')):
                    result_files.append(file_path)
        
        logger.info(f"Найдено сценариев: {len(scenario_files)}")
        logger.info(f"Найдено результатов анализов: {len(result_files)}")
        logger.info(f"Найдено PDF с базовой информацией: {len(base_knowledge_files)}")
        
        # Шаг 1.5: Читаем базовую информацию из PDF (всегда загружается первой)
        logger.info("Чтение базовой информации из PDF...")
        base_knowledge_parts = []
        
        for file_path in base_knowledge_files:
            file_name = os.path.basename(file_path)
            logger.info(f"  Читаю базовую информацию: {file_name}")
            
            text = self._read_pdf_file(file_path)
            
            if text:
                base_knowledge_parts.append(f"\n\n=== {file_name} ===\n{text}")
                logger.info(f"    ✅ Загружено: {len(text)} символов")
            else:
                logger.warning(f"    ⚠️ Не удалось прочитать файл")
        
        # Объединяем всю базовую информацию в один текст
        self.base_knowledge = "\n".join(base_knowledge_parts)
        if self.base_knowledge:
            logger.info(f"✅ Базовая информация загружена: {len(self.base_knowledge)} символов")
        
        # Шаг 2: Читаем содержимое сценариев
        logger.info("Чтение сценариев...")
        self.loaded_scenarios = []
        
        for file_path in scenario_files:
            file_name = os.path.basename(file_path)
            logger.info(f"  Читаю сценарий: {file_name}")
            
            # Читаем в зависимости от типа файла
            if file_name.endswith('.docx'):
                text = self._read_docx_file(file_path)
            elif file_name.endswith('.txt'):
                text = self._read_txt_file(file_path)
            elif file_name.endswith('.pdf'):
                text = self._read_pdf_file(file_path)
            else:
                text = ""
            
            if text:  # Если файл прочитан успешно
                # Определяем тип сценария из имени файла
                scenario_type = self._detect_scenario_type(file_name)
                
                # Сохраняем структурированную информацию
                self.loaded_scenarios.append({
                    'file_name': file_name,
                    'file_path': file_path,
                    'text': text,
                    'text_length': len(text),
                    'scenario_type': scenario_type
                })
                logger.info(f"    ✅ Загружено: {len(text)} символов, тип: {scenario_type}")
            else:
                logger.warning(f"    ⚠️ Не удалось прочитать файл")
        
        # Шаг 3: Читаем результаты анализов
        logger.info("Чтение результатов анализов...")
        self.loaded_results = []
        
        for file_path in result_files:
            file_name = os.path.basename(file_path)
            logger.info(f"  Читаю результат: {file_name}")
            
            # Читаем в зависимости от типа файла
            if file_name.endswith('.docx'):
                text = self._read_docx_file(file_path)
            elif file_name.endswith('.pdf'):
                text = self._read_pdf_file(file_path)
            else:
                text = ""
            
            if text:
                # Определяем тип сценария из имени файла результата
                scenario_type = self._detect_scenario_type(file_name)
                
                self.loaded_results.append({
                    'file_name': file_name,
                    'file_path': file_path,
                    'text': text,  # Сохраняем полный текст результатов
                    'text_length': len(text),
                    'scenario_type': scenario_type
                })
                logger.info(f"    ✅ Загружено: {len(text)} символов, тип: {scenario_type}")
        
        # Сохраняем список файлов для обратной совместимости
        self.examples = [s['file_name'] for s in self.loaded_scenarios]
        
        logger.info(f"✅ База знаний загружена:")
        logger.info(f"   - Сценариев: {len(self.loaded_scenarios)}")
        logger.info(f"   - Результатов анализов: {len(self.loaded_results)}")
        logger.info(f"   - Базовая информация из PDF: {len(self.base_knowledge)} символов")
        
        return {
            'scenarios': len(self.loaded_scenarios),
            'results': len(self.loaded_results),
            'base_knowledge_length': len(self.base_knowledge)
        }
    
    def _detect_scenario_type(self, file_name: str) -> str:
        """
        Определяет тип сценария по имени файла
        
        Что делает:
        - Анализирует имя файла
        - Определяет тип сценария (онлайн, первые встречи и т.д.)
        
        Args:
            file_name: имя файла
        
        Returns:
            тип сценария или "unknown"
        """
        file_lower = file_name.lower()
        
        if 'онлайн' in file_lower or 'e-com' in file_lower or 'еком' in file_lower:
            return 'scenario_online'
        elif 'первые' in file_lower or 'нович' in file_lower:
            return 'scenario_first_meetings'
        elif 'месяц' in file_lower:
            return 'scenario_first_month'
        elif 'мои встречи' in file_lower or 'встреч' in file_lower:
            return 'scenario_my_meetings'
        else:
            return 'scenario_universal'
    
    def _extract_keywords(self, text: str, max_words: int = 20) -> List[str]:
        """
        Извлекает ключевые слова из текста
        
        Что делает:
        1. Берет первые N слов из текста (самые важные обычно в начале)
        2. Убирает короткие слова (меньше 4 символов)
        3. Возвращает список ключевых слов
        
        Args:
            text: текст для анализа
            max_words: сколько слов взять
        
        Returns:
            список ключевых слов
        """
        # Берем первые слова из текста
        words = text.split()[:max_words]
        
        # Фильтруем: оставляем только слова длиннее 3 символов
        keywords = [w.lower().strip('.,!?;:()[]') for w in words if len(w) > 3]
        
        return keywords
    
    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """
        Вычисляет простую схожесть между двумя текстами
        
        Что делает:
        1. Использует SequenceMatcher для сравнения текстов
        2. Возвращает число от 0 до 1 (1 = полностью одинаковые)
        
        Args:
            text1: первый текст
            text2: второй текст
        
        Returns:
            коэффициент схожести (0.0 - 1.0)
        """
        # Берем первые 1000 символов для сравнения (чтобы не было слишком долго)
        text1_sample = text1[:1000].lower()
        text2_sample = text2[:1000].lower()
        
        # Используем SequenceMatcher для сравнения
        similarity = SequenceMatcher(None, text1_sample, text2_sample).ratio()
        
        return similarity
    
    def search_similar_examples(self, query_text: str, scenario_type: Optional[str] = None, top_k: int = 3) -> List[Dict]:
        """
        Ищет похожие примеры сценариев и результатов для заданного текста
        
        Как работает (простой алгоритм):
        1. Ищет похожие сценарии по типу сценария (если указан)
        2. Ищет похожие результаты анализов
        3. Объединяет результаты и выбирает самые релевантные
        
        Args:
            query_text: текст транскрипции встречи для поиска похожих
            scenario_type: тип сценария для фильтрации (опционально)
            top_k: сколько примеров вернуть (по умолчанию 3)
        
        Returns:
            список похожих примеров сценариев и результатов с оценкой схожести
        """
        if not self.loaded_scenarios and not self.loaded_results:
            logger.warning("База знаний пуста. Сначала загрузите сценарии и результаты.")
            return []
        
        logger.info(f"Поиск похожих примеров для текста длиной {len(query_text)} символов")
        
        all_candidates = []
        
        # Шаг 1: Ищем похожие сценарии
        scenario_candidates = self.loaded_scenarios
        if scenario_type:
            scenario_candidates = [s for s in self.loaded_scenarios if s['scenario_type'] == scenario_type]
            logger.info(f"Отфильтровано сценариев по типу '{scenario_type}': {len(scenario_candidates)}")
        
        if not scenario_candidates and scenario_type:
            logger.warning(f"Не найдено сценариев типа '{scenario_type}'. Используем все.")
            scenario_candidates = self.loaded_scenarios
        
        for scenario in scenario_candidates:
            similarity_score = self._calculate_similarity(query_text, scenario['text'])
            type_bonus = 0.15 if scenario['scenario_type'] == scenario_type else 0
            final_score = min(similarity_score + type_bonus, 1.0)
            
            all_candidates.append({
                'item': scenario,
                'similarity': final_score,
                'type': 'scenario'  # Помечаем как сценарий
            })
        
        # Шаг 2: Ищем похожие результаты анализов
        result_candidates = self.loaded_results
        if scenario_type:
            result_candidates = [r for r in self.loaded_results if r['scenario_type'] == scenario_type]
            logger.info(f"Отфильтровано результатов по типу '{scenario_type}': {len(result_candidates)}")
        
        for result in result_candidates:
            similarity_score = self._calculate_similarity(query_text, result['text'])
            type_bonus = 0.1 if result['scenario_type'] == scenario_type else 0
            final_score = min(similarity_score + type_bonus, 1.0)
            
            all_candidates.append({
                'item': result,
                'similarity': final_score,
                'type': 'result'  # Помечаем как результат
            })
        
        # Шаг 3: Сортируем по схожести (от большей к меньшей)
        all_candidates.sort(key=lambda x: x['similarity'], reverse=True)
        
        # Шаг 4: Берем топ-K самых похожих
        top_results = all_candidates[:top_k]
        
        # Форматируем результат
        results = []
        for item in top_results:
            data = item['item']
            results.append({
                'file_name': data['file_name'],
                'scenario_type': data['scenario_type'],
                'text': data['text'][:1000],  # Первые 1000 символов для контекста
                'similarity': item['similarity'],
                'text_length': data['text_length'],
                'item_type': item['type']  # 'scenario' или 'result'
            })
        
        logger.info(f"Найдено {len(results)} похожих примеров")
        for i, result in enumerate(results, 1):
            logger.info(f"  {i}. [{result['item_type']}] {result['file_name']} (схожесть: {result['similarity']:.2%})")
        
        return results
    
    def enhance_prompt(self, base_prompt: str, query_text: str, scenario_type: str) -> str:
        """
        Улучшает промпт, добавляя контекст из базы знаний (сценарии и результаты)
        
        Что делает:
        1. Добавляет базовую информацию из PDF (всегда первой)
        2. Ищет похожие сценарии и результаты анализов в базе знаний
        3. Добавляет найденные примеры в промпт
        4. Возвращает улучшенный промпт
        
        Args:
            base_prompt: базовый промпт из scenario_prompts.json
            query_text: текст транскрипции встречи
            scenario_type: тип сценария (scenario_online, scenario_first_meetings и т.д.)
        
        Returns:
            улучшенный промпт с контекстом из базы знаний
        """
        logger.info(f"Улучшение промпта для типа сценария: {scenario_type}")
        
        # Шаг 0: Добавляем базовую информацию из PDF (всегда первой)
        enhanced_prompt = base_prompt
        
        if self.base_knowledge:
            base_section = "\n\n📖 БАЗОВАЯ ИНФОРМАЦИЯ О ПРОВЕДЕНИИ МАСТЕРМАЙНДА:\n"
            base_section += "Эта информация содержит общие принципы и правила проведения мастермайндов.\n"
            base_section += "Используй её как основу для понимания формата и требований.\n\n"
            base_section += self.base_knowledge
            base_section += "\n\n[ВАЖНО] Опирайся на эту базовую информацию при анализе.\n"
            
            enhanced_prompt = base_prompt + base_section
            logger.info(f"Добавлена базовая информация из PDF: {len(self.base_knowledge)} символов")
        
        # Шаг 1: Ищем похожие примеры (сценарии и результаты)
        similar_examples = self.search_similar_examples(
            query_text=query_text[:2000],  # Используем первые 2000 символов для поиска
            scenario_type=scenario_type,
            top_k=3  # Берем 3 самых похожих примера (сценарии + результаты)
        )
        
        # Шаг 2: Если нашли примеры, добавляем их в промпт
        if similar_examples:
            context_section = "\n\n📚 КОНТЕКСТ ИЗ БАЗЫ ЗНАНИЙ (примеры сценариев и результатов хороших анализов):\n"
            context_section += "Используй эти примеры для более точного анализа. Обращай внимание на:\n"
            context_section += "- Как должны выглядеть правильные сценарии (из примеров сценариев)\n"
            context_section += "- Как должны выглядеть хорошие результаты проверки (из примеров результатов)\n\n"
            
            # Разделяем сценарии и результаты
            scenarios = [ex for ex in similar_examples if ex.get('item_type') == 'scenario']
            results = [ex for ex in similar_examples if ex.get('item_type') == 'result']
            
            if scenarios:
                context_section += "📋 ПРИМЕРЫ СЦЕНАРИЕВ:\n"
                for i, example in enumerate(scenarios, 1):
                    context_section += f"\nСценарий {i} (из файла: {example['file_name']}):\n"
                    context_section += f"Тип: {example['scenario_type']}\n"
                    context_section += f"Фрагмент:\n{example['text']}...\n"
            
            if results:
                context_section += "\n\n✅ ПРИМЕРЫ РЕЗУЛЬТАТОВ ХОРОШИХ АНАЛИЗОВ:\n"
                for i, example in enumerate(results, 1):
                    context_section += f"\nРезультат {i} (из файла: {example['file_name']}):\n"
                    context_section += f"Тип: {example['scenario_type']}\n"
                    context_section += f"Фрагмент:\n{example['text']}...\n"
            
            context_section += "\n\n[ВАЖНО] Используй контекст из базы знаний для более точных рекомендаций.\n"
            context_section += "- Сравни текущий сценарий с примерами правильных сценариев\n"
            context_section += "- Используй примеры результатов хороших анализов как образец для структуры и стиля ответа\n"
            
            # Добавляем контекст к улучшенному промпту
            enhanced_prompt = enhanced_prompt + context_section
            logger.info(f"Промпт улучшен: добавлено {len(similar_examples)} примеров из базы знаний "
                       f"({len(scenarios)} сценариев, {len(results)} результатов)")
            return enhanced_prompt
        else:
            # Если примеров не найдено, возвращаем промпт с базовой информацией (если она есть)
            if self.base_knowledge:
                logger.info("Похожих примеров не найдено, используем базовый промпт с базовой информацией")
            else:
                logger.info("Похожих примеров не найдено, используем базовый промпт")
            return enhanced_prompt


# Глобальный экземпляр RAG системы (singleton pattern)
_rag_instance = None


def get_rag_system() -> RAGSystem:
    """
    Получает глобальный экземпляр RAG системы
    
    Зачем singleton:
    - Не нужно создавать новую систему каждый раз
    - База знаний загружается один раз
    - Экономия памяти и времени
    
    Returns:
        экземпляр RAGSystem
    """
    global _rag_instance
    
    if _rag_instance is None:
        _rag_instance = RAGSystem()
        # Загружаем базу знаний при первом создании
        _rag_instance.load_knowledge_base()
    
    return _rag_instance


# Тестирование (можно запустить для проверки)
if __name__ == "__main__":
    print("=" * 60)
    print("ТЕСТ RAG СИСТЕМЫ")
    print("=" * 60)
    
    # Создаем экземпляр
    rag = get_rag_system()
    
    # Проверяем загрузку базы знаний
    print("\n✅ RAG система создана")
    print(f"📁 База знаний: {rag.knowledge_base_path}")
    print(f"📄 Найдено файлов: {len(rag.examples)}")
    
    # Показываем загруженные сценарии
    print(f"\n📚 Загружено сценариев: {len(rag.loaded_scenarios)}")
    for i, scenario in enumerate(rag.loaded_scenarios[:5], 1):  # Показываем первые 5
        print(f"  {i}. {scenario['file_name']}")
        print(f"     Тип: {scenario['scenario_type']}")
        print(f"     Размер: {scenario['text_length']} символов")
        print(f"     Превью: {scenario['text'][:100]}...")
    
    if len(rag.loaded_scenarios) > 5:
        print(f"  ... и еще {len(rag.loaded_scenarios) - 5} файлов")
    
    print(f"\n📊 Загружено результатов анализов: {len(rag.loaded_results)}")
    for i, result in enumerate(rag.loaded_results[:3], 1):  # Показываем первые 3
        print(f"  {i}. {result['file_name']}")
        print(f"     Тип: {result['scenario_type']}")
        print(f"     Размер: {result['text_length']} символов")
    
    print(f"\n📖 Базовая информация из PDF: {len(rag.base_knowledge)} символов")
    if rag.base_knowledge:
        print(f"   Превью: {rag.base_knowledge[:200]}...")
    
    # Тестируем поиск похожих примеров
    print("\n" + "=" * 60)
    print("ТЕСТ ПОИСКА ПОХОЖИХ ПРИМЕРОВ")
    print("=" * 60)
    
    # Тестовый запрос
    test_query = "Добрый день! Я буду модератором сегодняшней встречи. Давайте вспомним, в чем суть формата мастермайнда."
    
    print(f"\n🔍 Тестовый запрос: '{test_query[:50]}...'")
    print(f"Ищем похожие примеры...\n")
    
    # Ищем похожие примеры
    similar = rag.search_similar_examples(test_query, scenario_type='scenario_my_meetings', top_k=3)
    
    if similar:
        print(f"✅ Найдено {len(similar)} похожих примеров:\n")
        for i, example in enumerate(similar, 1):
            print(f"{i}. Файл: {example['file_name']}")
            print(f"   Тип: {example['scenario_type']}")
            print(f"   Схожесть: {example['similarity']:.1%}")
            print(f"   Превью: {example['text'][:100]}...")
            print()
    else:
        print("❌ Похожих примеров не найдено")
    
    print("=" * 60)
    print("✅ Шаг 3 выполнен: простой поиск реализован!")
    print("Следующий шаг: интегрируем RAG в scenario_checker")
    print("=" * 60)
