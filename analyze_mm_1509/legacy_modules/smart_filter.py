import nltk
import re
import string
from typing import List, Set
import asyncio

class SmartPhraseFilter:
    def __init__(self):
        # Расширенный список русских стоп-слов
        self.extended_stopwords = {
            'и', 'в', 'во', 'не', 'что', 'он', 'на', 'я', 'с', 'со', 'как', 'а', 'то', 'все', 'она', 'так',
            'его', 'но', 'да', 'ты', 'к', 'у', 'же', 'вы', 'за', 'бы', 'по', 'только', 'ее', 'мне', 'было',
            'вот', 'от', 'меня', 'еще', 'нет', 'о', 'из', 'ему', 'теперь', 'когда', 'даже', 'ну', 'вдруг',
            'ли', 'если', 'уже', 'или', 'ни', 'быть', 'был', 'него', 'до', 'вас', 'нибудь', 'опять', 'уж',
            'вам', 'ведь', 'там', 'потом', 'себя', 'ничего', 'ей', 'может', 'они', 'тут', 'где', 'есть',
            'надо', 'ней', 'для', 'мы', 'тебя', 'их', 'чем', 'была', 'сам', 'чтоб', 'без', 'будто', 'чего',
            'раз', 'тоже', 'себе', 'под', 'будет', 'ж', 'тогда', 'кто', 'этот', 'того', 'потому', 'этого',
            'какой', 'совсем', 'ним', 'здесь', 'этом', 'один', 'почти', 'мой', 'тем', 'чтобы', 'нее',
            'сейчас', 'были', 'куда', 'зачем', 'всех', 'никогда', 'можно', 'при', 'наконец', 'два',
            'об', 'другой', 'хоть', 'после', 'над', 'больше', 'тот', 'через', 'эти', 'нас', 'про', 'всего',
            'них', 'какая', 'много', 'разве', 'три', 'эту', 'моя', 'впрочем', 'хорошо', 'свою', 'этой',
            'перед', 'иногда', 'лучше', 'чуть', 'том', 'нельзя', 'такой', 'им', 'более', 'всегда',
            'конечно', 'всю', 'между', 'это', 'всё', 'то', 'этот', 'тот', 'эта', 'эти', 'те', 'мои',
            'твои', 'его', 'её', 'их', 'него', 'неё', 'них', 'мне', 'мной', 'мною', 'тебе', 'тебя',
            'тобой', 'тобою', 'нам', 'нами', 'вам', 'вами', 'им', 'ими', 'это', 'этот', 'эта', 'эти',
            'тот', 'та', 'те', 'такой', 'такая', 'такие', 'такое', 'так', 'также', 'тоже', 'либо',
            'или', 'ни', 'не', 'нет', 'ничего', 'никто', 'никогда', 'нигде', 'никуда', 'ниоткуда',
            'никак', 'нисколько', 'ничуть', 'ничуть', 'ничуть', 'ничуть', 'ничуть', 'ничуть', 'ничуть'
        }
        
        self.setup_nltk()
        self.russian_stopwords = set()
        self.load_russian_stopwords()
        
        # Паттерны незначимых фраз
        self.insignificant_patterns = [
            r'^(да|нет|ага|угу|ну|хм|эм|э)\s*[,.!?]*$',  # Междометия
            r'^\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}.*?:.*$',  # Временные метки
            r'^[а-яё]+,?\s*(город|г\.)\s+[а-яё]+\.?$',  # "Анастасия, город Электросталь"
            r'^(спасибо|пожалуйста|извините|простите)\.?$',  # Формальные фразы
            r'^(привет|пока|до\s*свидания|здравствуйте?)\.?$',  # Приветствия
            r'^(меня\s+зовут|я\s+[а-яё]+)\.?$',  # Представления
            r'^[а-яё]+\s*\.?$',  # Одиночные слова с точкой
            r'^(угу|ага|да|нет|хм|эм|э)\s*[,.!?]*$',  # Простые ответы
            r'^(хорошо|понятно|ясно|ладно)\s*[,.!?]*$',  # Согласие
            r'^(точно|конечно|разумеется)\s*[,.!?]*$',  # Подтверждение
        ]
    
    def setup_nltk(self):
        """Настройка NLTK"""
        try:
            # Пытаемся загрузить русские стоп-слова
            nltk.data.find('corpora/stopwords')
        except LookupError:
            print("Скачиваю стоп-слова NLTK...")
            nltk.download('stopwords', quiet=True)
    
    def load_russian_stopwords(self):
        """Загружает русские стоп-слова из NLTK"""
        try:
            from nltk.corpus import stopwords
            self.russian_stopwords = set(stopwords.words('russian'))
            # Добавляем расширенные стоп-слова
            self.russian_stopwords.update(self.extended_stopwords)
            
        except Exception as e:
            print(f"Не удалось загрузить стоп-слова NLTK: {e}")
            # Используем базовый набор русских стоп-слов как fallback
            self.russian_stopwords = self.extended_stopwords
    
    def clean_phrase(self, phrase: str) -> str:
        """Очищает фразу от временных меток и лишних символов"""
        # Убираем временные метки
        cleaned = re.sub(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} -\s*\w+:\s*', '', phrase)
        
        # Убираем лишние пробелы
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        
        return cleaned
    
    def is_insignificant_by_pattern(self, phrase: str) -> bool:
        """Проверяет, является ли фраза незначимой по паттернам"""
        cleaned_phrase = self.clean_phrase(phrase).lower()
        
        for pattern in self.insignificant_patterns:
            if re.match(pattern, cleaned_phrase, re.IGNORECASE):
                return True
        return False
    
    def analyze_morphology(self, phrase: str) -> dict:
        """Упрощенный анализ фразы без pymorphy2"""
        cleaned_phrase = self.clean_phrase(phrase)
        words = cleaned_phrase.translate(str.maketrans('', '', string.punctuation)).split()
        
        if not words:
            return {
                'total_words': 0,
                'meaningful_words': 0,
                'stopwords_count': 0,
                'interjections_count': 0,
                'significant_pos_count': 0
            }
        
        meaningful_words = []
        stopwords_count = 0
        interjections_count = 0
        significant_pos_count = 0
        
        # Простые междометия и незначимые слова
        interjections = {
            'угу', 'ага', 'хм', 'эм', 'э', 'ну', 'да', 'нет', 'хорошо', 'понятно', 
            'ясно', 'ладно', 'точно', 'конечно', 'разумеется', 'спасибо', 'пожалуйста'
        }
        
        for word in words:
            word_lower = word.lower()
            
            # Проверяем стоп-слова
            if word_lower in self.russian_stopwords:
                stopwords_count += 1
                continue
            
            # Проверяем междометия
            if word_lower in interjections:
                interjections_count += 1
                continue
            
            # Проверяем длину слова (слова длиннее 2 символов считаются значимыми)
            if len(word_lower) > 2:
                significant_pos_count += 1
                meaningful_words.append(word_lower)
        
        return {
            'total_words': len(words),
            'meaningful_words': len(meaningful_words),
            'stopwords_count': stopwords_count,
            'interjections_count': interjections_count,
            'significant_pos_count': significant_pos_count,
            'meaningful_word_list': meaningful_words
        }
    
    def is_meaningful_phrase_basic(self, phrase: str, min_length: int = 15, min_meaningful_words: int = 2) -> bool:
        """Базовая проверка значимости фразы без ИИ"""
        # Проверяем по паттернам
        if self.is_insignificant_by_pattern(phrase):
            return False
        
        # Проверяем минимальную длину
        cleaned = self.clean_phrase(phrase)
        if len(cleaned) < min_length:
            return False
        
        # Морфологический анализ
        morph_analysis = self.analyze_morphology(phrase)
        
        # Если слишком много стоп-слов относительно общего количества
        if morph_analysis['total_words'] > 0:
            stopword_ratio = morph_analysis['stopwords_count'] / morph_analysis['total_words']
            if stopword_ratio > 0.7:  # Более 70% стоп-слов
                return False
        
        # Если есть значимые слова
        if morph_analysis['meaningful_words'] >= min_meaningful_words:
            return True
        
        # Если есть значимые части речи
        if morph_analysis['significant_pos_count'] >= min_meaningful_words:
            return True
        
        return False
    
    async def is_meaningful_phrase_ai(self, phrase: str, giga_chat, context: str = "анализ компетенций") -> bool:
        """Проверка значимости фразы с помощью ИИ"""
        # Сначала базовая проверка
        if not self.is_meaningful_phrase_basic(phrase):
            return False
        
        # Если прошла базовую проверку, но все еще сомневаемся, спрашиваем ИИ
        cleaned_phrase = self.clean_phrase(phrase)
        
        prompt = f"""Определи, содержит ли данная фраза значимую информацию для {context}.

Фраза: "{cleaned_phrase}"

Критерии незначимых фраз:
- Междометия (угу, ага, хм)
- Формальные приветствия/прощания
- Представления (меня зовут...)
- Чисто технические реплики
- Переспросы без содержания

Ответь только: ДА (значимая) или НЕТ (незначимая)"""

        try:
            response = await giga_chat.send(prompt)
            return "да" in response.lower()
        except Exception:
            # В случае ошибки используем базовую проверку
            return True

# Функция для интеграции в основной скрипт
def create_smart_filter():
    """Создает и возвращает умный фильтр"""
    return SmartPhraseFilter()

# Тестирование
if __name__ == "__main__":
    filter = SmartPhraseFilter()
    
    # Тестовые фразы
    test_phrases = [
        "Угу, понятно",
        "Меня зовут Иван",
        "Я работаю в банке уже 5 лет и занимаюсь кредитованием малого бизнеса",
        "Спасибо за встречу",
        "Мы внедрили новую CRM систему для автоматизации процессов",
        "Хм, интересно",
        "Я руководитель отдела и отвечаю за планирование и контроль работы команды"
    ]
    
    print("Тестирование умного фильтра:")
    for phrase in test_phrases:
        is_meaningful = filter.is_meaningful_phrase_basic(phrase)
        print(f"'{phrase}' -> {'ЗНАЧИМАЯ' if is_meaningful else 'НЕЗНАЧИМАЯ'}") 