#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для автоматизированного сбора основных параметров системы Linux
С компактным выводом для терминала
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
    
    def __init__(self):
        self.system_info = {}
        self.verbose = False  # Режим подробного вывода
        
    def set_verbose(self, verbose):
        """Включить/выключить подробный вывод"""
        self.verbose = verbose
        
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
    
    def get_ip_addresses(self):
        """Получение всех IP-адресов системы"""
        ip_info = {
            'ipv4': [],
            'ipv6': [],
            'default_interface': {},
            'public_ip': None
        }
        
        try:
            net_if_addrs = psutil.net_if_addrs()
            
            for interface, addrs in net_if_addrs.items():
                for addr in addrs:
                    if addr.family == socket.AF_INET:
                        ip_info['ipv4'].append({
                            'interface': interface,
                            'ip': addr.address,
                            'netmask': addr.netmask,
                            'broadcast': addr.broadcast
                        })
                    elif addr.family == socket.AF_INET6:
                        if not addr.address.startswith('fe80:'):
                            ip_info['ipv6'].append({
                                'interface': interface,
                                'ip': addr.address,
                                'netmask': addr.netmask
                            })
            
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                    s.connect(("8.8.8.8", 80))
                    default_ip = s.getsockname()[0]
                    ip_info['default_interface']['ip'] = default_ip
                    
                    for iface_info in ip_info['ipv4']:
                        if iface_info['ip'] == default_ip:
                            ip_info['default_interface']['interface'] = iface_info['interface']
                            break
            except Exception:
                ip_info['default_interface']['ip'] = '127.0.0.1'
                ip_info['default_interface']['interface'] = 'lo'
            
            try:
                result = subprocess.run(
                    ['curl', '-s', 'https://api.ipify.org'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if result.returncode == 0 and result.stdout:
                    ip_info['public_ip'] = result.stdout.strip()
            except Exception:
                ip_info['public_ip'] = 'Unable to determine'
                
        except Exception as e:
            ip_info['error'] = str(e)
        
        return ip_info
    
    def get_network_info(self):
        """Получение информации о сети"""
        try:
            network_info = {}
            net_if_stats = psutil.net_if_stats()
            
            for interface, stats in net_if_stats.items():
                network_info[interface] = {
                    'is_up': stats.isup,
                    'speed': f"{stats.speed} Mbps" if stats.speed > 0 else "Unknown",
                    'mtu': stats.mtu
                }
            
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
    
    def check_applications_status(self, applications=None):
        """Проверка статуса запущенных приложений"""
        if applications is None:
            applications = [
                'ssh', 'sshd', 'cron', 'docker', 'nginx', 'mysql',
                'postgresql', 'redis', 'python', 'java'
            ]
        
        app_status = {}
        
        try:
            for app in applications:
                app_status[app] = {
                    'is_running': False,
                    'status': 'not_found',
                    'pid': None,
                    'service_type': None,
                    'ports': []
                }
                
                try:
                    result = subprocess.run(
                        ['systemctl', 'is-active', app],
                        capture_output=True,
                        text=True,
                        timeout=3
                    )
                    if result.returncode == 0 and result.stdout.strip() == 'active':
                        app_status[app]['is_running'] = True
                        app_status[app]['status'] = 'active'
                        app_status[app]['service_type'] = 'systemd'
                except:
                    pass
                
                for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                    try:
                        proc_name = proc.info['name'].lower() if proc.info['name'] else ''
                        cmdline = ' '.join(proc.info['cmdline']).lower() if proc.info['cmdline'] else ''
                        
                        if app.lower() in proc_name or app.lower() in cmdline:
                            app_status[app]['is_running'] = True
                            app_status[app]['pid'] = proc.info['pid']
                            if not app_status[app]['service_type']:
                                app_status[app]['service_type'] = 'process'
                            break
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue
                
                if not app_status[app]['is_running']:
                    try:
                        result = subprocess.run(
                            ['which', app],
                            capture_output=True,
                            text=True,
                            timeout=2
                        )
                        if result.returncode == 0:
                            app_status[app]['status'] = 'installed_not_running'
                        else:
                            app_status[app]['status'] = 'not_installed'
                    except:
                        app_status[app]['status'] = 'unknown'
                        
        except Exception as e:
            return {'error': str(e)}
        
        return app_status
    
    def get_process_info(self, top_n=5):
        """Получение информации о топ процессах"""
        try:
            processes = []
            for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
                try:
                    processes.append(proc.info)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            top_cpu = sorted(processes, key=lambda x: x['cpu_percent'] or 0, reverse=True)[:top_n]
            
            return {
                'top_cpu_processes': top_cpu,
                'total_processes': len(processes)
            }
        except Exception as e:
            return {'error': str(e)}
    
    def get_system_stats(self):
        """Сбор системной статистики"""
        stats = {}
        
        try:
            uptime = subprocess.check_output(['uptime'], text=True).strip()
            stats['uptime'] = uptime
        except:
            stats['uptime'] = "N/A"
        
        try:
            kernel = subprocess.check_output(['uname', '-r'], text=True).strip()
            stats['kernel'] = kernel
        except:
            stats['kernel'] = "N/A"
        
        try:
            stats['boot_time'] = datetime.fromtimestamp(psutil.boot_time()).strftime("%Y-%m-%d %H:%M:%S")
        except:
            stats['boot_time'] = "N/A"
        
        try:
            users = subprocess.check_output(['who'], text=True).strip().split('\n')
            stats['logged_users'] = len([u for u in users if u.strip()])
        except:
            stats['logged_users'] = 0
        
        return stats
    
    def _bytes_to_gb(self, bytes_value):
        """Конвертация байтов в гигабайты"""
        return f"{bytes_value / (1024**3):.2f} GB"
    
    def collect_all_info(self):
        """Сбор всей информации о системе"""
        if self.verbose:
            print("🔍 Сбор информации о системе Linux...")
        
        self.system_info = {
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'os_info': self.get_os_info(),
            'cpu_info': self.get_cpu_info(),
            'memory_info': self.get_memory_info(),
            'disk_info': self.get_disk_info(),
            'ip_addresses': self.get_ip_addresses(),
            'network_info': self.get_network_info(),
            'applications_status': self.check_applications_status(),
            'process_info': self.get_process_info(),
            'system_stats': self.get_system_stats()
        }
        
        return self.system_info
    
    def print_report_compact(self):
        """Компактная печать отчета (помещается в терминале)"""
        if not self.system_info:
            self.collect_all_info()
        
        # Очистка экрана (опционально)
        # os.system('clear')
        
        print("\n" + "═"*60)
        print("📊 LINUX SYSTEM MONITOR")
        print("═"*60)
        print(f"📅 {self.system_info['timestamp']}")
        print(f"🖥️  {self.system_info['os_info']['hostname']}")
        print(f"🐧 {self.system_info['os_info']['os_full']}")
        print("─"*60)
        
        # IP адреса (только основной)
        ip_info = self.system_info['ip_addresses']
        if 'error' not in ip_info:
            main_ip = ip_info['default_interface'].get('ip', 'N/A')
            public_ip = ip_info['public_ip'] or 'N/A'
            print(f"🌐 IP: {main_ip} | Публичный: {public_ip}")
        
        # CPU (одной строкой)
        cpu_info = self.system_info['cpu_info']
        if 'error' not in cpu_info:
            print(f"💻 CPU: {cpu_info['total_cpu_usage']} | Load: {', '.join(cpu_info['load_average'])}")
        
        # Память (одной строкой)
        mem_info = self.system_info['memory_info']
        if 'error' not in mem_info:
            print(f"🧠 RAM: {mem_info['ram_used']} / {mem_info['ram_total']} ({mem_info['ram_percentage']})")
            if mem_info['swap_total'] != '0.00 GB':
                print(f"🔄 Swap: {mem_info['swap_used']} / {mem_info['swap_total']} ({mem_info['swap_percentage']})")
        
        # Диски (только основные, одной строкой)
        disks = self.system_info['disk_info']
        if disks and 'error' not in disks[0]:
            disk_summary = []
            for disk in disks[:2]:  # Только первые 2 диска
                if disk['mountpoint'] in ['/', '/home']:
                    disk_summary.append(f"{disk['mountpoint']}: {disk['usage_percentage']}")
            if disk_summary:
                print(f"💾 Диски: {' | '.join(disk_summary)}")
        
        # Запущенные приложения (одной строкой)
        apps = self.system_info['applications_status']
        if 'error' not in apps:
            running = [app for app, status in apps.items() if status['is_running']]
            if running:
                running_str = ', '.join(running[:8])  # Только 8 приложений
                if len(running) > 8:
                    running_str += f" +{len(running)-8}"
                print(f"✅ Запущено: {running_str}")
        
        # Топ процессов (3 процесса)
        print("─"*60)
        print("🔥 TOP 3 PROCESSES BY CPU:")
        for i, proc in enumerate(self.system_info['process_info']['top_cpu_processes'][:3], 1):
            cpu = proc['cpu_percent'] if proc['cpu_percent'] is not None else 0
            name = proc['name'][:20] if proc['name'] else 'unknown'
            print(f"  {i}. {name:20} CPU: {cpu:5.1f}%")
        
        print("═"*60)
        
        # Статистика приложений
        if 'error' not in apps:
            total_apps = len(apps)
            running_count = len(running)
            print(f"📊 Приложения: {running_count}/{total_apps} запущено")
        
        print(f"👥 Пользователей: {self.system_info['system_stats']['logged_users']}")
        print("═"*60)
    
    def print_report_verbose(self):
        """Полная версия отчета"""
        self.print_report()  # Используем оригинальный метод
    
    def save_to_json(self, filename=None):
        """Сохранение отчета в JSON файл"""
        if not self.system_info:
            self.collect_all_info()
        
        if filename is None:
            filename = f"linux_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(self.system_info, f, indent=2, ensure_ascii=False, default=str)
        
        print(f"\n💾 Отчет сохранен: {filename}")
        return filename

def copy_reports_to_shared():
    """Копирование отчетов в общую папку"""
    import shutil
    import glob
    
    shared_folders = [
        '/mnt/shared',
        '/media/sf_shared',
        '/media/sf_Shared'
    ]
    
    shared_path = None
    for path in shared_folders:
        if os.path.exists(path):
            shared_path = path
            break
    
    if shared_path:
        reports_dir = os.path.join(shared_path, 'linux_reports')
        os.makedirs(reports_dir, exist_ok=True)
        
        for report_file in glob.glob('linux_report_*.json'):
            dest = os.path.join(reports_dir, report_file)
            shutil.copy2(report_file, dest)
            print(f"📁 Копия в общую папку: {dest}")
        
        newest_report = max(glob.glob('linux_report_*.json'), key=os.path.getctime, default=None)
        if newest_report:
            shutil.copy2(newest_report, os.path.join(reports_dir, 'current_report.json'))
            print(f"📁 Обновлен current_report.json")
    else:
        print("⚠️ Общая папка не найдена")

def main():
    """Основная функция"""
    import argparse
    
    # Парсер аргументов командной строки
    parser = argparse.ArgumentParser(description='Linux System Monitor')
    parser.add_argument('-v', '--verbose', action='store_true', help='Подробный вывод')
    parser.add_argument('-c', '--compact', action='store_true', default=True, help='Компактный вывод (по умолчанию)')
    parser.add_argument('-s', '--shared', action='store_true', help='Копировать отчет в общую папку')
    
    args = parser.parse_args()
    
    monitor = LinuxSystemMonitor()
    
    # Устанавливаем режим
    if args.verbose:
        monitor.set_verbose(True)
    
    # Сбор информации
    monitor.collect_all_info()
    
    # Вывод отчета
    if args.verbose:
        monitor.print_report_verbose()
    else:
        monitor.print_report_compact()
    
    # Сохранение в JSON
    monitor.save_to_json()
    
    # Копирование в общую папку
    if args.shared:
        copy_reports_to_shared()
    
    print("\n✅ Мониторинг завершен!")

if __name__ == "__main__":
    main()