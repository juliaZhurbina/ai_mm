import asyncio
from search import load_transcript, load_triggers, check_semantic_similarity, preprocess_text
from difflib import SequenceMatcher

async def test_matching():
    """Тестируем поиск совпадений между реальным текстом и маркерами"""
    
    print("=== ТЕСТ ПОИСКА СОВПАДЕНИЙ ===")
    
    # Загружаем данные
    try:
        text = load_transcript('trans.docx')
        triggers = load_triggers('triggers.xlsx')
        
        print(f"✅ Текст загружен: {len(text)} символов")
        print(f"✅ Триггеры загружены: {len(triggers)} компетенций")
        
        # Берем первые несколько предложений из транскрипта
        sentences = preprocess_text(text)
        print(f"\n📝 Первые 5 предложений из транскрипта:")
        for i, sent in enumerate(sentences[:5]):
            print(f"{i+1}. {sent[:100]}...")
        
        # Берем маркеры из первой компетенции
        first_comp = list(triggers.keys())[0]
        first_indicator = list(triggers[first_comp].keys())[0]
        pos_markers = triggers[first_comp][first_indicator]['positive_markers']
        
        print(f"\n🎯 Тестируем совпадения с компетенцией: {first_comp}")
        print(f"📊 Индикатор: {first_indicator}")
        print(f"📊 Количество позитивных маркеров: {len(pos_markers)}")
        
        print(f"\n🔍 Первые 3 маркера:")
        markers_list = list(pos_markers.keys())[:3]
        for i, marker in enumerate(markers_list):
            print(f"{i+1}. {marker[:100]}...")
        
        # Тестируем поиск совпадений
        print(f"\n🧪 ТЕСТ СОВПАДЕНИЙ:")
        best_matches = []
        
        for sent in sentences[:10]:  # Проверяем первые 10 предложений
            for marker in markers_list[:3]:  # С первыми 3 маркерами
                similarity = SequenceMatcher(None, sent.lower(), marker.lower()).ratio()
                if similarity > 0.3:  # Если есть хоть какое-то сходство
                    best_matches.append((sent, marker, similarity))
        
        if best_matches:
            print(f"✅ Найдено {len(best_matches)} потенциальных совпадений:")
            # Сортируем по убыванию сходства
            best_matches.sort(key=lambda x: x[2], reverse=True)
            for i, (sent, marker, sim) in enumerate(best_matches[:5]):
                print(f"{i+1}. Сходство: {sim:.3f} ({sim*100:.1f}%)")
                print(f"   Предложение: {sent[:80]}...")
                print(f"   Маркер: {marker[:80]}...")
                print()
        else:
            print("❌ Совпадений не найдено")
            
        # Проверим конкретные фразы из транскрипта
        print(f"\n🎯 ПРОВЕРКА КОНКРЕТНЫХ ФРАЗ:")
        test_phrases = [
            "я понимаю что в этой области я силён",
            "я стараюсь понять потребности клиента", 
            "работаем с клиентами",
            "поделиться опытом",
            "команда дружная"
        ]
        
        for phrase in test_phrases:
            for marker in markers_list[:2]:
                similarity = SequenceMatcher(None, phrase.lower(), marker.lower()).ratio()
                print(f"'{phrase}' → '{marker[:50]}...' = {similarity:.3f} ({similarity*100:.1f}%)")
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")

if __name__ == "__main__":
    asyncio.run(test_matching()) 