import asyncio
import logging
import os
from typing import Dict, Tuple
import pandas as pd
from docx import Document
import aiohttp
import json
import uuid
from datetime import datetime
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from search_optimized import AsyncGigaChat, load_triggers, load_transcript, filter_by_main_speaker, analyze_text_optimized, format_simple_report

class CompetencyAnalyzer:
    """Класс для анализа компетенций с интеграцией в Telegram бот"""
    
    def __init__(self):
        self.giga_chat = None
        
    async def initialize(self):
        """Инициализация GigaChat"""
        self.giga_chat = AsyncGigaChat()
        await self.giga_chat.initialize()
        
    async def close(self):
        """Закрытие соединения"""
        if self.giga_chat:
            await self.giga_chat.close()
            
    async def analyze_competencies(self, trans_file_path: str, triggers_file_path: str) -> Tuple[str, str]:
        """
        Анализирует компетенции и возвращает полный отчет и краткое резюме
        
        Args:
            trans_file_path: путь к файлу с текстом встречи
            triggers_file_path: путь к файлу с триггерами
            
        Returns:
            Tuple[str, str]: (полный отчет, краткое резюме)
        """
        try:
            # Загружаем файлы
            triggers = load_triggers(triggers_file_path)
            full_text = load_transcript(trans_file_path)
            
            # Фильтруем только главного спикера
            text = filter_by_main_speaker(full_text, "Александр")
            
            logging.info(f"Анализ компетенций: {len(full_text)} -> {len(text)} символов")
            
            # Анализируем текст
            analysis = await analyze_text_optimized(text, triggers, self.giga_chat)
            
            # Формируем полный отчет (как в REPORT.txt)
            full_report = self._create_detailed_report(analysis, trans_file_path, triggers_file_path)
            
            # Создаем краткое резюме (оставляем как есть)
            summary = self._create_summary(analysis)
            
            return full_report, summary
            
        except Exception as e:
            logging.error(f"Ошибка анализа компетенций: {e}")
            raise
            
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
                avg_score = sum(indicator_scores) / len(indicator_scores)
                competency_scores[comp] = {
                    'score': avg_score,
                    'courses': list(courses_for_comp),
                    'has_negative': any(ind_data['negative']['score'] > 0 for ind_data in data["indicators"].values())
                }
        
        # Сортируем компетенции по баллам
        sorted_competencies = sorted(competency_scores.items(), key=lambda x: x[1]['score'])
        
        for comp, data in sorted_competencies:
            score = data['score']
            courses = data['courses']
            has_negative = data['has_negative']
            
            # Определяем статус компетенции
            if score >= 8:
                status = "✅ Отлично развита"
                emoji = "🟢"
            elif score >= 6:
                status = "🟡 Требует внимания"
                emoji = "🟡"
            else:
                status = "❌ Требует развития"
                emoji = "🔴"
            
            summary += f"{emoji} **{comp}** - {score:.1f}/10 баллов\n"
            summary += f"   {status}\n"
            
            # Показываем курсы только если есть негативные проявления
            if has_negative and courses:
                summary += f"   📚 **Рекомендуемые курсы:**\n"
                for course in courses[:3]:  # Показываем максимум 3 курса
                    summary += f"      • {course}\n"
                summary += "\n"
            elif score < 6 and courses:
                summary += f"   📚 **Рекомендуемые курсы:**\n"
                for course in courses[:3]:
                    summary += f"      • {course}\n"
                summary += "\n"
            else:
                summary += "\n"
        
        # Общие рекомендации
        low_score_comps = [comp for comp, data in competency_scores.items() if data['score'] < 6]
        if low_score_comps:
            summary += "💡 **ОБЩИЕ РЕКОМЕНДАЦИИ:**\n"
            summary += f"   • Обратите внимание на развитие: {', '.join(low_score_comps[:3])}\n"
            summary += "   • Рекомендуется пройти соответствующие курсы\n"
            summary += "   • Практикуйте навыки в повседневной работе\n\n"
        
        high_score_comps = [comp for comp, data in competency_scores.items() if data['score'] >= 8]
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
                        report += f"        Балл: -{example['score']:.1f}\n\n"
                
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
            report += "📊 СТАТИСТИКА ОБРАБОТКИ:\n"
            report += "=" * 80 + "\n"
            report += f"   Время обработки: {stats.get('processing_time', 0):.1f}с\n"
            report += f"   Всего сравнений: {stats.get('total_comparisons', 0)}\n"
            report += f"   Токенов использовано: {stats.get('tokens_used', 0)}\n"
            report += f"   Размер кэша: {stats.get('cache_size', 0)}\n"
            report += f"   Предложений обработано: {stats.get('sentences_processed', 0)}\n"
            report += "=" * 80 + "\n\n"
        
        return report

# Функция для использования в Telegram боте
async def analyze_competencies_async(trans_file: str, triggers_file: str) -> Tuple[str, str]:
    """
    Асинхронная функция для анализа компетенций
    
    Args:
        trans_file: путь к файлу с текстом встречи
        triggers_file: путь к файлу с триггерами
        
    Returns:
        Tuple[str, str]: (полный отчет, краткое резюме)
    """
    analyzer = CompetencyAnalyzer()
    try:
        await analyzer.initialize()
        return await analyzer.analyze_competencies(trans_file, triggers_file)
    finally:
        await analyzer.close() 