# system_info.py - быстрая диагностика
import platform
import os

def quick_system_info():
    """Быстрая информация о системе"""
    info = {
        "Хост": platform.node(),
        "ОС": platform.system(),
        "Версия": platform.release(),
        "Архитектура": platform.machine(),
        "Пользователь": os.getlogin(),
        "Загружен": os.getloadavg()[0] if hasattr(os, 'getloadavg') else 'N/A',
    }
    
    for key, value in info.items():
        print(f"{key:12}: {value}")

quick_system_info()