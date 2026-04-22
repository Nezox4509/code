# clean_disk.py - удаляет старые логи и временные файлы
import os
import time
from pathlib import Path

# Удалить файлы старше N дней
def clean_old_files(directory, days=30):
    now = time.time()
    deleted = 0
    
    for root, dirs, files in os.walk(directory):
        for file in files:
            filepath = os.path.join(root, file)
            try:
                if os.path.getmtime(filepath) < now - days*86400:
                    os.remove(filepath)
                    deleted += 1
                    print(f"Удалён: {filepath}")
            except:
                pass
    
    print(f"\n✅ Удалено {deleted} файлов")

# Использование
clean_old_files("/var/log", 30)  # логи старше 30 дней
clean_old_files("/tmp", 7)        # temp файлы старше 7 дней
