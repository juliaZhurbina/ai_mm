import asyncio
import logging
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from telegram_bot import main

if __name__ == "__main__":
    # Настройка логирования
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    ) 
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nstopped")
    except Exception as e:
        print(f"\nerror: {e}")
        logging.error(f"\nerror: {e}") 