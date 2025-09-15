import asyncio
import logging
import os
from typing import Dict, Tuple, List
import pandas as pd
from docx import Document
import aiohttp
import json
import uuid
from datetime import datetime
import sys
import os
import time
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from search_optimized import AsyncGigaChat, load_triggers, load_transcript, analyze_text_optimized, format_simple_report

class CompetencyAnalyzer:
    """Класс для анализа компетенций с интеграцией в Telegram бот"""
    
    def __init__(self):
        self.giga_chat = None
        self.cache = {}  # Кэш для уже проверенных пар
        self.stats = {
            'total_requests': 0,
            'cache_hits': 0,
            'api_errors': 0,
            'start_time': None,
            'end_time': None
        }
        
    async def initialize(self):
        """Инициализация GigaChat"""
        self.giga_chat = AsyncGigaChat()
        await self.giga_chat.initialize()
        
    async def close(self):
        """Закрытие соединения"""
        if self.giga_chat:
            await self.giga_chat.close()
            
    async def analyze_competencies(self, trans_file_path: str, triggers_file_path: str) -> Tuple[str, str, Dict]:
        """
        Анализирует компетенции и возвращает полный отчет, краткое резюме и данные анализа
        
        Args:
            trans_file_path: путь к файлу с текстом встречи
            triggers_file_path: путь к файлу с триггерами
            
        Returns:
            Tuple[str, str, Dict]: (полный отчет, краткое резюме, данные анализа)
        """
        try:
            self.stats['start_time'] = time.time()
            print("🔍 ДИАГНОСТИКА: Начинаем анализ компетенций...")
            
            # Загружаем файлы
            print(f"📁 Загружаем триггеры: {triggers_file_path}")
            triggers = load_triggers(triggers_file_path)
            print(f"✅ Триггеры загружены: {len(triggers)} компетенций")
            
            print(f"📁 Загружаем транскрипт: {trans_file_path}")
            full_text = load_transcript(trans_file_path)
            print(f"✅ Транскрипт загружен: {len(full_text)} символов")
            
            # 🔧 ИСПРАВЛЕНИЕ: Автоматически выбираем главного спикера
            print("🎯 ИСПРАВЛЕНО: Автоматически выбираем главного спикера (у кого больше реплик)")
            from search_optimized import filter_by_main_speaker
            text = filter_by_main_speaker(full_text)  # Автоматически выбираем главного спикера
            print(f"✅ Текст отфильтрован: {len(full_text)} -> {len(text)} символов")
            
            if len(text.strip()) == 0:
                print("❌ КРИТИЧЕСКАЯ ОШИБКА: Исходный текст ПУСТОЙ!")
                return "Ошибка: пустой файл", "Файл не содержит текста"
            logging.info(f"Анализ компетенций: {len(full_text)} -> {len(text)} символов")
            
            # Анализируем текст
            print("🤖 Запускаем analyze_text_optimized...")
            analysis = await analyze_text_optimized(text, triggers, self.giga_chat)
            print(f"✅ Анализ завершен: {len(analysis)} компетенций обработано")
            
            # Обновляем статистику из результатов анализа
            self.update_stats_from_analysis(analysis)
            
            # Формируем полный отчет (как в REPORT.txt)
            full_report = self._create_detailed_report(analysis, trans_file_path, triggers_file_path)
            
            # Создаем краткое резюме (оставляем как есть)
            summary = self._create_summary(analysis)
            
            self.stats['end_time'] = time.time()
            return full_report, summary, analysis
            
        except Exception as e:
            logging.error(f"Ошибка анализа компетенций: {e}")
            raise
    
    def get_similarity_score_cached(self, phrase: str, trigger: str) -> int:
        """Получает оценку сходства с кэшированием"""
        cache_key = (phrase, trigger)
        
        # Проверяем кэш
        if cache_key in self.cache:
            self.stats['cache_hits'] += 1
            return self.cache[cache_key]
        
        self.stats['total_requests'] += 1
        # Здесь будет вызов API, пока возвращаем 0
        return 0
    
    def update_stats_from_analysis(self, analysis: Dict):
        """Обновляет статистику из результатов анализа"""
        if '_detailed_stats' in analysis:
            stats = analysis['_detailed_stats']
            # Исправляем: берем реальные данные из GigaChat и кэша
            self.stats['total_requests'] = self.giga_chat.total_requests if hasattr(self.giga_chat, 'total_requests') else 0
            self.stats['cache_hits'] = stats.get('similarity_cache_hits', 0)
            self.stats['api_errors'] = 0  # Пока не отслеживаем ошибки API
    
    def print_statistics(self):
        """Выводит статистику работы анализатора"""
        duration = self.stats['end_time'] - self.stats['start_time'] if self.stats['end_time'] else 0
        
        print("=== СТАТИСТИКА РАБОТЫ ===")
        print(f"Всего запросов к API: {self.stats['total_requests']}")
        print(f"Попаданий в кэш: {self.stats['cache_hits']}")
        print(f"Ошибок API: {self.stats['api_errors']}")
        print(f"Время выполнения: {duration:.2f} секунд")
        
        if self.stats['total_requests'] > 0:
            cache_hit_rate = (self.stats['cache_hits'] / (self.stats['cache_hits'] + self.stats['total_requests'])) * 100
            print(f"Процент попаданий в кэш: {cache_hit_rate:.1f}%")
    
    def _generate_positive_alternative(self, negative_phrase: str, indicator: str) -> str:
        """Генерирует позитивную альтернативу для негативной фразы"""
        alternatives = {
            "Коммуникация": {
                "я не знаю": "я изучу этот вопрос",
                "я не понимаю": "давайте разберем подробнее",
                "это невозможно": "это сложная задача, но мы можем найти решение",
                "я не могу": "мне нужно больше времени на изучение",
                "это не моя проблема": "я помогу решить эту задачу",
                "я не хочу": "я готов обсудить альтернативы",
                "это глупо": "это интересная идея, давайте обсудим",
                "вы неправы": "у нас разные точки зрения, давайте обсудим",
                "это не работает": "давайте найдем другой подход",
                "я не согласен": "у меня есть другие соображения",
                "я не умею": "я научусь этому",
                "это не мое": "я готов попробовать",
                "я не хочу говорить": "я готов поделиться своими мыслями",
                "это бессмысленно": "давайте найдем смысл в этом",
                "я не хочу слушать": "я готов выслушать вашу точку зрения"
            },
            "Лидерство": {
                "я не могу решить": "я изучу все варианты и приму решение",
                "это не моя ответственность": "я возьму на себя эту задачу",
                "я не хочу руководить": "я готов взять на себя руководство",
                "пусть другие решают": "я возьму инициативу в свои руки",
                "я не знаю что делать": "я проанализирую ситуацию и определю план",
                "это слишком сложно": "это вызов, который мы преодолеем",
                "я не готов": "я подготовлюсь и буду готов",
                "пусть кто-то другой": "я готов взять на себя эту роль",
                "я не хочу принимать решения": "я готов взять ответственность за решение",
                "это не мое дело": "я возьму на себя эту задачу",
                "я не хочу командовать": "я готов координировать работу команды",
                "пусть сами разбираются": "я помогу команде найти решение"
            },
            "Адаптивность": {
                "я не хочу меняться": "я готов адаптироваться к новым условиям",
                "это не для меня": "я изучу новые возможности",
                "я привык по-другому": "я готов изучить новые подходы",
                "это слишком сложно": "я освою новые навыки",
                "я не понимаю зачем": "я изучу преимущества нового подхода",
                "это не работает": "я найду эффективные способы адаптации",
                "я не хочу учиться": "я готов освоить новые навыки",
                "это не мой стиль": "я готов попробовать новый подход",
                "я не хочу пробовать": "я готов экспериментировать",
                "это не подходит": "я найду способ адаптироваться"
            },
            "Решение проблем": {
                "я не знаю как решить": "я проанализирую проблему и найду решение",
                "это невозможно": "я найду альтернативные пути решения",
                "я не могу это исправить": "я изучу причины и найду способ исправления",
                "это не моя проблема": "я помогу решить эту проблему",
                "я не хочу этим заниматься": "я готов взять на себя решение этой задачи",
                "это не моя вина": "я помогу найти решение независимо от причин",
                "я не хочу разбираться": "я готов глубоко изучить проблему",
                "это не мое дело": "я возьму на себя решение этой задачи",
                "пусть кто-то другой решает": "я готов взять на себя решение"
            },
            "Работа в команде": {
                "я не хочу работать в команде": "я готов сотрудничать с командой",
                "я лучше работаю один": "я готов внести свой вклад в командную работу",
                "я не хочу делиться": "я готов поделиться своими идеями",
                "это не моя команда": "я готов стать частью команды",
                "я не хочу помогать": "я готов поддержать коллег",
                "пусть сами разбираются": "я готов помочь команде"
            },
            "Критическое мышление": {
                "я не хочу думать": "я готов проанализировать ситуацию",
                "это очевидно": "давайте рассмотрим это глубже",
                "я не хочу анализировать": "я готов детально изучить вопрос",
                "это не важно": "давайте разберем все аспекты",
                "я не хочу разбираться": "я готов глубоко изучить проблему"
            }
        }
        
        # Ищем подходящую альтернативу
        for comp, phrases in alternatives.items():
            if comp.lower() in indicator.lower():
                for neg_phrase, pos_phrase in phrases.items():
                    if neg_phrase.lower() in negative_phrase.lower():
                        return pos_phrase
        
        # Если не найдено конкретное соответствие, возвращаем общую альтернативу
        return f"вместо этого можно сказать более конструктивно"
            
    def _create_summary(self, analysis: Dict) -> str:
        """Создает краткое резюме по компетенциям"""
        summary = "📊 КРАТКОЕ РЕЗЮМЕ ПО КОМПЕТЕНЦИЯМ\n\n"
        
        competency_scores = {}
        
        # Собираем данные по компетенциям
        for comp, data in analysis.items():
            if comp == '_detailed_stats':
                continue
                
            # Подсчитываем средний балл по компетенции
            indicator_scores = []
            courses_for_comp = set()
            
            for indicator, ind_data in data["indicators"].items():
                indicator_scores.append(ind_data['score'])
                if ind_data['courses']:
                    courses_for_comp.update(ind_data['courses'])
            
            if indicator_scores:
                # Показываем сумму всех баллов без нормализации
                total_score = sum(indicator_scores)
                competency_scores[comp] = {
                    'score': total_score,
                    'courses': list(courses_for_comp),
                    'has_negative': any(ind_data['negative']['score'] > 0 for ind_data in data["indicators"].values())
                }
        
        # Сортируем компетенции по баллам
        sorted_competencies = sorted(competency_scores.items(), key=lambda x: x[1]['score'])
        
        for comp, data in sorted_competencies:
            score = data['score']
            courses = data['courses']
            has_negative = data['has_negative']
            
            # Определяем статус компетенции (адаптировано для сырых сумм)
            if score >= 30:
                status = "✅ Отлично развита"
                emoji = "🟢"
            elif score >= 15:
                status = "🟡 Требует внимания"
                emoji = "🟡"
            else:
                status = "❌ Требует развития"
                emoji = "🔴"
            
            # Исправляем отображение - убираем "/10" и показываем как "X баллов"
            summary += f"{emoji} **{comp}** - {score:.1f} баллов\n"
            summary += f"   {status}\n"
            
            # Показываем курсы только если есть негативные проявления
            if has_negative and courses:
                summary += f"   📚 **Рекомендуемые курсы:**\n"
                for course in courses[:3]:  # Показываем максимум 3 курса
                    summary += f"      • {course}\n"
                summary += "\n"
            elif score < 15 and courses:
                summary += f"   📚 **Рекомендуемые курсы:**\n"
                for course in courses[:3]:
                    summary += f"      • {course}\n"
                summary += "\n"
            else:
                summary += "\n"
            
            # Добавляем примеры негативных фраз и альтернатив
            if has_negative:
                summary += f"   💡 **Примеры улучшения коммуникации:**\n"
                negative_examples = []
                for indicator, ind_data in analysis[comp]["indicators"].items():
                    for example in ind_data['negative']['examples'][:2]:  # Берем максимум 2 примера
                        alternative = self._generate_positive_alternative(example['found'], indicator)
                        negative_examples.append(f"      • Вместо: \"{example['found'][:50]}...\"\n        Можно: \"{alternative}\"")
                
                # Показываем максимум 3 примера
                for example in negative_examples[:3]:
                    summary += f"{example}\n"
                summary += "\n"
        
        # Общие рекомендации
        low_score_comps = [comp for comp, data in competency_scores.items() if data['score'] < 15]
        if low_score_comps:
            summary += "💡 **ОБЩИЕ РЕКОМЕНДАЦИИ:**\n"
            summary += f"   • Обратите внимание на развитие: {', '.join(low_score_comps[:3])}\n"
            summary += "   • Рекомендуется пройти соответствующие курсы\n"
            summary += "   • Практикуйте навыки в повседневной работе\n\n"
        
        high_score_comps = [comp for comp, data in competency_scores.items() if data['score'] >= 30]
        if high_score_comps:
            summary += "🎉 **СИЛЬНЫЕ СТОРОНЫ:**\n"
            summary += f"   • Отлично развиты: {', '.join(high_score_comps[:3])}\n"
            summary += "   • Продолжайте поддерживать высокий уровень\n\n"
        
        return summary

    def _create_detailed_report(self, analysis: Dict, trans_file_path: str, triggers_file_path: str) -> str:
        """Создает детальный отчет в формате REPORT.txt"""
        report = "🎯 ДЕТАЛЬНЫЙ АНАЛИЗ КОМПЕТЕНЦИЙ\n\n"
        report += "=" * 80 + "\n"
        report += f"📁 Файл встречи: {trans_file_path}\n"
        report += f"📁 Файл триггеров: {triggers_file_path}\n"
        report += f"📅 Дата анализа: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        report += "=" * 80 + "\n\n"
        
        # Анализ компетенций
        for comp, data in analysis.items():
            if comp == '_detailed_stats':
                continue
            
            # Подсчет среднего балла по компетенции
            indicator_scores = []
            for indicator, ind_data in data["indicators"].items():
                indicator_scores.append(ind_data['score'])
            
            if indicator_scores:
                avg_score = sum(indicator_scores) / len(indicator_scores)
            else:
                avg_score = 0
            
            report += f"🏆 {comp} - средний балл {avg_score:.1f}\n"
            report += "=" * 80 + "\n\n"
            
            for indicator, ind_data in data["indicators"].items():
                report += f"📊 {indicator} - {ind_data['score']:.1f} балла\n"
                report += f"   Позитивных: {ind_data['positive']['score']:.1f}\n"
                report += f"   Негативных: {ind_data['negative']['score']:.1f}\n"
                
                # Показываем найденные совпадения
                if ind_data['positive']['examples']:
                    report += "   \n   ✅ НАЙДЕНО В ТЕКСТЕ (позитивное):\n"
                    for example in ind_data['positive']['examples']:
                        report += f"      • \"{example['found'][:200]}...\"\n"
                        report += f"        Похоже на: \"{example['original'][:100]}...\"\n"
                        report += f"        Балл: {example['score']:.1f}\n\n"
                
                if ind_data['negative']['examples']:
                    report += "   \n   ❌ НАЙДЕНО В ТЕКСТЕ (негативное):\n"
                    for example in ind_data['negative']['examples']:
                        report += f"      • \"{example['found'][:200]}...\"\n"
                        report += f"        Похоже на: \"{example['original'][:100]}...\"\n"
                        report += f"        Балл: -{example['score']:.1f}\n"
                        # Добавляем альтернативу
                        alternative = self._generate_positive_alternative(example['found'], indicator)
                        report += f"        💡 Мог бы сказать: \"{alternative}\"\n\n"
                
                # Рекомендации по курсам
                if ind_data['courses']:
                    report += "   💡 РЕКОМЕНДОВАННЫЕ КУРСЫ:\n"
                    for course in ind_data['courses']:
                        report += f"      • {course}\n"
                    if ind_data['negative']['score'] > 0:
                        report += f"      Обоснование: найден негативный триггер (балл: -{ind_data['negative']['score']:.1f})\n"
                    report += "\n"
                
                report += "-" * 70 + "\n\n"
            
            report += "\n"
        
        # Добавляем статистику обработки
        if '_detailed_stats' in analysis:
            stats = analysis['_detailed_stats']
            report += "�� СТАТИСТИКА ОБРАБОТКИ:\n"
            report += "=" * 80 + "\n"
            report += f"   Время обработки: {stats.get('processing_time', 0):.1f}с\n"
            report += f"   Всего сравнений: {stats.get('total_comparisons', 0)}\n"
            report += f"   Токенов использовано: {stats.get('tokens_used', 0)}\n"
            report += f"   Размер кэша: {stats.get('cache_size', 0)}\n"
            report += f"   Предложений обработано: {stats.get('sentences_processed', 0)}\n"
            report += "=" * 80 + "\n\n"
        
        return report
    
    def save_results_to_files(self, analysis: Dict, trans_file_path: str, triggers_file_path: str, output_dir: str = "results"):
        """Сохраняет результаты анализа в файлы"""
        os.makedirs(output_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Сохраняем детальный отчет
        report_file = os.path.join(output_dir, f"detailed_report_{timestamp}.txt")
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(self._create_detailed_report(analysis, trans_file_path, triggers_file_path))
        print(f"📄 Детальный отчет сохранен в {report_file}")
        
        # Сохраняем краткое резюме
        summary_file = os.path.join(output_dir, f"summary_{timestamp}.txt")
        with open(summary_file, 'w', encoding='utf-8') as f:
            f.write(self._create_summary(analysis))
        print(f"📄 Краткое резюме сохранено в {summary_file}")
        
        # Сохраняем статистику
        stats_file = os.path.join(output_dir, f"stats_{timestamp}.json")
        with open(stats_file, 'w', encoding='utf-8') as f:
            json.dump(self.stats, f, indent=2, ensure_ascii=False)
        print(f"📊 Статистика сохранена в {stats_file}")
    
    def create_csv_report(self, analysis: Dict, output_dir: str = "results"):
        """Создает CSV отчет с результатами анализа"""
        os.makedirs(output_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Создаем DataFrame для детальных результатов
        detailed_data = []
        summary_data = []
        
        for comp, data in analysis.items():
            if comp == '_detailed_stats':
                continue
                
            # Подсчитываем средний балл по компетенции
            indicator_scores = []
            for indicator, ind_data in data["indicators"].items():
                indicator_scores.append(ind_data['score'])
                
                # Добавляем детальные данные
                detailed_data.append({
                    'competency': comp,
                    'indicator': indicator,
                    'score': ind_data['score'],
                    'positive_score': ind_data['positive']['score'],
                    'negative_score': ind_data['negative']['score'],
                    'positive_examples_count': len(ind_data['positive']['examples']),
                    'negative_examples_count': len(ind_data['negative']['examples']),
                    'courses_count': len(ind_data['courses'])
                })
            
            if indicator_scores:
                avg_score = sum(indicator_scores) / len(indicator_scores)
                summary_data.append({
                    'competency': comp,
                    'avg_score': avg_score,
                    'indicators_count': len(indicator_scores),
                    'total_positive': sum(ind_data['positive']['score'] for ind_data in data["indicators"].values()),
                    'total_negative': sum(ind_data['negative']['score'] for ind_data in data["indicators"].values())
                })
        
        # Сохраняем детальный отчет
        if detailed_data:
            df_detailed = pd.DataFrame(detailed_data)
            detailed_file = os.path.join(output_dir, f"detailed_analysis_{timestamp}.csv")
            df_detailed.to_csv(detailed_file, index=False, encoding='utf-8-sig')
            print(f"📊 Детальный CSV отчет сохранен в {detailed_file}")
        
        # Сохраняем сводный отчет
        if summary_data:
            df_summary = pd.DataFrame(summary_data)
            summary_file = os.path.join(output_dir, f"summary_analysis_{timestamp}.csv")
            df_summary.to_csv(summary_file, index=False, encoding='utf-8-sig')
            print(f"📊 Сводный CSV отчет сохранен в {summary_file}")

# Функция для использования в Telegram боте
async def analyze_competencies_async(trans_file: str, triggers_file: str, save_files: bool = False) -> Tuple[str, str]:
    """
    Асинхронная функция для анализа компетенций
    
    Args:
        trans_file: путь к файлу с текстом встречи
        triggers_file: путь к файлу с триггерами
        save_files: сохранять ли результаты в файлы
        
    Returns:
        Tuple[str, str]: (полный отчет, краткое резюме)
    """
    analyzer = CompetencyAnalyzer()
    try:
        await analyzer.initialize()
        full_report, summary, analysis = await analyzer.analyze_competencies(trans_file, triggers_file)
        
        # Выводим статистику
        analyzer.print_statistics()
        
        # Сохраняем файлы если нужно
        if save_files:
            analyzer.save_results_to_files(analysis, trans_file, triggers_file)
            analyzer.create_csv_report(analysis)
        
        return full_report, summary
    finally:
        await analyzer.close() 