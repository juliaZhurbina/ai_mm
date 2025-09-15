#!/usr/bin/env python3
"""
Тестовый скрипт для проверки функциональности бота
"""

import asyncio
import logging
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from competency_analyzer import analyze_competencies_async
from giga_recomendation import MeetingAnalyzer

async def test_competency_analysis():
    """Тест анализа компетенций"""
    print("🧪 Тестирование анализа компетенций...")
    
    try:
        # Проверяем наличие файлов
        trans_file = "./backstage/trans.docx"
        triggers_file = "./backstage/triggers.xlsx"
        
        if not os.path.exists(trans_file):
            print(f"❌ Файл {trans_file} не найден")
            return False
            
        if not os.path.exists(triggers_file):
            print(f"❌ Файл {triggers_file} не найден")
            return False
        
        print("✅ Файлы найдены")
        
        # Тестируем анализ компетенций
        full_report, summary = await analyze_competencies_async(trans_file, triggers_file)
        
        print("✅ Анализ компетенций выполнен успешно")
        print(f"📊 Длина отчета: {len(full_report)} символов")
        print(f"📋 Длина резюме: {len(summary)} символов")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка анализа компетенций: {e}")
        return False

async def test_recommendations():
    """Тест генерации рекомендаций"""
    print("\n🧪 Тестирование генерации рекомендаций...")
    
    try:
        # Создаем анализатор
        AUTH_KEY = 'ZGMzMGJmZjEtODQwYS00ZjAwLWI2NjgtNGIyNGNiY2ViNmE1OjYwNjM3NTU0LWQxMDctNDA5ZS1hZWM3LTAwYjQ5MjZkOGU2OA=='
        SCOPE = 'GIGACHAT_API_PERS'
        API_AUTH_URL = 'https://ngw.devices.sberbank.ru:9443/api/v2/oauth'
        API_CHAT_URL = 'https://gigachat.devices.sberbank.ru/api/v1/chat/completions'
        
        analyzer = MeetingAnalyzer(AUTH_KEY, SCOPE, API_AUTH_URL, API_CHAT_URL)
        
        # Тестируем анализ с файлом
        trans_file = "./backstage/trans.docx"
        if not os.path.exists(trans_file):
            print(f"❌ Файл {trans_file} не найден")
            return False
        
        result = analyzer.analyze_meeting_with_file(trans_file)
        
        print("✅ Генерация рекомендаций выполнена успешно")
        print(f"📊 Длина результата: {len(result)} символов")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка генерации рекомендаций: {e}")
        return False

async def main():
    """Главная функция тестирования"""
    print("🚀 Запуск тестов функциональности бота...")
    print("=" * 60)
    
    # Настройка логирования
    logging.basicConfig(level=logging.INFO)
    
    # Тестируем компоненты
    competency_test = await test_competency_analysis()
    recommendations_test = await test_recommendations()
    
    print("\n" + "=" * 60)
    print("📊 РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ:")
    print(f"📊 Анализ компетенций: {'✅ УСПЕШНО' if competency_test else '❌ ОШИБКА'}")
    print(f"💡 Генерация рекомендаций: {'✅ УСПЕШНО' if recommendations_test else '❌ ОШИБКА'}")
    
    if competency_test and recommendations_test:
        print("\n🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО!")
        print("🤖 Бот готов к использованию")
    else:
        print("\n⚠️ НЕКОТОРЫЕ ТЕСТЫ НЕ ПРОЙДЕНЫ")
        print("🔧 Проверьте настройки и файлы")

if __name__ == "__main__":
    import os
    asyncio.run(main()) 