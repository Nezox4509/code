#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для автоматизированного сбора основных параметров системы Linux
"""

import os
import sys
import psutil
import platform
import subprocess
from datetime import datetime
import json

class LinuxSystemMonitor:
    """Класс для мониторинга основных параметров Linux системы"""
    
    def __init__(self):
        self.system_info = {}
        
    def get_os_info(self):
        """Получение информации об ОС"""
        return {
            'system': platform.system(),
            'hostname': platform.node(),
            'release': platform.release(),
            'version': platform.version(),
            'architecture': platform.machine(),
            'processor': platform.processor(),
            'os_full': f"{platform.system()} {platform.release()}"
        }
    
    def get_cpu_info(self):
        """Получение информации о CPU"""
        try:
            cpu_freq = psutil.cpu_freq()
            return {
                'physical_cores': psutil.cpu_count(logical=False),
                'total_cores': psutil.cpu_count(logical=True),
                'max_frequency': f"{cpu_freq.max:.2f} MHz" if cpu_freq else "N/A",
                'min_frequency': f"{cpu_freq.min:.2f} MHz" if cpu_freq else "N/A",
                'current_frequency': f"{cpu_freq.current:.2f} MHz" if cpu_freq else "N/A",
                'cpu_usage_per_core': [f"{x:.1f}%" for x in psutil.cpu_percent(percpu=True, interval=1)],
                'total_cpu_usage': f"{psutil.cpu_percent(interval=1)}%",
                'load_average': [f"{x:.2f}" for x in os.getloadavg()]
            }
        except Exception as e:
            return {'error': str(e)}
    
    def get_memory_info(self):
        """Получение информации о памяти"""
        try:
            memory = psutil.virtual_memory()
            swap = psutil.swap_memory()
            return {
                'ram_total': self._bytes_to_gb(memory.total),
                'ram_available': self._bytes_to_gb(memory.available),
                'ram_used': self._bytes_to_gb(memory.used),
                'ram_percentage': f"{memory.percent}%",
                'swap_total': self._bytes_to_gb(swap.total),
                'swap_used': self._bytes_to_gb(swap.used),
                'swap_percentage': f"{swap.percent}%",
                'ram_detailed': {
                    'total_bytes': memory.total,
                    'available_bytes': memory.available,
                    'used_bytes': memory.used,
                    'free_bytes': memory.free
                }
            }
        except Exception as e:
            return {'error': str(e)}
    
    def get_disk_info(self):
        """Получение информации о дисках"""
        try:
            disk_info = []
            for partition in psutil.disk_partitions():
                try:
                    partition_usage = psutil.disk_usage(partition.mountpoint)
                    disk_info.append({
                        'device': partition.device,
                        'mountpoint': partition.mountpoint,
                        'file_system': partition.fstype,
                        'total_space': self._bytes_to_gb(partition_usage.total),
                        'used_space': self._bytes_to_gb(partition_usage.used),
                        'free_space': self._bytes_to_gb(partition_usage.free),
                        'usage_percentage': f"{partition_usage.percent}%"
                    })
                except PermissionError:
                    continue
            return disk_info
        except Exception as e:
            return {'error': str(e)}
    
    def get_network_info(self):
        """Получение информации о сети"""
        try:
            network_info = {}
            # Сбор информации о сетевых интерфейсах
            net_if_addrs = psutil.net_if_addrs()
            net_if_stats = psutil.net_if_stats()
            
            for interface, addrs in net_if_addrs.items():
                network_info[interface] = {
                    'is_up': net_if_stats[interface].isup if interface in net_if_stats else False,
                    'speed': f"{net_if_stats[interface].speed} Mbps" if interface in net_if_stats and net_if_stats[interface].speed > 0 else "Unknown",
                    'addresses': []
                }
                for addr in addrs:
                    network_info[interface]['addresses'].append({
                        'family': str(addr.family),
                        'address': addr.address,
                        'netmask': addr.netmask,
                        'broadcast': addr.broadcast
                    })
            
            # Сбор статистики по сети
            net_io = psutil.net_io_counters()
            network_info['statistics'] = {
                'bytes_sent': self._bytes_to_gb(net_io.bytes_sent),
                'bytes_recv': self._bytes_to_gb(net_io.bytes_recv),
                'packets_sent': net_io.packets_sent,
                'packets_recv': net_io.packets_recv,
                'errin': net_io.errin,
                'errout': net_io.errout,
                'dropin': net_io.dropin,
                'dropout': net_io.dropout
            }
            
            return network_info
        except Exception as e:
            return {'error': str(e)}
    
    def get_process_info(self, top_n=10):
        """Получение информации о топ процессах по CPU и памяти"""
        try:
            processes = []
            for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent', 'status']):
                try:
                    processes.append(proc.info)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            # Сортировка процессов по использованию CPU
            top_cpu = sorted(processes, key=lambda x: x['cpu_percent'] or 0, reverse=True)[:top_n]
            # Сортировка процессов по использованию памяти
            top_memory = sorted(processes, key=lambda x: x['memory_percent'] or 0, reverse=True)[:top_n]
            
            return {
                'top_cpu_processes': top_cpu,
                'top_memory_processes': top_memory,
                'total_processes': len(processes)
            }
        except Exception as e:
            return {'error': str(e)}
    
    def get_system_stats(self):
        """Сбор системной статистики через shell команды"""
        stats = {}
        
        # Информация о загрузке системы
        try:
            uptime = subprocess.check_output(['uptime'], text=True).strip()
            stats['uptime'] = uptime
        except:
            stats['uptime'] = "N/A"
        
        # Информация о ядре
        try:
            kernel = subprocess.check_output(['uname', '-r'], text=True).strip()
            stats['kernel'] = kernel
        except:
            stats['kernel'] = "N/A"
        
        # Информация о времени работы
        try:
            stats['boot_time'] = datetime.fromtimestamp(psutil.boot_time()).strftime("%Y-%m-%d %H:%M:%S")
        except:
            stats['boot_time'] = "N/A"
        
        return stats
    
    def _bytes_to_gb(self, bytes_value):
        """Конвертация байтов в гигабайты"""
        return f"{bytes_value / (1024**3):.2f} GB"
    
    def collect_all_info(self):
        """Сбор всей информации о системе"""
        print("🔍 Сбор информации о системе Linux...\n")
        
        self.system_info = {
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'os_info': self.get_os_info(),
            'cpu_info': self.get_cpu_info(),
            'memory_info': self.get_memory_info(),
            'disk_info': self.get_disk_info(),
            'network_info': self.get_network_info(),
            'process_info': self.get_process_info(),
            'system_stats': self.get_system_stats()
        }
        
        return self.system_info
    
    def print_report(self):
        """Печать отчета в консоль"""
        if not self.system_info:
            self.collect_all_info()
        
        print("="*60)
        print(f"📊 ОТЧЕТ ПО СИСТЕМЕ LINUX")
        print("="*60)
        print(f"📅 Время сбора: {self.system_info['timestamp']}")
        print(f"🖥️  Хост: {self.system_info['os_info']['hostname']}")
        print(f"🐧 ОС: {self.system_info['os_info']['os_full']}")
        print(f"🏗️ Архитектура: {self.system_info['os_info']['architecture']}")
        print(f"⏱️ Время работы: {self.system_info['system_stats']['uptime']}")
        
        print("\n" + "="*60)
        print("💻 CPU ИНФОРМАЦИЯ")
        print("="*60)
        cpu_info = self.system_info['cpu_info']
        if 'error' not in cpu_info:
            print(f"Ядер (физических): {cpu_info['physical_cores']}")
            print(f"Ядер (логических): {cpu_info['total_cores']}")
            print(f"Частота: {cpu_info['current_frequency']} / {cpu_info['max_frequency']}")
            print(f"Общая загрузка CPU: {cpu_info['total_cpu_usage']}")
            print(f"Load Average: {', '.join(cpu_info['load_average'])}")
        
        print("\n" + "="*60)
        print("🧠 ПАМЯТЬ")
        print("="*60)
        mem_info = self.system_info['memory_info']
        if 'error' not in mem_info:
            print(f"ОЗУ: {mem_info['ram_used']} / {mem_info['ram_total']} ({mem_info['ram_percentage']})")
            print(f"Swap: {mem_info['swap_used']} / {mem_info['swap_total']} ({mem_info['swap_percentage']})")
        
        print("\n" + "="*60)
        print("💾 ДИСКИ")
        print("="*60)
        for disk in self.system_info['disk_info']:
            if 'error' not in disk:
                print(f"{disk['device']} - {disk['mountpoint']}")
                print(f"  Использовано: {disk['used_space']} / {disk['total_space']} ({disk['usage_percentage']})")
                print(f"  ФС: {disk['file_system']}")
        
        # Топ процессов
        print("\n" + "="*60)
        print("🔥 ТОП 5 ПРОЦЕССОВ ПО CPU")
        print("="*60)
        for i, proc in enumerate(self.system_info['process_info']['top_cpu_processes'][:5], 1):
            print(f"{i}. PID: {proc['pid']} - {proc['name']} (CPU: {proc['cpu_percent']}%)")
    
    def save_to_json(self, filename=None):
        """Сохранение отчета в JSON файл"""
        if not self.system_info:
            self.collect_all_info()
        
        if filename is None:
            filename = f"linux_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(self.system_info, f, indent=2, ensure_ascii=False)
        
        print(f"\n✅ Отчет сохранен в файл: {filename}")
        return filename

def main():
    """Основная функция"""
    monitor = LinuxSystemMonitor()
    
    # Сбор всей информации
    monitor.collect_all_info()
    
    # Печать отчета
    monitor.print_report()
    
    # Сохранение в JSON
    monitor.save_to_json()
    
    print("\n✅ Мониторинг завершен!")

if __name__ == "__main__":
    main()