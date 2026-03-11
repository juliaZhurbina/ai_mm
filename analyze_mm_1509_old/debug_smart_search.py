import asyncio
import logging
import time
from search import load_transcript, load_triggers, AsyncGigaChat
from smart_filter import SmartPhraseFilter

async def debug_analysis():
    """Отладочный анализ по шагам"""
    
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
    
    print("=== ОТЛАДКА АНАЛИЗА ===")
    
    try:
        # Шаг 1: Загрузка файлов
        print("1. Загружаю файлы...")
        start_time = time.time()
        text = load_transcript('trans.docx')
        triggers = load_triggers('triggers.xlsx')
        print(f"✅ Файлы загружены за {time.time() - start_time:.2f}с: {len(text)} символов, {len(triggers)} компетенций")
        
        # Шаг 2: Инициализация умного фильтра
        print("2. Инициализирую умный фильтр...")
        start_time = time.time()
        smart_filter = SmartPhraseFilter()
        print(f"✅ Умный фильтр инициализирован за {time.time() - start_time:.2f}с")
        
        # Шаг 3: Тест фильтра на небольшом тексте
        print("3. Тестирую фильтр...")
        test_phrases = text.split('.', 10)[:10]  # Первые 10 предложений
        meaningful_count = 0
        
        for i, phrase in enumerate(test_phrases):
            if phrase.strip():
                try:
                    start_time = time.time()
                    is_meaningful = smart_filter.is_meaningful_phrase_basic(phrase)
                    filter_time = time.time() - start_time
                    
                    if is_meaningful:
                        meaningful_count += 1
                    print(f"   Фраза {i+1} ({filter_time:.3f}с): {'✅' if is_meaningful else '❌'} - {phrase[:50]}...")
                except Exception as e:
                    print(f"   ❌ Ошибка в фразе {i+1}: {e}")
        
        print(f"✅ Фильтр работает. Значимых фраз: {meaningful_count}/{len(test_phrases)}")
        
        # Шаг 4: Попытка подключения к GigaChat
        print("4. Подключаюсь к GigaChat...")
        try:
            start_time = time.time()
            giga_chat = AsyncGigaChat()
            await giga_chat.initialize()
            init_time = time.time() - start_time
            print(f"✅ GigaChat подключен за {init_time:.2f}с")
            
            # Простой тест
            start_time = time.time()
            response = await giga_chat.send("Привет, это тест. Ответь кратко: работаешь?")
            request_time = time.time() - start_time
            print(f"✅ Тест GigaChat ({request_time:.2f}с): {response[:50]}...")
            
            await giga_chat.close()
            
        except Exception as e:
            print(f"❌ Ошибка GigaChat: {e}")
            return
        
        # Шаг 5: Анализ производительности
        print("5. Анализ производительности...")
        
        # Считаем сколько фраз нужно обработать
        sentences = text.split('.')
        meaningful_sentences = []
        
        print("   Анализирую первые 100 предложений...")
        start_time = time.time()
        
        for i, sent in enumerate(sentences[:100]):
            if sent.strip() and smart_filter.is_meaningful_phrase_basic(sent):
                meaningful_sentences.append(sent)
            
            if i % 25 == 0:
                print(f"      Обработано {i}/100 предложений...")
        
        filter_time = time.time() - start_time
        
        # Считаем маркеры
        total_markers = 0
        for comp_data in triggers.values():
            for ind_data in comp_data.values():
                total_markers += len(ind_data['positive_markers']) + len(ind_data['negative_markers'])
        
        estimated_comparisons = len(meaningful_sentences) * total_markers
        
        print(f"📊 Статистика:")
        print(f"   - Всего предложений: {len(sentences)}")
        print(f"   - Значимых предложений (первые 100): {len(meaningful_sentences)}")
        print(f"   - Время фильтрации 100 предл.: {filter_time:.2f}с")
        print(f"   - Всего маркеров: {total_markers}")
        print(f"   - Ожидаемые сравнения (100 предл.): {estimated_comparisons}")
        
        # Экстраполяция на весь текст
        full_meaningful = int(len(meaningful_sentences) * len(sentences) / 100)
        full_comparisons = full_meaningful * total_markers
        estimated_time = (filter_time * len(sentences) / 100) + (full_comparisons * 0.1)  # 0.1с на сравнение
        
        print(f"   - Полная обработка потребует: ~{full_comparisons} сравнений")
        print(f"   - Ожидаемое время: ~{estimated_time/60:.1f} минут")
        
        if estimated_time > 300:  # Больше 5 минут
            print("⚠️  ПРЕДУПРЕЖДЕНИЕ: Очень долгая обработка! Рекомендуется оптимизация.")
        
        print("\n✅ Отладка завершена. Основные компоненты работают.")
        
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(debug_analysis()) 