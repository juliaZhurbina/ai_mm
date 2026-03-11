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

# КАРДИНАЛЬНО ИСПРАВЛЕННЫЕ настройки
SEMANTIC_THRESHOLD = 0.12  # 🔧 ЕЩЕ СНИЖЕН порог с 15% до 12% для лучшего поиска негативных совпадений
MAX_SENTENCES = 500  # 🔧 УВЕЛИЧЕН лимит с 200 до 500 предложений
MIN_SIMILARITY_FOR_AI = 0.08  # 🔧 ЕЩЕ СНИЖЕН порог для AI с 10% до 8% для поиска негативных маркеров
MAX_SIMILARITY_CAP = 0.85  # 🔧 ЕЩЕ УВЕЛИЧЕН лимит с 75% до 85%
CACHE_SIZE_LIMIT = 1000

# 🔧 МАКСИМАЛЬНО ОСЛАБЛЕННЫЕ ограничения для нахождения позитивных совпадений
MAX_POSITIVE_MATCHES = 10  # УВЕЛИЧЕН с 5 до 10 позитивных совпадений на индикатор
MAX_NEGATIVE_MATCHES = 8  # УВЕЛИЧЕН с 5 до 8 негативных совпадений на индикатор
MIN_PERCENTAGE = -200  # СНИЖЕН с -100% до -200%
MAX_PERCENTAGE = 300  # УВЕЛИЧЕН с 200% до 300%

# Инициализируем умный фильтр с ослабленными критериями для поиска позитивных совпадений
smart_filter = SmartPhraseFilter()

# Глобальный кэш для ускорения
similarity_cache = {}

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
    logging.info(result)
    return result

def is_meaningful_phrase(phrase: str) -> bool:
    """Умная проверка значимости фразы с ОСЛАБЛЕННЫМИ критериями для поиска позитивных совпадений."""
    return smart_filter.is_meaningful_phrase_basic(phrase, min_length=20, min_meaningful_words=3)

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
    """🔧 ОСЛАБЛЕННАЯ ФУНКЦИЯ: Более мягкая проверка контекстуальной релевантности для поиска негативных маркеров"""
    sent_category = categorize_content(sentence)
    marker_category = categorize_content(marker)
    
    # 🔧 ОСЛАБЛЕННЫЕ ПРАВИЛА: разрешаем больше совпадений для поиска негативных маркеров
    
    # Блокируем только явно неподходящие короткие формальные фразы
    if len(sentence) < 20 and sent_category == 'formal':
        return False
    
    # Блокируем только очень короткие организационные фразы
    if len(sentence) < 25 and sent_category == 'organizational':
        return False
    
    # Все остальные совпадения разрешаем для поиска негативных маркеров
    return True

def is_contextually_relevant_positive(sentence: str, marker: str) -> bool:
    """🔧 МАКСИМАЛЬНО ОСЛАБЛЕННАЯ проверка для ПОЗИТИВНЫХ маркеров - почти все разрешено"""
    sent_category = categorize_content(sentence)
    marker_category = categorize_content(marker)
    
    # Для позитивных маркеров разрешаем почти все
    # Блокируем только явно неподходящие короткие формальные фразы
    if len(sentence) < 30 and sent_category == 'formal':
        return False
    
    # Все остальное разрешаем для позитивных совпадений
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
    # Кэш
    cache_key = f"POS_{hash(sent)}_{hash(marker)}"
    if cache_key in similarity_cache:
        return similarity_cache[cache_key], total_tokens

    # Для позитивных маркеров - максимально мягкая проверка контекста
    if not is_contextually_relevant_positive(sent, marker):
        similarity_cache[cache_key] = 0.0
        return 0.0, total_tokens

    # Базовое сходство с бонусом для позитивных
    base_similarity = SequenceMatcher(None, sent.lower(), marker.lower()).ratio()
    
    # Для позитивных маркеров снижаем порог еще больше
    if base_similarity < 0.05:  # Очень низкий порог
        similarity_cache[cache_key] = 0.0
        return 0.0, total_tokens
    
    # Проверяем токены
    if total_tokens >= MAX_TOKENS:
        # Для позитивных даем бонус к базовому сходству
        boosted_similarity = min(base_similarity + 0.1, 0.8)
        similarity_cache[cache_key] = boosted_similarity
        return boosted_similarity, total_tokens

    try:
        # Используем специальную мягкую функцию для позитивных маркеров
        ai_similarity = await check_semantic_similarity_positive(giga_chat, sent, marker)
        new_tokens = total_tokens + len(sent) + len(marker)
        
        # Для позитивных маркеров берем максимум из базового и ИИ
        final_similarity = max(ai_similarity, base_similarity + 0.05)
        final_similarity = min(final_similarity, 0.8)
        
        similarity_cache[cache_key] = final_similarity
        return final_similarity, new_tokens
        
    except Exception:
        # В случае ошибки даем бонус к базовому сходству
        boosted_similarity = min(base_similarity + 0.1, 0.8)
        similarity_cache[cache_key] = boosted_similarity
        return boosted_similarity, total_tokens

async def check_phrase_similarity_optimized(giga_chat: 'AsyncGigaChat', sent: str, marker: str, total_tokens: int) -> Tuple[float, int]:
    """🔧 ОСЛАБЛЕННАЯ проверка схожести для поиска негативных маркеров"""
    # Кэш
    cache_key = f"{hash(sent)}_{hash(marker)}"
    if cache_key in similarity_cache:
        return similarity_cache[cache_key], total_tokens

    # 🔧 ОСЛАБЛЕННАЯ проверка - контекстуальная релевантность
    if not is_contextually_relevant(sent, marker):
        similarity_cache[cache_key] = 0.0
        return 0.0, total_tokens

    # Базовое сходство
    base_similarity = SequenceMatcher(None, sent.lower(), marker.lower()).ratio()
    
    # 🔧 ОСЛАБЛЕННЫЙ порог для негативных маркеров
    if base_similarity < 0.05:  # Снижен с MIN_SIMILARITY_FOR_AI до 0.05
        similarity_cache[cache_key] = 0.0
        return 0.0, total_tokens
    
    # 🔧 Если высокое - ограничиваем
    if base_similarity >= MAX_SIMILARITY_CAP:
        final_similarity = min(base_similarity, MAX_SIMILARITY_CAP)
        similarity_cache[cache_key] = final_similarity
        return final_similarity, total_tokens
    
    # Проверяем токены
    if total_tokens >= MAX_TOKENS:
        # Для негативных маркеров даем небольшой бонус к базовому сходству
        boosted_similarity = min(base_similarity + 0.05, 0.8)
        similarity_cache[cache_key] = boosted_similarity
        return boosted_similarity, total_tokens

    try:
        # 🔧 ОСЛАБЛЕННАЯ проверка через AI для негативных маркеров
        ai_similarity = await check_semantic_similarity_strict(giga_chat, sent, marker)
        new_tokens = total_tokens + len(sent) + len(marker)
        
        # 🔧 ОСЛАБЛЕННАЯ валидация AI для негативных маркеров
        if ai_similarity > MAX_SIMILARITY_CAP:
            final_similarity = min(base_similarity, MAX_SIMILARITY_CAP)
        elif ai_similarity < base_similarity * 0.5:  # Снижен с 0.6 до 0.5
            final_similarity = base_similarity
        else:
            final_similarity = min(max(ai_similarity, base_similarity), MAX_SIMILARITY_CAP)
        
        similarity_cache[cache_key] = final_similarity
        return final_similarity, new_tokens
        
    except Exception:
        # Для негативных маркеров даем небольшой бонус к базовому сходству
        boosted_similarity = min(base_similarity + 0.05, 0.8)
        similarity_cache[cache_key] = boosted_similarity
        return boosted_similarity, total_tokens

async def check_semantic_similarity_positive(giga_chat: 'AsyncGigaChat', sentence: str, marker: str) -> float:
    """🔧 СПЕЦИАЛЬНАЯ функция для ПОЗИТИВНЫХ маркеров - максимально мягкая"""
    
    prompt = f"""Оцени смысловое сходство по шкале 0-1 с МАКСИМАЛЬНЫМ ПОЗИТИВНЫМ УКЛОНОМ.

ФРАЗА ИЗ ВСТРЕЧИ: "{sentence}"
ПОЗИТИВНЫЙ МАРКЕР: "{marker}"

СУПЕР МЯГКИЕ ПРАВИЛА:
- Если человек говорит о ЛЮБЫХ качествах, навыках, целях = ПОЗИТИВНО (0.5+)
- Если упоминает работу с клиентами, команду, развитие = ПОЗИТИВНО (0.4+)
- Если делится опытом, планами, знаниями = ПОЗИТИВНО (0.3+)
- Ищи ЛЮБЫЕ смысловые связи, будь максимально лояльным
- Минимальная оценка 0.2, максимальная 0.8

Ответь только число 0.XX"""

    try:
        response = await giga_chat.send(prompt)
        result = float(response.strip())
        # Для позитивных маркеров повышаем результат
        return min(max(result, 0.2), 0.8)
    except:
        # Для позитивных маркеров даем больший базовый бонус
        base_sim = SequenceMatcher(None, sentence.lower(), marker.lower()).ratio()
        return min(max(base_sim + 0.1, 0.2), 0.8)

async def check_semantic_similarity_strict(giga_chat: 'AsyncGigaChat', sentence: str, marker: str) -> float:
    """🔧 ОСЛАБЛЕННАЯ функция: Гибкая контекстуальная проверка через AI для поиска негативных совпадений"""
    
    prompt = f"""Оцени смысловое сходство по шкале 0-1 с ОСЛАБЛЕННЫМИ КРИТЕРИЯМИ.

ФРАЗА ИЗ ВСТРЕЧИ: "{sentence}"
НЕГАТИВНЫЙ МАРКЕР: "{marker}"

ОСЛАБЛЕННЫЕ ПРАВИЛА:
- Ищи ЛЮБЫЕ смысловые связи, даже отдаленные
- Если человек говорит о проблемах, сложностях, недостатках - это НЕГАТИВНО
- Если обсуждает ошибки, неудачи, неэффективность - это НЕГАТИВНО
- Если выражает сомнения, недовольство, критику - это НЕГАТИВНО
- Будь МАКСИМАЛЬНО внимательным к негативным проявлениям
- Оценивай от 0.12 до 0.85

Ответь только число 0.XX"""

    try:
        response = await giga_chat.send(prompt)
        result = float(response.strip())
        return min(result, MAX_SIMILARITY_CAP)
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
        
        # Проверяем длину (ОСЛАБЛЕННЫЙ фильтр)
        cleaned = smart_filter.clean_phrase(sent)
        if len(cleaned) < 20:
            filter_stats['filtered_by_length'] += 1
            if len(filter_stats['filtered_examples']['length']) < 5:
                filter_stats['filtered_examples']['length'].append(sent[:100])
            continue
        
        # Морфологический анализ
        morph_analysis = smart_filter.analyze_morphology(sent)
        
        # Проверяем стоп-слова (ОСЛАБЛЕННЫЙ фильтр)
        if morph_analysis['total_words'] > 0:
            stopword_ratio = morph_analysis['stopwords_count'] / morph_analysis['total_words']
            if stopword_ratio > 0.85:  # ОСЛАБЛЕННЫЙ с 70% до 85%
                filter_stats['filtered_by_stopwords'] += 1
                if len(filter_stats['filtered_examples']['stopwords']) < 5:
                    filter_stats['filtered_examples']['stopwords'].append(sent[:100])
                continue
        
        # Проверяем значимые слова (ОСЛАБЛЕННЫЙ фильтр)
        if morph_analysis['meaningful_words'] < 3:  # ОСЛАБЛЕННЫЙ с 5 до 3
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
            for marker, score in data['positive_markers'].items():
                if not marker:
                    continue
                
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
            for marker, score in data['negative_markers'].items():
                if not marker:
                    continue
                
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
                        # 🔧 ИСПРАВЛЕНО: присваиваем ПОЛНЫЙ балл из Excel для негативных маркеров
                        weighted_score = score  # Берем полный балл из файла триггеров
                        method = "sequence_matcher" if similarity <= 0.3 else "giga_enhanced"
                        prompt = (
                            f"Преобразуй негативную фразу в конструктивную, позитивную, сохраняя суть. "
                            f"Ответь ТОЛЬКО позитивной фразой без лишних слов, разметки или объяснений.\n"
                            f"Негатив: \"{sent}\"\n"
                            f"Позитив:"
                        )
                        try:
                            advice = await giga_chat.send(prompt)
                            advice = advice.strip()
                            # Post-processing: если совет неинформативный, подставить дефолт
                            if not advice or advice.lower().startswith("позитив:") or len(advice) < 5:
                                advice = "Сформулируйте мысль конструктивно, с акцентом на развитие и готовность к изменениям."
                        except Exception:
                            advice = "Сформулируйте мысль конструктивно, с акцентом на развитие и готовность к изменениям."
                        match_info = {
                            "found": sent,
                            "original": marker,
                            "score": weighted_score,
                            "similarity": similarity,
                            "method": method,
                            "advice": advice
                        }
                        neg_matches.append(match_info)
                        marker_stats['matches'].append(match_info)
                        indicator_stats['negative_matches'] += 1
                    elif similarity > 0.1:  # Записываем близкие, но не прошедшие порог
                        marker_stats['below_threshold_count'] += 1
                        indicator_stats['below_threshold'] += 1

                indicator_stats['marker_analysis'][f"neg_{marker[:50]}"] = marker_stats
                comp_stats['total_markers'] += 1

            # Подсчет СРЕДНИХ баллов вместо суммирования
            pos_score = sum(m['score'] for m in pos_matches) / len(pos_matches) if pos_matches else 0
            neg_score = sum(m['score'] for m in neg_matches) / len(neg_matches) if neg_matches else 0
            total_score = pos_score - neg_score
            
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

        # Вычисляем средний балл по компетенции
        if comp_results["indicator_scores"]:
            comp_results["total_score"] = sum(comp_results["indicator_scores"]) / len(comp_results["indicator_scores"])
        else:
            comp_results["total_score"] = 0
            
        comp_time = time.time() - comp_start
        print(f"✅ Компетенция завершена за {comp_time:.1f}с")
        print(f"   Маркеров: {comp_stats['total_markers']}, Сравнений: {comp_stats['total_comparisons']}")
        print(f"   Найдено совпадений: {comp_stats['matches_found']}, Ниже порога: {comp_stats['matches_below_threshold']}")
        print(f"   Средний балл компетенции: {comp_results['total_score']:.1f}")
        
        results[comp] = comp_results
        detailed_stats['competency_stats'][comp] = comp_stats

    total_time = time.time() - start_time
    print(f"\n📊 Общая статистика обработки:")
    print(f"   - Время: {total_time:.1f}с")
    print(f"   - Сравнений: {processed_comparisons}")
    print(f"   - Токенов использовано: {total_tokens}")
    print(f"   - Размер кэша: {len(similarity_cache)}")

    # Добавляем детальную статистику к результатам
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
    
    return report

def filter_by_main_speaker(text: str, main_speaker: str = "Александр") -> str:
    """Фильтрует текст, оставляя только реплики главного спикера"""
    lines = text.split('\n')
    speaker_lines = []
    current_speaker = None
    
    for line in lines:
        # Ищем строки с временными метками
        match = re.search(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} -\s*(.+?):)', line)
        if match:
            current_speaker = match.group(2).strip()
            if current_speaker == main_speaker:
                # Добавляем реплику главного спикера (убираем временную метку)
                speech_text = line[match.end():].strip()
                if speech_text:
                    speaker_lines.append(speech_text)
        elif current_speaker == main_speaker and line.strip():
            # Продолжение реплики главного спикера
            speaker_lines.append(line.strip())
    
    return '\n'.join(speaker_lines)

class AsyncGigaChat:
    def __init__(self):
        self.session = None
        self.token = None
        self.history = []

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

        headers = {
            'Authorization': f'Bearer {self.token}',
            'Content-Type': 'application/json'
        }
        payload = {
            'model': 'GigaChat',
            'messages': [
                {
                    'role': 'user',
                    'content': prompt
                }
            ],
            'temperature': 0.7,
            'max_tokens': 500
        }

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
        print(f"   🎯 Порог схожести: {SEMANTIC_THRESHOLD*100:.0f}% (МАКСИМАЛЬНО СНИЖЕН)")
        print(f"   📊 Лимит предложений: {MAX_SENTENCES} (УВЕЛИЧЕН)")
        print(f"   🧠 ОТДЕЛЬНАЯ мягкая ИИ-функция для позитивных маркеров")
        print(f"   ⭐ ИСПРАВЛЕНО: присваиваются ПОЛНЫЕ баллы из Excel (не умноженные)")
        print(f"   🎪 КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: анализируется только главный спикер")
        print(f"   🎯 Специальные бонусы для позитивных совпадений")
        print(f"   ⚖️ Лимиты: +{MAX_POSITIVE_MATCHES} -{MAX_NEGATIVE_MATCHES}")
        print(f"   📈 Диапазон: {MIN_PERCENTAGE}% - {MAX_PERCENTAGE}%")
        print("=" * 60)
        
        logging.info("Начало оптимизированного анализа с ослабленными фильтрами")

        # 1. Загрузка файлов
        if not os.path.exists('./backstage/trans.docx'):
            raise FileNotFoundError("Файл trans.docx не найден")
        if not os.path.exists('./backstage/triggers.xlsx'):
            raise FileNotFoundError("Файл triggers.xlsx не найден")

        triggers = load_triggers('./backstage/triggers.xlsx')
        full_text = load_transcript('./backstage/trans.docx')
        
        text = filter_by_main_speaker(full_text, "Александр")
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