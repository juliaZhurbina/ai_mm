def format_detailed_report(analysis: dict, SEMANTIC_THRESHOLD: float, MAX_POSITIVE_MATCHES: int, MAX_NEGATIVE_MATCHES: int, MIN_PERCENTAGE: int, MAX_PERCENTAGE: int) -> str:
    """Формирует подробный итоговый отчет с диагностикой"""
    
    # Извлекаем детальную статистику
    detailed_stats = analysis.get('_detailed_stats', {})
    filter_stats = detailed_stats.get('filter_stats', {})
    competency_stats = detailed_stats.get('competency_stats', {})
    
    report = "🔧 ПОДРОБНЫЙ ОТЧЕТ ПО АНАЛИЗУ КОМПЕТЕНЦИЙ\n\n"
    report += "=" * 80 + "\n"
    report += "📊 ОБЩАЯ СТАТИСТИКА ФИЛЬТРАЦИИ ТЕКСТА\n"
    report += "=" * 80 + "\n\n"
    
    if filter_stats:
        report += f"Всего предложений в тексте: {filter_stats.get('total_sentences', 0)}\n"
        report += f"Прошли умный фильтр: {filter_stats.get('passed_filter', 0)}\n"
        report += f"Отфильтровано по паттернам: {filter_stats.get('filtered_by_pattern', 0)}\n"
        report += f"Отфильтровано по длине: {filter_stats.get('filtered_by_length', 0)}\n"
        report += f"Отфильтровано по стоп-словам: {filter_stats.get('filtered_by_stopwords', 0)}\n"
        report += f"Отфильтровано по морфологии: {filter_stats.get('filtered_by_morphology', 0)}\n\n"
        
        # Примеры отфильтрованных фраз
        filtered_examples = filter_stats.get('filtered_examples', {})
        
        if filtered_examples.get('pattern'):
            report += "🚫 ПРИМЕРЫ ФРАЗ, ОТФИЛЬТРОВАННЫХ ПО ПАТТЕРНАМ:\n"
            for i, example in enumerate(filtered_examples['pattern'], 1):
                report += f"  {i}. \"{example}...\"\n"
            report += "\n"
        
        if filtered_examples.get('length'):
            report += "📏 ПРИМЕРЫ ФРАЗ, ОТФИЛЬТРОВАННЫХ ПО ДЛИНЕ (< 30 символов):\n"
            for i, example in enumerate(filtered_examples['length'], 1):
                report += f"  {i}. \"{example}...\"\n"
            report += "\n"
        
        if filtered_examples.get('stopwords'):
            report += "⛔ ПРИМЕРЫ ФРАЗ, ОТФИЛЬТРОВАННЫХ ПО СТОП-СЛОВАМ (>70%):\n"
            for i, example in enumerate(filtered_examples['stopwords'], 1):
                report += f"  {i}. \"{example}...\"\n"
            report += "\n"
        
        if filtered_examples.get('morphology'):
            report += "🔤 ПРИМЕРЫ ФРАЗ, ОТФИЛЬТРОВАННЫХ ПО МОРФОЛОГИИ (<5 значимых слов):\n"
            for i, example in enumerate(filtered_examples['morphology'], 1):
                report += f"  {i}. \"{example}...\"\n"
            report += "\n"
    
    report += "=" * 80 + "\n"
    report += "🎯 НАСТРОЙКИ АНАЛИЗА\n"
    report += "=" * 80 + "\n\n"
    report += f"✅ Порог семантического сходства: {SEMANTIC_THRESHOLD*100:.0f}%\n"
    report += f"✅ Контекстуальная проверка релевантности включена\n"
    report += f"✅ Тематическая категоризация контента включена\n"
    report += f"✅ Максимум позитивных совпадений на индикатор: {MAX_POSITIVE_MATCHES}\n"
    report += f"✅ Максимум негативных совпадений на индикатор: {MAX_NEGATIVE_MATCHES}\n"
    report += f"✅ Диапазон итоговых процентов: {MIN_PERCENTAGE}% - {MAX_PERCENTAGE}%\n\n"

    # Анализ компетенций
    for comp, data in analysis.items():
        if comp == '_detailed_stats':  # Пропускаем служебные данные
            continue
            
        max_score = data["max_score"]
        current_score = data["total_score"]
        
        # Расчет процента с ограничениями
        if max_score > 0:
            percentage = (current_score / max_score * 100)
            percentage = max(percentage, MIN_PERCENTAGE)
            percentage = min(percentage, MAX_PERCENTAGE)
        else:
            percentage = 0

        # Уровни компетенции
        if percentage >= 70:
            level = "Высокий"
        elif percentage >= 40:
            level = "Средний"
        elif percentage >= 0:
            level = "Низкий"
        else:
            level = "Критически низкий"

        report += "=" * 80 + "\n"
        report += f"🏆 КОМПЕТЕНЦИЯ: {comp}\n"
        report += "=" * 80 + "\n"
        report += f"Общий балл: {current_score:.1f} из {max_score} ({percentage:.1f}% - {level} уровень)\n\n"
        
        # Статистика по компетенции
        comp_stat = competency_stats.get(comp, {})
        if comp_stat:
            report += f"📈 СТАТИСТИКА АНАЛИЗА КОМПЕТЕНЦИИ:\n"
            report += f"   Всего маркеров: {comp_stat.get('total_markers', 0)}\n"
            report += f"   Всего сравнений: {comp_stat.get('total_comparisons', 0)}\n"
            report += f"   Найдено совпадений: {comp_stat.get('matches_found', 0)}\n"
            report += f"   Ниже порога сходства: {comp_stat.get('matches_below_threshold', 0)}\n"
            report += f"   Отфильтровано по контексту: {comp_stat.get('contextually_irrelevant', 0)}\n\n"

        for indicator, ind_data in data["indicators"].items():
            # Расчет процента для индикатора
            if ind_data['max_score'] > 0:
                ind_percentage = (ind_data['score'] / ind_data['max_score'] * 100)
                ind_percentage = max(ind_percentage, MIN_PERCENTAGE)
                ind_percentage = min(ind_percentage, MAX_PERCENTAGE)
            else:
                ind_percentage = 0
                
            report += f"🎯 ИНДИКАТОР: {indicator}\n"
            report += f"Балл: {ind_data['score']:.1f} из {ind_data['max_score']} ({ind_percentage:.1f}%)\n"
            
            # Подробная статистика индикатора
            detailed_ind_stats = ind_data.get('detailed_stats', {})
            if detailed_ind_stats:
                report += f"\n📊 ДЕТАЛЬНАЯ СТАТИСТИКА ИНДИКАТОРА:\n"
                report += f"   Позитивных маркеров: {detailed_ind_stats.get('positive_markers', 0)}\n"
                report += f"   Негативных маркеров: {detailed_ind_stats.get('negative_markers', 0)}\n"
                report += f"   Позитивных сравнений: {detailed_ind_stats.get('positive_comparisons', 0)}\n"
                report += f"   Негативных сравнений: {detailed_ind_stats.get('negative_comparisons', 0)}\n"
                report += f"   Позитивных совпадений: {detailed_ind_stats.get('positive_matches', 0)}\n"
                report += f"   Негативных совпадений: {detailed_ind_stats.get('negative_matches', 0)}\n"
                report += f"   Ниже порога: {detailed_ind_stats.get('below_threshold', 0)}\n"
                report += f"   Отфильтровано по контексту: {detailed_ind_stats.get('contextually_filtered', 0)}\n"
                
                # Детальный анализ каждого маркера
                marker_analysis = detailed_ind_stats.get('marker_analysis', {})
                if marker_analysis:
                    report += f"\n🔍 ПОДРОБНЫЙ АНАЛИЗ МАРКЕРОВ:\n"
                    for marker_key, marker_data in marker_analysis.items():
                        marker_type = "ПОЗИТИВНЫЙ" if marker_key.startswith('pos_') else "НЕГАТИВНЫЙ"
                        report += f"\n   📌 {marker_type} МАРКЕР: \"{marker_data.get('marker_text', '')[:80]}...\"\n"
                        report += f"      Вес балла: {marker_data.get('score_weight', 0)}\n"
                        report += f"      Сравнений: {marker_data.get('comparisons', 0)}\n"
                        report += f"      Найдено совпадений: {len(marker_data.get('matches', []))}\n"
                        report += f"      Ниже порога: {marker_data.get('below_threshold_count', 0)}\n"
                        report += f"      Отфильтровано по контексту: {marker_data.get('contextually_filtered_count', 0)}\n"
                        
                        # Показываем найденные совпадения для этого маркера
                        marker_matches = marker_data.get('matches', [])
                        if marker_matches:
                            report += f"      🎯 НАЙДЕННЫЕ СОВПАДЕНИЯ:\n"
                            for i, match in enumerate(marker_matches, 1):
                                report += f"         {i}. \"{match['found'][:120]}...\"\n"
                                report += f"            Сходство: {match['similarity']:.1%}, Балл: {match['score']:.2f}\n"

            # Примеры позитивных проявлений
            if ind_data['positive']['examples']:
                report += f"\n✅ ЛУЧШИЕ ПОЗИТИВНЫЕ ПРОЯВЛЕНИЯ:\n"
                for i, example in enumerate(ind_data['positive']['examples'], 1):
                    report += f"  {i}. НАЙДЕНО: \"{example['found'][:150]}...\"\n"
                    report += f"     МАРКЕР: \"{example['original'][:80]}...\"\n"
                    report += f"     СХОДСТВО: {example['similarity']:.1%}, БАЛЛ: {example['score']:.2f}\n"
                    report += f"     МЕТОД: {example['method']}\n\n"

            # Примеры негативных проявлений
            if ind_data['negative']['examples']:
                report += f"❌ НЕГАТИВНЫЕ ПРОЯВЛЕНИЯ:\n"
                for i, example in enumerate(ind_data['negative']['examples'], 1):
                    report += f"  {i}. НАЙДЕНО: \"{example['found'][:150]}...\"\n"
                    report += f"     МАРКЕР: \"{example['original'][:80]}...\"\n"
                    report += f"     СХОДСТВО: {example['similarity']:.1%}, БАЛЛ: -{example['score']:.2f}\n"
                    report += f"     МЕТОД: {example['method']}\n\n"

            # Рекомендации
            if ind_data['courses']:
                report += f"💡 РЕКОМЕНДАЦИИ ДЛЯ РАЗВИТИЯ:\n"
                for course in ind_data['courses']:
                    report += f"   - {course}\n"

            report += "\n" + "-" * 70 + "\n\n"

        report += "\n"

    return report 