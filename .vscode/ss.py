#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для автоматизированного сбора основных параметров системы Linux
С сохранением результатов в общую папку VirtualBox
"""

import os
import sys
import psutil
import platform
import subprocess
from datetime import datetime
import json
import socket
import re

class LinuxSystemMonitor:
    """Класс для мониторинга основных параметров Linux системы"""
    
    def __init__(self, shared_folder_path=None):
        """
        shared_folder_path - путь к общей папке VirtualBox
        """
        self.system_info = {}
        self.shared_folder = shared_folder_path
        self.reports_dir = None
        
        # Определяем путь для сохранения отчетов
        self._setup_report_directory()
    
    def _setup_report_directory(self):
        """Настройка директории для сохранения отчетов"""
        # Список возможных путей общей папки VirtualBox
        possible_shared_paths = [
            self.shared_folder,
            '/mnt/shared',
            '/media/sf_shared',
            '/media/sf_Shared',
            '/home/user/shared',
            '/root/shared'
        ]
        
        # Убираем None значения
        possible_shared_paths = [p for p in possible_shared_paths if p]
        
        # Проверяем существующие общие папки
        for path in possible_shared_paths:
            if os.path.exists(path) and os.path.isdir(path):
                # Создаем директорию для отчетов
                self.reports_dir = os.path.join(path, 'linux_reports')
                if not os.path.exists(self.reports_dir):
                    try:
                        os.makedirs(self.reports_dir)
                        print(f"📁 Создана директория для отчетов: {self.reports_dir}")
                    except:
                        pass
                break
        
        # Если общая папка не найдена, сохраняем локально
        if self.reports_dir is None:
            self.reports_dir = os.path.join(os.getcwd(), 'linux_reports')
            if not os.path.exists(self.reports_dir):
                os.makedirs(self.reports_dir)
            print(f"⚠️ Общая папка не найдена, отчеты сохраняются локально: {self.reports_dir}")
    
    # ... (остальные методы остаются теми же) ...
    
    def save_to_json(self, filename=None):
        """Сохранение отчета в JSON файл в общую папку"""
        if not self.system_info:
            self.collect_all_info()
        
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"linux_report_{timestamp}.json"
        
        # Полный путь для сохранения
        filepath = os.path.join(self.reports_dir, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.system_info, f, indent=2, ensure_ascii=False, default=str)
        
        print(f"✅ Отчет сохранен: {filepath}")
        
        # Если отчет сохранился в общую папку, показываем путь на хосте
        if 'sf_' in filepath or 'shared' in filepath:
            print(f"📂 Файл доступен на хост-системе в общей папке")
        
        return filepath
    
    def save_to_multiple_formats(self):
        """Сохранение отчета в разных форматах"""
        base_filename = f"linux_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # JSON формат
        json_path = self.save_to_json(f"{base_filename}.json")
        
        # TXT формат (читаемый)
        txt_path = os.path.join(self.reports_dir, f"{base_filename}.txt")
        with open(txt_path, 'w', encoding='utf-8') as f:
            f.write(f"LINUX SYSTEM REPORT\n")
            f.write(f"="*60 + "\n")
            f.write(f"Created: {self.system_info['timestamp']}\n")
            f.write(f"Hostname: {self.system_info['os_info']['hostname']}\n\n")
            
            # Добавляем информацию об IP
            f.write("IP ADDRESSES:\n")
            for ip in self.system_info['ip_addresses']['ipv4']:
                f.write(f"  {ip['interface']}: {ip['ip']}\n")
            
            # Добавляем информацию о CPU
            f.write(f"\nCPU: {self.system_info['cpu_info']['total_cpu_usage']}\n")
            
            # Добавляем информацию о памяти
            f.write(f"RAM: {self.system_info['memory_info']['ram_percentage']}\n")
            
            # Добавляем статус приложений
            f.write("\nRUNNING APPLICATIONS:\n")
            for app, status in self.system_info['applications_status'].items():
                if status['is_running']:
                    f.write(f"  ✅ {app}\n")
        
        print(f"✅ TXT отчет сохранен: {txt_path}")
        return json_path, txt_path

def main():
    """Основная функция"""
    # Укажите путь к общей папке VirtualBox
    # Варианты:
    # shared_path = '/mnt/shared'  # если смонтировали в /mnt/shared
    # shared_path = '/media/sf_shared'  # если автоматическое монтирование
    shared_path = None  # автоопределение
    
    monitor = LinuxSystemMonitor(shared_folder_path=shared_path)
    
    # Сбор всей информации
    monitor.collect_all_info()
    
    # Печать отчета
    monitor.print_report()
    
    # Сохранение в JSON (в общую папку)
    monitor.save_to_json()
    
    # Сохранение в нескольких форматах
    # monitor.save_to_multiple_formats()
    
    print(f"\n✅ Мониторинг завершен!")
    print(f"📁 Отчеты сохранены в: {monitor.reports_dir}")

if __name__ "__main__":
    main()