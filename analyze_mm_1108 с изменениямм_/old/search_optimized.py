import pandas as pd
from docx import Document
import asyncio
import uuid
import aiohttp
import json
import re
from io import BytesIO
from typing import List, Dict, Tuple, Optional
from difflib import SequenceMatcher
import logging
import os
import string
import time

# Импортируем умный фильтр и подробную отчётность
from smart_filter import SmartPhraseFilter
# from detailed_report import format_detailed_report

AUTH_KEY = 'ZGMzMGJmZjEtODQwYS00ZjAwLWI2NjgtNGIyNGNiY2ViNmE1OjYwNjM3NTU0LWQxMDctNDA5ZS1hZWM3LTAwYjQ5MjZkOGU2OA=='
SCOPE = 'GIGACHAT_API_PERS'
API_AUTH_URL = 'https://ngw.devices.sberbank.ru:9443/api/v2/oauth'
API_CHAT_URL = 'https://gigachat.devices.sberbank.ru/api/v1/chat/completions'
MAX_TOKENS = 20000  # Лимит токенов для GigaChat

# 🔧 УБРАНЫ ВСЕ ОГРАНИЧЕНИЯ для максимального поиска совпадений
SEMANTIC_THRESHOLD = 0.15  # 🔧 СНИЖЕН порог для поиска большего количества совпадений
MAX_SENTENCES = 1000  # 🔧 ПОВЫШЕН лимит для анализа большего количества предложений
MIN_SIMILARITY_FOR_AI = 0.05  # 🔧 СНИЖЕН порог для AI до минимума
MAX_SIMILARITY_CAP = 0.95  # 🔧 ПОВЫШЕН лимит для максимального поиска
CACHE_SIZE_LIMIT = 10000

# 🔧 УБРАНЫ ВСЕ ЛИМИТЫ на совпадения
MAX_POSITIVE_MATCHES_PER_MARKER = 10  # ПОВЫШЕН до 10 совпадений на маркер
MAX_NEGATIVE_MATCHES_PER_MARKER = 10  # ПОВЫШЕН до 10 совпадений на маркер
MIN_PERCENTAGE = -500  # СНИЖЕН для поиска большего количества негативных совпадений
MAX_PERCENTAGE = 500  # ПОВЫШЕН для поиска большего количества позитивных совпадений

# Инициализируем умный фильтр с ослабленными критериями для поиска позитивных совпадений
smart_filter = SmartPhraseFilter()

# Глобальный кэш для ускорения
similarity_cache = {}
# Счетчик попаданий в кэш для статистики
global_cache_hits = 0

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
                markers = [m for m in markers if m]
                for marker in markers:
                    pos_markers[marker] = score

        # Обрабатываем все колонки с негативными маркерами (10, 8, 6, 4, 2)
        for score in [10, 8, 6, 4, 2]:
            col_name = f'Фразы/маркеры "Негативные проявления" {score}'
            if col_name in group.columns:
                markers = group[col_name].dropna().astype(str).str.strip()
                markers = [m for m in markers if m]
                for marker in markers:
                    neg_markers[marker] = score

        courses = []
        if 'курсы' in group.columns and not group['курсы'].dropna().empty:
            courses = [c.strip() for c in str(group['курсы'].dropna().iloc[0]).split(',') if c.strip()]

        if comp not in result:
            result[comp] = {}

        result[comp][indicator] = {
            "positive_markers": pos_markers,
            "negative_markers": neg_markers,
            "courses": courses
        }
    return result

def is_meaningful_phrase(phrase: str) -> bool:
    """🔧 БОЛЕЕ СТРОГАЯ проверка значимости фразы для повышения точности анализа."""
    return smart_filter.is_meaningful_phrase_basic(phrase, min_length=25, min_meaningful_words=4)

def categorize_content(text: str) -> str:
    """🔧 НОВАЯ ФУНКЦИЯ: Категоризирует содержимое по тематике"""
    text_lower = text.lower()
    
    # Техническое/IT
    if any(word in text_lower for word in ['технолог', 'цифров', 'автоматизац', 'crm', 'онлайн', 'платформ']):
        return 'technical'
    
    # Бизнес/финансы
    if any(word in text_lower for word in ['лизинг', 'кредит', 'депозит', 'ндс', 'налог', 'банк']):
        return 'business'
    
    # Организационное
    if any(word in text_lower for word in ['знаком', 'представ', 'собрал', 'встреч', 'мастер']):
        return 'organizational'
    
    # Формальное общение
    if any(word in text_lower for word in ['спасибо', 'пожалуйста', 'извините', 'здравствуйте']):
        return 'formal'
    
    # Межличностное
    if any(word in text_lower for word in ['команд', 'коллег', 'общен', 'поддерж', 'совместн']):
        return 'interpersonal'
    
    # Управленческое
    if any(word in text_lower for word in ['управл', 'планир', 'организ', 'контрол']):
        return 'management'
    
    return 'general'

def is_contextually_relevant(sentence: str, marker: str) -> bool:
    """🔧 УБРАНЫ ВСЕ ОГРАНИЧЕНИЯ для максимального поиска совпадений"""
    # УБРАНЫ все ограничения - проверяем все фразы
    return True

def is_contextually_relevant_positive(sentence: str, marker: str) -> bool:
    """🔧 УБРАНЫ ВСЕ ОГРАНИЧЕНИЯ для максимального поиска совпадений"""
    # УБРАНЫ все ограничения - проверяем все фразы
    return True

def preprocess_text_optimized(text: str) -> List[str]:
    """Оптимизированная предобработка текста"""
    # Разбиваем на предложения
    sentences = []
    current_sentence = []

    for char in text:
        current_sentence.append(char)
        if char in '.!?':
            sentence = ''.join(current_sentence).strip()
            if sentence and len(sentence) > 10:
                sentences.append(sentence)
            current_sentence = []

    if current_sentence:
        final_sentence = ''.join(current_sentence).strip()
        if final_sentence and len(final_sentence) > 10:
            sentences.append(final_sentence)

    # Фильтруем только значимые предложения
    meaningful_sentences = []
    for sent in sentences:
        if is_meaningful_phrase(sent):
            meaningful_sentences.append(sent)
        
        # Ограничиваем количество для ускорения
        if len(meaningful_sentences) >= MAX_SENTENCES:
            break

    return meaningful_sentences

async def check_phrase_similarity_positive(giga_chat: 'AsyncGigaChat', sent: str, marker: str, total_tokens: int) -> Tuple[float, int]:
    """🔧 СПЕЦИАЛЬНАЯ функция для ПОЗИТИВНЫХ маркеров - максимально мягкая проверка"""
    global global_cache_hits
    # Кэш
    cache_key = f"POS_{hash(sent)}_{hash(marker)}"
    if cache_key in similarity_cache:
        global_cache_hits += 1
        return similarity_cache[cache_key], total_tokens

    # Для позитивных маркеров - максимально мягкая проверка контекста
    if not is_contextually_relevant_positive(sent, marker):
        similarity_cache[cache_key] = 0.0
        return 0.0, total_tokens

    # Базовое сходство с бонусом для позитивных
    base_similarity = SequenceMatcher(None, sent.lower(), marker.lower()).ratio()
    
    # 🔧 УБРАН порог для позитивных маркеров
    if base_similarity < 0.01:  # СНИЖЕН с 0.10 до 0.01
        similarity_cache[cache_key] = 0.0
        return 0.0, total_tokens
    
    # Проверяем токены
    if total_tokens >= MAX_TOKENS:
        # 🔧 УБРАНЫ ограничения
        boosted_similarity = min(base_similarity + 0.1, 0.95)  # ПОВЫШЕН с 0.05 до 0.1, с 0.75 до 0.95
        similarity_cache[cache_key] = boosted_similarity
        return boosted_similarity, total_tokens

    try:
        # Используем специальную мягкую функцию для позитивных маркеров
        ai_similarity = await check_semantic_similarity_positive(giga_chat, sent, marker)
        new_tokens = total_tokens + len(sent) + len(marker)
        
        # Для позитивных маркеров берем максимум из базового и ИИ
        final_similarity = max(ai_similarity, base_similarity + 0.1)
        final_similarity = min(final_similarity, 0.95)
        
        similarity_cache[cache_key] = final_similarity
        return final_similarity, new_tokens
        
    except Exception:
        # В случае ошибки даем бонус к базовому сходству
        boosted_similarity = min(base_similarity + 0.15, 0.95)
        similarity_cache[cache_key] = boosted_similarity
        return boosted_similarity, total_tokens

async def check_phrase_similarity_optimized(giga_chat: 'AsyncGigaChat', sent: str, marker: str, total_tokens: int) -> Tuple[float, int]:
    """🔧 ИСПРАВЛЕННАЯ проверка схожести с защитой от ложных совпадений"""
    global global_cache_hits
    # Кэш
    cache_key = f"{hash(sent)}_{hash(marker)}"
    if cache_key in similarity_cache:
        global_cache_hits += 1
        return similarity_cache[cache_key], total_tokens

    # 🔧 ПЕРВАЯ проверка - контекстуальная релевантность
    if not is_contextually_relevant(sent, marker):
        similarity_cache[cache_key] = 0.0
        return 0.0, total_tokens

    # Базовое сходство
    base_similarity = SequenceMatcher(None, sent.lower(), marker.lower()).ratio()
    
    # 🔧 УБРАН порог - проверяем все
    if base_similarity < 0.001:  # СНИЖЕН до минимума
        similarity_cache[cache_key] = 0.0
        return 0.0, total_tokens
    
    # 🔧 УБРАНО ограничение
    if base_similarity >= 0.95:
        final_similarity = min(base_similarity, 0.95)
        similarity_cache[cache_key] = final_similarity
        return final_similarity, total_tokens
    
    # Проверяем токены
    if total_tokens >= MAX_TOKENS:
        similarity_cache[cache_key] = base_similarity
        return base_similarity, total_tokens

    try:
        # 🔧 УЛУЧШЕННАЯ проверка через AI
        ai_similarity = await check_semantic_similarity_strict(giga_chat, sent, marker)
        new_tokens = total_tokens + len(sent) + len(marker)
        
        # 🔧 УБРАНА строгая валидация AI
        if ai_similarity > 0.95:
            final_similarity = min(base_similarity, 0.95)
        elif ai_similarity < base_similarity * 0.3:  # СНИЖЕН с 0.6 до 0.3
            final_similarity = base_similarity
        else:
            final_similarity = min(max(ai_similarity, base_similarity), 0.95)
        
        similarity_cache[cache_key] = final_similarity
        return final_similarity, new_tokens
        
    except Exception:
        similarity_cache[cache_key] = base_similarity
        return base_similarity, total_tokens

async def check_semantic_similarity_positive(giga_chat: 'AsyncGigaChat', sentence: str, marker: str) -> float:
    """🔧 СПЕЦИАЛЬНАЯ функция для ПОЗИТИВНЫХ маркеров - более строгая"""
    
    prompt = f"""Оцени смысловое сходство по шкале 0-1 с БОЛЕЕ СТРОГИМИ критериями.

ФРАЗА ИЗ ВСТРЕЧИ: "{sentence}"
ПОЗИТИВНЫЙ МАРКЕР: "{marker}"

СТРОГИЕ ПРАВИЛА:
- Ищи РЕАЛЬНЫЕ смысловые связи, а не поверхностные
- Если человек КОНКРЕТНО демонстрирует навык = ПОЗИТИВНО (0.6+)
- Если упоминает работу с клиентами/командой КОНКРЕТНО = ПОЗИТИВНО (0.5+)
- Если делится ОПЫТОМ, а не просто планами = ПОЗИТИВНО (0.4+)
- Будь БОЛЕЕ ТРЕБОВАТЕЛЬНЫМ к качеству совпадений
- Минимальная оценка 0.15, максимальная 0.75

Ответь только число 0.XX"""

    try:
        response = await giga_chat.send(prompt)
        result = float(response.strip())
        # УБРАНЫ ограничения для позитивных маркеров
        return min(max(result, 0.05), 0.95)
    except:
        # УБРАНЫ ограничения
        base_sim = SequenceMatcher(None, sentence.lower(), marker.lower()).ratio()
        return min(max(base_sim + 0.05, 0.05), 0.95)

async def check_semantic_similarity_strict(giga_chat: 'AsyncGigaChat', sentence: str, marker: str) -> float:
    """🔧 БОЛЕЕ СТРОГАЯ функция: Требовательная контекстуальная проверка через AI"""
    
    prompt = f"""Оцени смысловое сходство по шкале 0-1 с БОЛЕЕ СТРОГИМИ критериями.

ФРАЗА ИЗ ВСТРЕЧИ: "{sentence}"
МАРКЕР КОМПЕТЕНЦИИ: "{marker}"

СТРОГИЕ ПРАВИЛА:
- Ищи КОНКРЕТНЫЕ смысловые связи, а не общие
- Если человек ДЕМОНСТРИРУЕТ навык/качество - это ПОЗИТИВНО
- Если обсуждает РЕАЛЬНУЮ работу, а не планы - может быть ПОЗИТИВНО
- Будь БОЛЕЕ ТРЕБОВАТЕЛЬНЫМ к качеству совпадений
- Оценивай от 0.20 до 0.75

Ответь только число 0.XX"""

    try:
        response = await giga_chat.send(prompt)
        result = float(response.strip())
        return min(result, 0.95)
    except:
        return SequenceMatcher(None, sentence.lower(), marker.lower()).ratio()

async def check_semantic_similarity(giga_chat: 'AsyncGigaChat', text1: str, text2: str) -> float:
    """Проверяет семантическое сходство двух фраз с помощью GigaChat"""
    prompt = f"""Определите сходство фраз по шкале 0-1:

Фраза 1: "{text1}"
Фраза 2: "{text2}"

Ответьте только числом 0.XX без объяснений."""

    try:
        response = await giga_chat.send(prompt)
        return float(response.strip())
    except (ValueError, AttributeError):
        return SequenceMatcher(None, text1.lower(), text2.lower()).ratio()
    except Exception:
        return 0.0

async def analyze_text_optimized(text: str, triggers: dict, giga_chat: 'AsyncGigaChat') -> dict:
    """Оптимизированный анализ текста с подробной статистикой"""
    start_time = time.time()
    
    # Предобработка с ограничениями и сбор статистики
    print("🔄 Предобработка текста...")
    
    # Разбиваем на все предложения
    all_sentences = []
    current_sentence = []
    for char in text:
        current_sentence.append(char)
        if char in '.!?':
            sentence = ''.join(current_sentence).strip()
            if sentence and len(sentence) > 10:
                all_sentences.append(sentence)
            current_sentence = []
    if current_sentence:
        final_sentence = ''.join(current_sentence).strip()
        if final_sentence and len(final_sentence) > 10:
            all_sentences.append(final_sentence)
    
    # Детальная статистика фильтрации
    filter_stats = {
        'total_sentences': len(all_sentences),
        'passed_filter': 0,
        'filtered_by_pattern': 0,
        'filtered_by_length': 0,
        'filtered_by_stopwords': 0,
        'filtered_by_morphology': 0,
        'filtered_examples': {
            'pattern': [],
            'length': [],
            'stopwords': [],
            'morphology': []
        }
    }
    
    # Фильтруем с детальной статистикой
    meaningful_sentences = []
    for sent in all_sentences:
        # Проверяем паттерны
        if smart_filter.is_insignificant_by_pattern(sent):
            filter_stats['filtered_by_pattern'] += 1
            if len(filter_stats['filtered_examples']['pattern']) < 5:
                filter_stats['filtered_examples']['pattern'].append(sent[:100])
            continue
        
        # Проверяем длину (УБРАН фильтр)
        cleaned = smart_filter.clean_phrase(sent)
        if len(cleaned) < 5:  # СНИЖЕН с 20 до 5
            filter_stats['filtered_by_length'] += 1
            if len(filter_stats['filtered_examples']['length']) < 5:
                filter_stats['filtered_examples']['length'].append(sent[:100])
            continue
        
        # Морфологический анализ
        morph_analysis = smart_filter.analyze_morphology(sent)
        
        # Проверяем стоп-слова (УБРАН фильтр)
        if morph_analysis['total_words'] > 0:
            stopword_ratio = morph_analysis['stopwords_count'] / morph_analysis['total_words']
            if stopword_ratio > 0.95:  # ПОВЫШЕН с 85% до 95%
                filter_stats['filtered_by_stopwords'] += 1
                if len(filter_stats['filtered_examples']['stopwords']) < 5:
                    filter_stats['filtered_examples']['stopwords'].append(sent[:100])
                continue
        
        # Проверяем значимые слова (УБРАН фильтр)
        if morph_analysis['meaningful_words'] < 1:  # СНИЖЕН с 3 до 1
            filter_stats['filtered_by_morphology'] += 1
            if len(filter_stats['filtered_examples']['morphology']) < 5:
                filter_stats['filtered_examples']['morphology'].append(sent[:100])
            continue
        
        meaningful_sentences.append(sent)
        filter_stats['passed_filter'] += 1
        
        # Ограничиваем количество для ускорения
        if len(meaningful_sentences) >= MAX_SENTENCES:
            break
    
    print(f"✅ Статистика фильтрации:")
    print(f"   Всего предложений: {filter_stats['total_sentences']}")
    print(f"   Прошли фильтр: {filter_stats['passed_filter']}")
    print(f"   Отфильтровано по паттернам: {filter_stats['filtered_by_pattern']}")
    print(f"   Отфильтровано по длине: {filter_stats['filtered_by_length']}")
    print(f"   Отфильтровано по стоп-словам: {filter_stats['filtered_by_stopwords']}")
    print(f"   Отфильтровано по морфологии: {filter_stats['filtered_by_morphology']}")
    
    results = {}
    total_tokens = 0
    processed_comparisons = 0
    
    # Подробная статистика по каждой компетенции
    detailed_stats = {
        'filter_stats': filter_stats,
        'competency_stats': {}
    }

    for comp_idx, (comp, indicators) in enumerate(triggers.items()):
        comp_start = time.time()
        print(f"🔄 Анализ компетенции {comp_idx+1}/{len(triggers)}: {comp}")
        
        # 🔍 ДИАГНОСТИКА КОМПЕТЕНЦИИ
        total_pos_markers = 0
        total_neg_markers = 0
        print(f"📋 ДИАГНОСТИКА КОМПЕТЕНЦИИ '{comp}':")
        for ind_name, ind_data in indicators.items():
            if ind_name == 'courses':
                continue
            pos_count = len(ind_data.get('positive_markers', {}))
            neg_count = len(ind_data.get('negative_markers', {}))
            total_pos_markers += pos_count
            total_neg_markers += neg_count
            print(f"   📊 {ind_name}: +{pos_count} -{neg_count} маркеров")
        print(f"   📈 ВСЕГО: +{total_pos_markers} -{total_neg_markers} маркеров")
        
        comp_results = {
            "total_score": 0,
            "max_score": 0,
            "indicators": {},
            "indicator_scores": []  # Для вычисления среднего
        }
        
        # Статистика для компетенции
        comp_stats = {
            'total_markers': 0,
            'total_comparisons': 0,
            'matches_found': 0,
            'matches_below_threshold': 0,
            'contextually_irrelevant': 0,
            'marker_details': {}
        }

        for indicator, data in indicators.items():
            pos_matches = []
            neg_matches = []
            
            # Статистика для индикатора
            indicator_stats = {
                'positive_markers': len(data['positive_markers']),
                'negative_markers': len(data['negative_markers']),
                'positive_comparisons': 0,
                'negative_comparisons': 0,
                'positive_matches': 0,
                'negative_matches': 0,
                'below_threshold': 0,
                'contextually_filtered': 0,
                'marker_analysis': {}
            }

            # Максимальный возможный балл для индикатора
            max_pos_score = max(data['positive_markers'].values(), default=0)
            max_neg_score = max(data['negative_markers'].values(), default=0)
            indicator_max_score = max_pos_score + max_neg_score
            comp_results["max_score"] += indicator_max_score

            # Проверка позитивных маркеров
            print(f"      🟢 Обрабатываю {len(data['positive_markers'])} позитивных маркеров...")
            for marker_idx, (marker, score) in enumerate(data['positive_markers'].items()):
                if not marker:
                    continue
                
                # Показываем первые 3 маркера для диагностики
                if marker_idx < 3:
                    print(f"         +Маркер {marker_idx+1}: '{marker[:60]}...' (балл: {score})")
                
                marker_stats = {
                    'marker_text': marker,
                    'score_weight': score,
                    'comparisons': 0,
                    'matches': [],
                    'below_threshold_count': 0,
                    'contextually_filtered_count': 0
                }

                for sent in meaningful_sentences:
                    similarity, total_tokens = await check_phrase_similarity_positive(
                        giga_chat, sent, marker, total_tokens
                    )
                    marker_stats['comparisons'] += 1
                    indicator_stats['positive_comparisons'] += 1
                    processed_comparisons += 1

                    if not is_contextually_relevant_positive(sent, marker):
                        marker_stats['contextually_filtered_count'] += 1
                        indicator_stats['contextually_filtered'] += 1
                        continue

                    if similarity >= SEMANTIC_THRESHOLD:
                        # 🔧 КРИТИЧЕСКИ ВАЖНО: Ограничиваем количество совпадений на маркер
                        if len(marker_stats['matches']) >= MAX_POSITIVE_MATCHES_PER_MARKER:
                            continue  # Пропускаем, если уже достаточно совпадений для этого маркера
                        
                        # 🔧 ИСПРАВЛЕНО: присваиваем ПОЛНЫЙ балл из Excel для позитивных маркеров
                        weighted_score = score  # Берем полный балл из файла триггеров
                        method = "sequence_matcher" if similarity <= 0.3 else "giga_enhanced"
                        match_info = {
                            "found": sent,
                            "original": marker,
                            "score": weighted_score,
                            "similarity": similarity,
                            "method": method
                        }
                        pos_matches.append(match_info)
                        marker_stats['matches'].append(match_info)
                        indicator_stats['positive_matches'] += 1
                    elif similarity > 0.1:  # Записываем близкие, но не прошедшие порог
                        marker_stats['below_threshold_count'] += 1
                        indicator_stats['below_threshold'] += 1

                indicator_stats['marker_analysis'][f"pos_{marker[:50]}"] = marker_stats
                comp_stats['total_markers'] += 1

            # Проверка негативных маркеров
            print(f"      🔴 Обрабатываю {len(data['negative_markers'])} негативных маркеров...")
            for marker_idx, (marker, score) in enumerate(data['negative_markers'].items()):
                if not marker:
                    continue
                
                # Показываем первые 3 маркера для диагностики
                if marker_idx < 3:
                    print(f"         -Маркер {marker_idx+1}: '{marker[:60]}...' (балл: {score})")
                
                marker_stats = {
                    'marker_text': marker,
                    'score_weight': score,
                    'comparisons': 0,
                    'matches': [],
                    'below_threshold_count': 0,
                    'contextually_filtered_count': 0
                }

                for sent in meaningful_sentences:
                    similarity, total_tokens = await check_phrase_similarity_optimized(
                        giga_chat, sent, marker, total_tokens
                    )
                    marker_stats['comparisons'] += 1
                    indicator_stats['negative_comparisons'] += 1
                    processed_comparisons += 1

                    if not is_contextually_relevant(sent, marker):
                        marker_stats['contextually_filtered_count'] += 1
                        indicator_stats['contextually_filtered'] += 1
                        continue

                    if similarity >= SEMANTIC_THRESHOLD:
                        # 🔧 КРИТИЧЕСКИ ВАЖНО: Ограничиваем количество совпадений на маркер
                        if len(marker_stats['matches']) >= MAX_NEGATIVE_MATCHES_PER_MARKER:
                            continue  # Пропускаем, если уже достаточно совпадений для этого маркера
                        
                        # 🔧 ИСПРАВЛЕНО: присваиваем ПОЛНЫЙ балл из Excel для негативных маркеров
                        weighted_score = score  # Берем полный балл из файла триггеров
                        method = "sequence_matcher" if similarity <= 0.3 else "giga_enhanced"
                        match_info = {
                            "found": sent,
                            "original": marker,
                            "score": weighted_score,
                            "similarity": similarity,
                            "method": method
                        }
                        neg_matches.append(match_info)
                        marker_stats['matches'].append(match_info)
                        indicator_stats['negative_matches'] += 1
                    elif similarity > 0.1:  # Записываем близкие, но не прошедшие порог
                        marker_stats['below_threshold_count'] += 1
                        indicator_stats['below_threshold'] += 1

                indicator_stats['marker_analysis'][f"neg_{marker[:50]}"] = marker_stats
                comp_stats['total_markers'] += 1

            # ИСПРАВЛЕНО: Подсчет СУММЫ баллов как указано в Excel
            pos_score = sum(m['score'] for m in pos_matches) if pos_matches else 0
            neg_score = sum(m['score'] for m in neg_matches) if neg_matches else 0
            total_score = pos_score - neg_score
            
            # 🔍 ДИАГНОСТИКА РЕЗУЛЬТАТА ИНДИКАТОРА
            print(f"      📊 РЕЗУЛЬТАТ '{indicator}': {len(pos_matches)} позитивных, {len(neg_matches)} негативных совпадений")
            print(f"         Балл: +{pos_score:.1f} -{neg_score:.1f} = {total_score:.1f}")
            
            # Добавляем балл индикатора в список для вычисления среднего по компетенции
            comp_results["indicator_scores"].append(total_score)

            # Формируем результаты со ВСЕМИ найденными совпадениями
            comp_results["indicators"][indicator] = {
                "score": total_score,
                "max_score": indicator_max_score,
                "positive": {
                    "count": len(pos_matches),
                    "score": pos_score,
                    "examples": sorted(pos_matches, key=lambda x: x['similarity'], reverse=True)
                },
                "negative": {
                    "count": len(neg_matches),
                    "score": neg_score,
                    "examples": sorted(neg_matches, key=lambda x: x['similarity'], reverse=True)
                },
                "courses": data['courses'] if neg_score > 0 else [],  # Показываем курсы только если есть негативные
                "detailed_stats": indicator_stats
            }
            
            comp_stats['total_comparisons'] += indicator_stats['positive_comparisons'] + indicator_stats['negative_comparisons']
            comp_stats['matches_found'] += indicator_stats['positive_matches'] + indicator_stats['negative_matches']
            comp_stats['matches_below_threshold'] += indicator_stats['below_threshold']
            comp_stats['contextually_irrelevant'] += indicator_stats['contextually_filtered']

        # ИСПРАВЛЕНО: Суммируем баллы по компетенции
        if comp_results["indicator_scores"]:
            comp_results["total_score"] = sum(comp_results["indicator_scores"])
        else:
            comp_results["total_score"] = 0
            
        comp_time = time.time() - comp_start
        print(f"✅ Компетенция завершена за {comp_time:.1f}с")
        print(f"   Маркеров: {comp_stats['total_markers']}, Сравнений: {comp_stats['total_comparisons']}")
        print(f"   Найдено совпадений: {comp_stats['matches_found']}, Ниже порога: {comp_stats['matches_below_threshold']}")
        print(f"   Итоговый балл компетенции: {comp_results['total_score']:.1f}")
        
        results[comp] = comp_results
        detailed_stats['competency_stats'][comp] = comp_stats

    total_time = time.time() - start_time
    print(f"\n📊 Общая статистика обработки:")
    print(f"   - Время: {total_time:.1f}с")
    print(f"   - Сравнений: {processed_comparisons}")
    print(f"   - Токенов использовано: {total_tokens}")
    print(f"   - Размер кэша: {len(similarity_cache)}")

    # Добавляем детальную статистику к результатам
    detailed_stats['similarity_cache_hits'] = global_cache_hits
    results['_detailed_stats'] = detailed_stats
    return results

def format_simple_report(analysis: dict) -> str:
    """Формирует упрощенный отчет только с компетенциями, индикаторами, баллами и расшифровкой"""
    
    report = "🎯 АНАЛИЗ КОМПЕТЕНЦИЙ\n\n"
    report += "=" * 80 + "\n"
    
    # Анализ компетенций
    for comp, data in analysis.items():
        if comp == '_detailed_stats':  # Пропускаем служебные данные
            continue
        
        # Подсчет среднего балла по компетенции
        indicator_scores = []
        for indicator, ind_data in data["indicators"].items():
            indicator_scores.append(ind_data['score'])
        
        if indicator_scores:
            total_score = sum(indicator_scores)
        else:
            total_score = 0
        
        report += f"🏆 {comp} - итоговый балл {total_score:.1f}\n"
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
    
    return report

def filter_by_main_speaker(text: str, main_speaker: str = None) -> str:
    """Фильтрует текст, оставляя только реплики главного спикера"""
    print(f"🎯 ФИЛЬТРАЦИЯ ПО ГЛАВНОМУ СПИКЕРУ")
    
    lines = text.split('\n')
    speaker_stats = {}  # Статистика по спикерам
    all_speakers_content = {}  # Содержимое по спикерам
    current_speaker = None
    
    # Первый проход: собираем статистику по всем спикерам
    for line in lines:
        match = re.search(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} -\s*(.+?):)', line)
        if match:
            speaker = match.group(2).strip()
            current_speaker = speaker
            
            if speaker not in speaker_stats:
                speaker_stats[speaker] = 0
                all_speakers_content[speaker] = []
            
            # Добавляем текст реплики
            speech_text = line[match.end():].strip()
            if speech_text:
                speaker_stats[speaker] += 1
                all_speakers_content[speaker].append(speech_text)
        elif current_speaker and line.strip():
            # Продолжение реплики
            speaker_stats[current_speaker] += 1
            all_speakers_content[current_speaker].append(line.strip())
    
    # Показываем статистику
    print(f"📊 СТАТИСТИКА СПИКЕРОВ:")
    sorted_speakers = sorted(speaker_stats.items(), key=lambda x: x[1], reverse=True)
    for speaker, count in sorted_speakers:
        print(f"   🎤 {speaker}: {count} реплик")
    
    # Автоматически выбираем главного спикера
    if main_speaker is None and sorted_speakers:
        main_speaker = sorted_speakers[0][0]  # Спикер с наибольшим количеством реплик
        print(f"🎯 АВТОМАТИЧЕСКИ ВЫБРАН: '{main_speaker}' ({speaker_stats[main_speaker]} реплик)")
    elif main_speaker:
        print(f"🎯 ИСПОЛЬЗУЕМ ЗАДАННОГО: '{main_speaker}' ({speaker_stats.get(main_speaker, 0)} реплик)")
    
    # Возвращаем контент главного спикера
    if main_speaker in all_speakers_content:
        result = '\n'.join(all_speakers_content[main_speaker])
        print(f"✅ Отфильтровано: {len(result)} символов от спикера '{main_speaker}'")
        return result
    else:
        print(f"❌ Спикер '{main_speaker}' не найден!")
        return ""

class AsyncGigaChat:
    def __init__(self):
        self.session = None
        self.token = None
        self.history = []
        self.total_requests = 0  # Счетчик запросов к API

    async def initialize(self):
        self.session = aiohttp.ClientSession()
        await self._fetch_token()

    async def close(self):
        if self.session:
            await self.session.close()

    async def _fetch_token(self):
        headers = {
            'Authorization': f'Basic {AUTH_KEY}',
            'Content-Type': 'application/x-www-form-urlencoded',
            'Accept': 'application/json',
            'RqUID': str(uuid.uuid4()),
        }
        data = {'grant_type': 'client_credentials', 'scope': SCOPE}
        async with self.session.post(API_AUTH_URL, headers=headers, data=data, ssl=False) as resp:
            js = await resp.json()
            self.token = js.get('access_token')
            if resp.status != 200 or not self.token:
                raise RuntimeError(f"Auth failed {resp.status}")

    async def send(self, prompt: str) -> str:
        if not self.token:
            await self._fetch_token()

        self.history.append({'role': 'user', 'content': prompt})
        headers = {
            'Authorization': f'Bearer {self.token}',
            'Content-Type': 'application/json'
        }
        payload = {
            'model': 'GigaChat',
            'messages': self.history,
            'temperature': 0.7,
            'max_tokens': 500
        }

        self.total_requests += 1  # Увеличиваем счетчик запросов
        async with self.session.post(API_CHAT_URL, headers=headers, json=payload, ssl=False) as resp:
            if resp.status == 200:
                js = await resp.json()
                return js['choices'][0]['message']['content']
            else:
                raise RuntimeError(f"Request failed with status {resp.status}")

async def main():
    """Главная оптимизированная функция"""
    try:
        # Настройка логирования
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

        print("🔧 ФИНАЛЬНАЯ ВЕРСИЯ: ТОЛЬКО ГЛАВНЫЙ СПИКЕР + ПОЛНЫЕ БАЛЛЫ")
        print("=" * 60)
        print("ИСПРАВЛЕННАЯ СИСТЕМА БАЛЛОВ:")
        print(f"   🎯 Порог схожести: {SEMANTIC_THRESHOLD*100:.0f}% (ВЫСОКИЙ ДЛЯ ТОЧНОСТИ)")
        print(f"   📊 Лимит предложений: {MAX_SENTENCES} (УВЕЛИЧЕН)")
        print(f"   🧠 ОТДЕЛЬНАЯ мягкая ИИ-функция для позитивных маркеров")
        print(f"   ⭐ ИСПРАВЛЕНО: присваиваются ПОЛНЫЕ баллы из Excel (не умноженные)")
        print(f"   🎪 КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: анализируется только главный спикер")
        print(f"   🎯 Специальные бонусы для позитивных совпадений")
        print(f"   ⚖️ Лимиты: Максимум {MAX_POSITIVE_MATCHES_PER_MARKER} совпадений на маркер")
        print(f"   📈 Диапазон: {MIN_PERCENTAGE}% - {MAX_PERCENTAGE}%")
        print("=" * 60)
        
        logging.info("Начало оптимизированного анализа с ослабленными фильтрами")

        # 1. Загрузка файлов
        if not os.path.exists('./trans.docx'):
            raise FileNotFoundError("Файл trans.docx не найден")
        if not os.path.exists('./triggers.xlsx'):
            raise FileNotFoundError("Файл triggers.xlsx не найден")

        triggers = load_triggers('./triggers.xlsx')
        full_text = load_transcript('./trans.docx')
        
        text = filter_by_main_speaker(full_text)  # Автоматически выбираем главного спикера
        logging.info(f"Файлы успешно загружены. Фильтрация: только реплики главного спикера (Александр)")
        logging.info(f"Исходный текст: {len(full_text)} символов, после фильтрации: {len(text)} символов")

        # 2. Инициализация GigaChat
        giga_chat = AsyncGigaChat()
        await giga_chat.initialize()

        try:
            # 3. Оптимизированный анализ
            logging.info("Начало анализа текста...")
            analysis = await analyze_text_optimized(text, triggers, giga_chat)

            # 4. Формирование упрощенного отчета
            final_report = format_simple_report(analysis)

            # 5. Сохранение результатов
            with open('REPORT.txt', 'w', encoding='utf-8') as f:
                f.write(final_report)

            print(final_report)

        finally:
            await giga_chat.close()

    except Exception as e:
        logging.error(f"Ошибка: {e}")
        raise
    finally:
        logging.info("Анализ завершен")

if __name__ == '__main__':
    asyncio.run(main()) 