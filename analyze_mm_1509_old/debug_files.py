import pandas as pd
from docx import Document
import os

def analyze_transcript(file_path):
    """Анализирует содержимое транскрипта"""
    print(f"=== АНАЛИЗ ФАЙЛА {file_path} ===")
    
    if not os.path.exists(file_path):
        print(f"❌ Файл {file_path} не найден!")
        return
    
    try:
        doc = Document(file_path)
        paragraphs = [para.text for para in doc.paragraphs if para.text.strip()]
        
        print(f"✅ Файл успешно прочитан")
        print(f"📊 Количество абзацев: {len(paragraphs)}")
        print(f"📊 Общая длина текста: {len(' '.join(paragraphs))} символов")
        
        if paragraphs:
            print(f"\n📝 Первые 3 абзаца:")
            for i, para in enumerate(paragraphs[:3]):
                print(f"{i+1}. {para[:100]}{'...' if len(para) > 100 else ''}")
        else:
            print("❌ Текст в файле не найден!")
            
    except Exception as e:
        print(f"❌ Ошибка при чтении файла: {e}")

def analyze_triggers(file_path):
    """Анализирует содержимое файла триггеров"""
    print(f"\n=== АНАЛИЗ ФАЙЛА {file_path} ===")
    
    if not os.path.exists(file_path):
        print(f"❌ Файл {file_path} не найден!")
        return
    
    try:
        df = pd.read_excel(file_path, sheet_name='Лист1')
        print(f"✅ Файл успешно прочитан")
        print(f"📊 Размер таблицы: {df.shape[0]} строк, {df.shape[1]} колонок")
        
        print(f"\n📋 Колонки в файле:")
        for i, col in enumerate(df.columns):
            print(f"{i+1}. '{col}'")
        
        # Анализируем содержимое
        df.columns = df.columns.str.strip()
        df['компетенция'] = df['компетенция'].ffill()
        df['Поведенческие проявления (индикаторы)'] = df['Поведенческие проявления (индикаторы)'].ffill()
        
        print(f"\n🎯 Уникальные компетенции:")
        competencies = df['компетенция'].dropna().unique()
        for i, comp in enumerate(competencies):
            print(f"{i+1}. {comp}")
        
        print(f"\n📈 Пример маркеров из первой компетенции:")
        first_comp = competencies[0] if len(competencies) > 0 else None
        if first_comp:
            comp_data = df[df['компетенция'] == first_comp]
            
            # Ищем позитивные маркеры
            pos_cols = [col for col in df.columns if 'Позитивные проявления' in col]
            neg_cols = [col for col in df.columns if 'Негативные проявления' in col]
            
            print(f"   Позитивные колонки: {pos_cols}")
            print(f"   Негативные колонки: {neg_cols}")
            
            if pos_cols:
                print(f"\n   📝 Пример позитивных маркеров:")
                for i, marker in enumerate(comp_data[pos_cols[0]].dropna().head(3)):
                    if marker and str(marker).strip():
                        print(f"   {i+1}. {marker}")
        
    except Exception as e:
        print(f"❌ Ошибка при чтении файла: {e}")

def test_similarity():
    """Тестируем базовую работу сравнения"""
    print(f"\n=== ТЕСТ СЕМАНТИЧЕСКОГО АНАЛИЗА ===")
    from difflib import SequenceMatcher
    
    # Тестовые фразы
    test_phrase = "Я стараюсь понять потребности клиента"
    test_markers = [
        "понимает потребности клиентов",
        "выясняет потребности клиента", 
        "активно слушает клиента",
        "совершенно несвязанная фраза"
    ]
    
    print(f"🧪 Тестовая фраза: '{test_phrase}'")
    print(f"🎯 Тестовые маркеры:")
    
    for marker in test_markers:
        similarity = SequenceMatcher(None, test_phrase.lower(), marker.lower()).ratio()
        print(f"   '{marker}' → {similarity:.3f} ({similarity*100:.1f}%)")

if __name__ == "__main__":
    analyze_transcript('trans.docx')
    analyze_triggers('triggers.xlsx')
    test_similarity() 