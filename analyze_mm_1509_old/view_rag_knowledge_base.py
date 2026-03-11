"""
Скрипт для просмотра базы знаний RAG системы

Что делает:
- Показывает все загруженные сценарии и результаты анализов
- Показывает их содержимое
- Позволяет искать по базе знаний
"""

from rag_system import get_rag_system
import json


def print_separator():
    """Красивая линия-разделитель"""
    print("=" * 80)


def view_all_transcripts(rag):
    """
    Показывает все загруженные сценарии и результаты анализов
    
    Что показывает:
    - Имя файла
    - Тип сценария
    - Размер текста
    - Превью содержимого
    """
    print_separator()
    print("📚 ВСЕ ЗАГРУЖЕННЫЕ СЦЕНАРИИ И РЕЗУЛЬТАТЫ")
    print_separator()
    
    if not rag.loaded_scenarios and not rag.loaded_results:
        print("❌ База знаний пуста!")
        return
    
    print(f"\n📋 СЦЕНАРИИ (всего: {len(rag.loaded_scenarios)}):\n")
    
    for i, scenario in enumerate(rag.loaded_scenarios, 1):
        print(f"{i}. 📄 {scenario['file_name']}")
        print(f"   Тип сценария: {scenario['scenario_type']}")
        print(f"   Размер: {scenario['text_length']:,} символов")
        print(f"   Путь: {scenario['file_path']}")
        
        # Показываем первые 200 символов текста
        preview = scenario['text'][:200].replace('\n', ' ')
        print(f"   Превью: {preview}...")
        print()
    
    print(f"\n✅ РЕЗУЛЬТАТЫ АНАЛИЗОВ (всего: {len(rag.loaded_results)}):\n")
    
    for i, result in enumerate(rag.loaded_results, 1):
        print(f"{i}. 📊 {result['file_name']}")
        print(f"   Тип сценария: {result['scenario_type']}")
        print(f"   Размер: {result['text_length']:,} символов")
        print(f"   Путь: {result['file_path']}")
        
        # Показываем первые 200 символов текста
        preview = result['text'][:200].replace('\n', ' ')
        print(f"   Превью: {preview}...")
        print()


def view_transcript_details(rag, file_name=None, index=None, item_type='scenario'):
    """
    Показывает детальную информацию о конкретном сценарии или результате
    
    Args:
        file_name: имя файла для просмотра
        index: номер в списке (начиная с 1)
        item_type: 'scenario' или 'result'
    """
    print_separator()
    if item_type == 'scenario':
        print("📖 ДЕТАЛЬНАЯ ИНФОРМАЦИЯ О СЦЕНАРИИ")
    else:
        print("📖 ДЕТАЛЬНАЯ ИНФОРМАЦИЯ О РЕЗУЛЬТАТЕ АНАЛИЗА")
    print_separator()
    
    # Выбираем нужный список
    items_list = rag.loaded_scenarios if item_type == 'scenario' else rag.loaded_results
    
    if not items_list:
        print(f"❌ Список {'сценариев' if item_type == 'scenario' else 'результатов'} пуст!")
        return
    
    # Находим элемент
    item = None
    
    if index:
        if 1 <= index <= len(items_list):
            item = items_list[index - 1]
        else:
            print(f"❌ Неверный номер. Доступны номера от 1 до {len(items_list)}")
            return
    elif file_name:
        for t in items_list:
            if file_name in t['file_name']:
                item = t
                break
        
        if not item:
            print(f"❌ Файл '{file_name}' не найден")
            return
    else:
        print("❌ Укажите file_name или index")
        return
    
    # Показываем детальную информацию
    print(f"\n📄 Файл: {item['file_name']}")
    print(f"📁 Путь: {item['file_path']}")
    print(f"🏷️  Тип сценария: {item['scenario_type']}")
    print(f"📊 Размер: {item['text_length']:,} символов")
    print(f"📝 Строк: {len(item['text'].split(chr(10)))}")
    
    print("\n" + "-" * 80)
    if item_type == 'scenario':
        print("ПОЛНЫЙ ТЕКСТ СЦЕНАРИЯ:")
    else:
        print("ПОЛНЫЙ ТЕКСТ РЕЗУЛЬТАТА АНАЛИЗА:")
    print("-" * 80)
    print(item['text'])
    print("-" * 80)


def test_search(rag, query_text, scenario_type=None):
    """
    Тестирует поиск похожих примеров
    
    Args:
        query_text: текст для поиска
        scenario_type: тип сценария (опционально)
    """
    print_separator()
    print("🔍 ТЕСТ ПОИСКА ПОХОЖИХ ПРИМЕРОВ")
    print_separator()
    
    print(f"\nЗапрос: '{query_text[:100]}...'")
    if scenario_type:
        print(f"Тип сценария: {scenario_type}")
    
    print("\nИщем похожие примеры...\n")
    
    # Ищем похожие примеры
    results = rag.search_similar_examples(
        query_text=query_text,
        scenario_type=scenario_type,
        top_k=5
    )
    
    if results:
        print(f"✅ Найдено {len(results)} похожих примеров:\n")
        
        for i, result in enumerate(results, 1):
            item_type_label = "📋 Сценарий" if result.get('item_type') == 'scenario' else "✅ Результат"
            print(f"{i}. {item_type_label} - {result['file_name']}")
            print(f"   🏷️  Тип: {result['scenario_type']}")
            print(f"   📊 Схожесть: {result['similarity']:.1%}")
            print(f"   📏 Размер: {result['text_length']:,} символов")
            print(f"   📝 Фрагмент:")
            print(f"   {result['text'][:300]}...")
            print()
    else:
        print("❌ Похожих примеров не найдено")


def show_statistics(rag):
    """Показывает статистику по базе знаний"""
    print_separator()
    print("📊 СТАТИСТИКА БАЗЫ ЗНАНИЙ")
    print_separator()
    
    if not rag.loaded_scenarios and not rag.loaded_results:
        print("❌ База знаний пуста!")
        return
    
    # Статистика по типам сценариев (для сценариев)
    scenario_counts = {}
    total_scenario_chars = 0
    
    for scenario in rag.loaded_scenarios:
        scenario_type = scenario['scenario_type']
        scenario_counts[scenario_type] = scenario_counts.get(scenario_type, 0) + 1
        total_scenario_chars += scenario['text_length']
    
    # Статистика по типам сценариев (для результатов)
    result_counts = {}
    total_result_chars = 0
    
    for result in rag.loaded_results:
        scenario_type = result['scenario_type']
        result_counts[scenario_type] = result_counts.get(scenario_type, 0) + 1
        total_result_chars += result['text_length']
    
    print(f"\n📚 Всего сценариев: {len(rag.loaded_scenarios)}")
    if rag.loaded_scenarios:
        print(f"📝 Всего символов в сценариях: {total_scenario_chars:,}")
        print(f"📊 Средний размер сценария: {total_scenario_chars // len(rag.loaded_scenarios):,} символов")
        
        print(f"\n📋 Распределение сценариев по типам:")
        for scenario_type, count in sorted(scenario_counts.items()):
            print(f"   • {scenario_type}: {count} файлов")
    
        print(f"\n✅ Всего результатов анализов: {len(rag.loaded_results)}")
    if rag.loaded_results:
        print(f"📝 Всего символов в результатах: {total_result_chars:,}")
        print(f"📊 Средний размер результата: {total_result_chars // len(rag.loaded_results):,} символов")
        
        print(f"\n📋 Распределение результатов по типам:")
        for scenario_type, count in sorted(result_counts.items()):
            print(f"   • {scenario_type}: {count} файлов")
    
    print(f"\n📖 Базовая информация из PDF: {len(rag.base_knowledge):,} символов")
    if rag.base_knowledge:
        print(f"   Превью: {rag.base_knowledge[:300]}...")


def interactive_menu(rag):
    """Интерактивное меню для просмотра базы знаний"""
    while True:
        print_separator()
        print("🔍 ПРОСМОТР БАЗЫ ЗНАНИЙ RAG")
        print_separator()
        print("\nВыберите действие:")
        print("1. Показать все сценарии и результаты (список)")
        print("2. Показать детали конкретного сценария")
        print("3. Показать детали конкретного результата")
        print("4. Показать базовую информацию из PDF")
        print("5. Тест поиска похожих примеров")
        print("6. Статистика базы знаний")
        print("7. Экспорт базы знаний в JSON")
        print("0. Выход")
        
        choice = input("\nВаш выбор: ").strip()
        
        if choice == "1":
            view_all_transcripts(rag)
            input("\nНажмите Enter для продолжения...")
        
        elif choice == "2":
            print("\nВведите номер сценария (из списка выше) или часть имени файла:")
            user_input = input("> ").strip()
            
            # Пытаемся понять, это номер или имя файла
            try:
                index = int(user_input)
                view_transcript_details(rag, index=index, item_type='scenario')
            except ValueError:
                view_transcript_details(rag, file_name=user_input, item_type='scenario')
            
            input("\nНажмите Enter для продолжения...")
        
        elif choice == "3":
            print("\nВведите номер результата (из списка выше) или часть имени файла:")
            user_input = input("> ").strip()
            
            # Пытаемся понять, это номер или имя файла
            try:
                index = int(user_input)
                view_transcript_details(rag, index=index, item_type='result')
            except ValueError:
                view_transcript_details(rag, file_name=user_input, item_type='result')
            
            input("\nНажмите Enter для продолжения...")
        
        elif choice == "4":
            print_separator()
            print("📖 БАЗОВАЯ ИНФОРМАЦИЯ ИЗ PDF")
            print_separator()
            
            if rag.base_knowledge:
                print(f"\nРазмер: {len(rag.base_knowledge):,} символов\n")
                print("-" * 80)
                print(rag.base_knowledge)
                print("-" * 80)
            else:
                print("\n❌ Базовая информация не загружена!")
                print("Убедитесь, что в папке 'транскрибации, промпты/промпты' есть PDF файлы")
                print("с общей информацией про мастермайнды (без специфических названий сценариев)")
            
            input("\nНажмите Enter для продолжения...")
        
        elif choice == "5":
            print("\nВведите текст для поиска похожих примеров:")
            query = input("> ").strip()
            
            print("\nВведите тип сценария (или Enter для поиска по всем):")
            print("  - scenario_online")
            print("  - scenario_first_meetings")
            print("  - scenario_first_month")
            print("  - scenario_my_meetings")
            print("  - scenario_universal")
            scenario_type = input("> ").strip() or None
            
            test_search(rag, query, scenario_type)
            input("\nНажмите Enter для продолжения...")
        
        elif choice == "6":
            show_statistics(rag)
            input("\nНажмите Enter для продолжения...")
        
        elif choice == "7":
            export_to_json(rag)
            input("\nНажмите Enter для продолжения...")
        
        elif choice == "0":
            print("\n👋 До свидания!")
            break
        
        else:
            print("\n❌ Неверный выбор. Попробуйте снова.")


def export_to_json(rag):
    """Экспортирует базу знаний в JSON файл"""
    print_separator()
    print("💾 ЭКСПОРТ БАЗЫ ЗНАНИЙ В JSON")
    print_separator()
    
    # Формируем данные для экспорта
    export_data = {
        'total_scenarios': len(rag.loaded_scenarios),
        'total_results': len(rag.loaded_results),
        'base_knowledge_length': len(rag.base_knowledge),
        'scenarios': [],
        'results': [],
        'base_knowledge': rag.base_knowledge
    }
    
    for scenario in rag.loaded_scenarios:
        export_data['scenarios'].append({
            'file_name': scenario['file_name'],
            'file_path': scenario['file_path'],
            'scenario_type': scenario['scenario_type'],
            'text_length': scenario['text_length'],
            'text_preview': scenario['text'][:500],  # Первые 500 символов
            'full_text': scenario['text']  # Полный текст
        })
    
    for result in rag.loaded_results:
        export_data['results'].append({
            'file_name': result['file_name'],
            'file_path': result['file_path'],
            'scenario_type': result['scenario_type'],
            'text_length': result['text_length'],
            'text_preview': result['text'][:500],  # Первые 500 символов
            'full_text': result['text']  # Полный текст
        })
    
    # Сохраняем в файл
    output_file = 'rag_knowledge_base_export.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(export_data, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ База знаний экспортирована в файл: {output_file}")
    print(f"   - Сценариев: {len(export_data['scenarios'])}")
    print(f"   - Результатов: {len(export_data['results'])}")
    print(f"   - Базовая информация: {len(export_data['base_knowledge']):,} символов")
    print(f"   - Размер файла: {len(json.dumps(export_data, ensure_ascii=False)):,} символов")


def main():
    """Главная функция"""
    print("=" * 80)
    print("🔍 ПРОСМОТР БАЗЫ ЗНАНИЙ RAG СИСТЕМЫ")
    print("=" * 80)
    
    # Загружаем RAG систему
    print("\n⏳ Загрузка базы знаний...")
    rag = get_rag_system()
    
    if not rag.loaded_scenarios and not rag.loaded_results:
        print("\n❌ База знаний пуста!")
        print("Убедитесь, что:")
        print("  - В папке 'транскрибации, промпты/промпты' есть файлы сценариев (.docx, .txt, .pdf)")
        print("  - В папке 'транскрибации, промпты' есть файлы результатов анализов (с 'результат' в названии, .docx, .pdf)")
        return
    
    print(f"✅ База знаний загружена:")
    print(f"   - Сценариев: {len(rag.loaded_scenarios)}")
    print(f"   - Результатов анализов: {len(rag.loaded_results)}")
    print(f"   - Базовая информация из PDF: {len(rag.base_knowledge):,} символов")
    
    # Показываем краткую статистику
    show_statistics(rag)
    
    # Запускаем интерактивное меню
    print("\n")
    interactive_menu(rag)


if __name__ == "__main__":
    main()
