import pandas as pd
from docx import Document
import re
from difflib import SequenceMatcher

def load_transcript(path: str) -> str:
    """Читает весь текст встречи из .docx и возвращает строку."""
    doc = Document(path)
    return "\n".join(para.text for para in doc.paragraphs if para.text.strip())

def load_triggers(xlsx_path: str) -> dict:
    """Загружает триггеры из Excel файла с группировкой по компетенциям и индикаторам."""
    df = pd.read_excel(xlsx_path, sheet_name='Лист1')
    df.columns = df.columns.str.strip()

    # Заполняем пропущенные значения для иерархии
    df['компетенция'] = df['компетенция'].ffill()
    df['Поведенческие проявления (индикаторы)'] = df['Поведенческие проявления (индикаторы)'].ffill()

    result = {}
    for (comp, indicator), group in df.groupby(['компетенция', 'Поведенческие проявления (индикаторы)']):
        # Собираем все позитивные и негативные маркеры с их баллами
        pos_markers = {}
        neg_markers = {}

        # Обрабатываем все колонки с позитивными маркерами (10, 8, 6, 4)
        for score in [10, 8, 6, 4]:
            col_name = f'Фразы/маркеры "Позитивные проявления" {score}'
            if col_name in group.columns:
                markers = group[col_name].dropna().astype(str).str.strip()
                for marker in markers:
                    if marker and marker != 'nan':
                        pos_markers[marker] = score

        # Обрабатываем все колонки с негативными маркерами (10, 8, 6, 4, 2)
        for score in [10, 8, 6, 4, 2]:
            col_name = f'Фразы/маркеры "Негативные проявления" {score}'
            if col_name in group.columns:
                markers = group[col_name].dropna().astype(str).str.strip()
                for marker in markers:
                    if marker and marker != 'nan':
                        neg_markers[marker] = score

        if comp not in result:
            result[comp] = {}

        result[comp][indicator] = {
            "positive_markers": pos_markers,
            "negative_markers": neg_markers
        }
    return result

def preprocess_text_simple(text: str) -> list:
    """Простая предобработка текста для диагностики"""
    sentences = re.split(r'[.!?]+', text)
    return [s.strip() for s in sentences if s.strip() and len(s.strip()) > 10]

def diagnose_scoring_algorithm():
    """Диагностирует проблемы в алгоритме подсчета баллов"""
    
    print("=== ДИАГНОСТИКА АЛГОРИТМА ПОДСЧЕТА БАЛЛОВ ===")
    
    # Загружаем данные
    text = load_transcript('trans.docx')
    triggers = load_triggers('triggers.xlsx')
    sentences = preprocess_text_simple(text)
    
    print(f"📊 Загружено предложений: {len(sentences)}")
    print(f"📊 Компетенций: {len(triggers)}")
    
    # Анализируем проблемную компетенцию "Управление собой и жизнестойкость"
    problem_comp = "Управление собой и жизнестойкость"
    
    if problem_comp in triggers:
        print(f"\n🔍 АНАЛИЗ ПРОБЛЕМНОЙ КОМПЕТЕНЦИИ: {problem_comp}")
        comp_data = triggers[problem_comp]
        
        for indicator, data in comp_data.items():
            print(f"\n--- Индикатор: {indicator} ---")
            
            pos_markers = data['positive_markers']
            neg_markers = data['negative_markers']
            
            print(f"Позитивных маркеров: {len(pos_markers)}")
            print(f"Негативных маркеров: {len(neg_markers)}")
            
            # Показываем баллы
            if pos_markers:
                pos_scores = list(pos_markers.values())
                print(f"Позитивные баллы: {pos_scores}")
                print(f"Макс позитивный: {max(pos_scores)}")
            
            if neg_markers:
                neg_scores = list(neg_markers.values())
                print(f"Негативные баллы: {neg_scores}")
                print(f"Макс негативный: {max(neg_scores)}")
                
                # Проверяем аномальные значения
                if any(score > 100 for score in neg_scores):
                    print("❌ АНОМАЛИЯ: Негативные баллы больше 100!")
                
                total_neg_weight = sum(neg_scores)
                print(f"Общий вес негативных маркеров: {total_neg_weight}")
                
                if total_neg_weight > 1000:
                    print("❌ ПРОБЛЕМА: Слишком большой суммарный вес негативных маркеров!")
            
            # Расчет максимального балла индикатора
            max_pos = max(pos_markers.values()) if pos_markers else 0
            max_neg = max(neg_markers.values()) if neg_markers else 0
            max_score = max_pos + max_neg
            
            print(f"Максимальный балл индикатора: {max_pos} + {max_neg} = {max_score}")
            
            # Симуляция негативного сценария
            if neg_markers:
                # Представим, что нашли много негативных совпадений
                sim_neg_total = sum(score * 0.3 for score in neg_markers.values())  # 30% сходство
                sim_percentage = (-sim_neg_total / max_score * 100) if max_score > 0 else 0
                
                print(f"Симуляция максимального негатива:")
                print(f"  Негативных баллов: -{sim_neg_total:.1f}")
                print(f"  Процент: {sim_percentage:.1f}%")
                
                if sim_percentage < -500:
                    print("❌ ВОТ ИСТОЧНИК ПРОБЛЕМЫ! Негативных маркеров слишком много!")
            
            print("-" * 80)

if __name__ == "__main__":
    diagnose_scoring_algorithm() 