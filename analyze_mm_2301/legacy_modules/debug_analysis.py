import asyncio
from search import load_transcript, load_triggers, preprocess_text, AsyncGigaChat
from difflib import SequenceMatcher

async def debug_analysis():
    """Отладочный анализ для выявления проблем"""
    
    print("=== ОТЛАДОЧНЫЙ АНАЛИЗ ===")
    
    # Загружаем данные
    text = load_transcript('trans.docx')
    triggers = load_triggers('triggers.xlsx')
    sentences = preprocess_text(text)
    
    print(f"✅ Загружено предложений: {len(sentences)}")
    print(f"✅ Компетенций: {len(triggers)}")
    
    # Считаем общее количество маркеров
    total_markers = 0
    for comp_data in triggers.values():
        for ind_data in comp_data.values():
            total_markers += len(ind_data['positive_markers']) + len(ind_data['negative_markers'])
    
    print(f"✅ Всего маркеров: {total_markers}")
    
    # Тестируем подключение к GigaChat
    print(f"\n🤖 ТЕСТ GIGACHAT API:")
    try:
        giga_chat = AsyncGigaChat()
        await giga_chat.initialize()
        print(f"✅ GigaChat успешно подключен")
        
        # Простой тест
        test_response = await giga_chat.send("Привет, как дела?")
        print(f"✅ Тест-ответ: {test_response[:50]}...")
        
        await giga_chat.close()
        
    except Exception as e:
        print(f"❌ Ошибка GigaChat: {e}")
        print(f"🔧 Будем использовать только SequenceMatcher")
    
    # Простой анализ без GigaChat
    print(f"\n🧪 АНАЛИЗ БЕЗ GIGACHAT (только SequenceMatcher):")
    
    FALLBACK_THRESHOLD = 0.1  # Порог для SequenceMatcher
    found_matches = 0
    
    # Берем первую компетенцию для теста
    first_comp = list(triggers.keys())[0]
    first_indicator = list(triggers[first_comp].keys())[0]
    pos_markers = triggers[first_comp][first_indicator]['positive_markers']
    
    print(f"🎯 Тестируем: {first_comp} -> {first_indicator}")
    print(f"📊 Маркеров: {len(pos_markers)}")
    
    best_matches = []
    
    for sent in sentences[:20]:  # Первые 20 предложений
        for marker, score in list(pos_markers.items())[:3]:  # Первые 3 маркера
            similarity = SequenceMatcher(None, sent.lower(), marker.lower()).ratio()
            
            if similarity >= FALLBACK_THRESHOLD:
                found_matches += 1
                weighted_score = score * similarity
                best_matches.append({
                    "sentence": sent,
                    "marker": marker,
                    "similarity": similarity,
                    "score": weighted_score,
                    "original_score": score
                })
    
    print(f"✅ Найдено совпадений: {found_matches}")
    
    if best_matches:
        # Сортируем по убыванию сходства
        best_matches.sort(key=lambda x: x['similarity'], reverse=True)
        
        print(f"\n🏆 ТОП-3 СОВПАДЕНИЯ:")
        for i, match in enumerate(best_matches[:3]):
            print(f"\n{i+1}. Сходство: {match['similarity']:.3f} ({match['similarity']*100:.1f}%)")
            print(f"   Взвешенный балл: {match['score']:.2f} из {match['original_score']}")
            print(f"   Предложение: {match['sentence'][:80]}...")
            print(f"   Маркер: {match['marker'][:80]}...")
    
    # Проверяем лимит токенов
    print(f"\n📊 ПРОВЕРКА ЛИМИТОВ:")
    total_text_length = sum(len(sent) + len(marker) for sent in sentences[:10] 
                           for marker in list(pos_markers.keys())[:3])
    
    print(f"📊 Примерная длина для анализа 10 предложений: {total_text_length} символов")
    print(f"📊 Лимит токенов в скрипте: 2000")
    print(f"📊 Превышение: {'Да' if total_text_length > 2000 else 'Нет'}")

if __name__ == "__main__":
    asyncio.run(debug_analysis())