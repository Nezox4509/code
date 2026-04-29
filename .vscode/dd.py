#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для автоматизированного сбора основных параметров системы Linux
С добавленной информацией об IP-адресах и статусе приложений
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
            # Получение IP-адресов через socket
            hostname = socket.gethostname()
            
            # Получение всех интерфейсов через netifaces или через psutil
            net_if_addrs = psutil.net_if_addrs()
            
            for interface, addrs in net_if_addrs.items():
                for addr in addrs:
                    if addr.family == socket.AF_INET:  # IPv4
                        ip_info['ipv4'].append({
                            'interface': interface,
                            'ip': addr.address,
                            'netmask': addr.netmask,
                            'broadcast': addr.broadcast
                        })
                    elif addr.family == socket.AF_INET6:  # IPv6
                        if not addr.address.startswith('fe80:'):  # Исключаем link-local
                            ip_info['ipv6'].append({
                                'interface': interface,
                                'ip': addr.address,
                                'netmask': addr.netmask
                            })
            
            # Определение основного интерфейса и IP
            try:
                # Получаем IP по умолчанию через подключение к внешнему серверу
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                    s.connect(("8.8.8.8", 80))
                    default_ip = s.getsockname()[0]
                    ip_info['default_interface']['ip'] = default_ip
                    
                    # Находим интерфейс для этого IP
                    for iface_info in ip_info['ipv4']:
                        if iface_info['ip'] == default_ip:
                            ip_info['default_interface']['interface'] = iface_info['interface']
                            break
            except Exception:
                ip_info['default_interface']['ip'] = '127.0.0.1'
                ip_info['default_interface']['interface'] = 'lo'
            
            # Получение публичного IP через внешний сервис
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
        """Получение информации о сети (дополнительно к IP)"""
        try:
            network_info = {}
            net_if_stats = psutil.net_if_stats()
            
            for interface, stats in net_if_stats.items():
                network_info[interface] = {
                    'is_up': stats.isup,
                    'speed': f"{stats.speed} Mbps" if stats.speed > 0 else "Unknown",
                    'mtu': stats.mtu
                }
            
            # Статистика сети
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
        """
        Проверка статуса запущенных приложений
        applications: список приложений для проверки (если None - проверяет популярные)
        """
        if applications is None:
            # Список популярных приложений для проверки
            applications = [
                'nginx', 'apache2', 'httpd', 'mysql', 'mariadb', 'postgresql',
                'redis', 'mongodb', 'docker', 'kubelet', 'jenkins', 'gitlab',
                'prometheus', 'grafana', 'elasticsearch', 'kibana', 'logstash',
                'tomcat', 'node', 'python', 'java', 'ssh', 'sshd', 'cron',
                'firewalld', 'ufw', 'fail2ban', 'zabbix_agent', 'nagios'
            ]
        
        app_status = {}
        
        # Проверка через systemctl (для systemd систем)
        try:
            for app in applications:
                app_status[app] = {
                    'is_running': False,
                    'status': 'not_found',
                    'pid': None,
                    'service_type': None,
                    'ports': []
                }
                
                # Проверка через systemctl
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
                
                # Поиск процессов
                for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                    try:
                        proc_name = proc.info['name'].lower() if proc.info['name'] else ''
                        cmdline = ' '.join(proc.info['cmdline']).lower() if proc.info['cmdline'] else ''
                        
                        if app.lower() in proc_name or app.lower() in cmdline:
                            app_status[app]['is_running'] = True
                            app_status[app]['pid'] = proc.info['pid']
                            if not app_status[app]['service_type']:
                                app_status[app]['service_type'] = 'process'
                            
                            # Попытка найти порты, которые слушает процесс
                            try:
                                connections = psutil.net_connections()
                                for conn in connections:
                                    if conn.pid == proc.info['pid'] and conn.status == 'LISTEN':
                                        app_status[app]['ports'].append(conn.laddr.port)
                            except:
                                pass
                            break
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue
                
                # Если приложение не найдено, проверяем через which
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
    
    def check_custom_services(self, services_list):
        """
        Проверка статуса пользовательского списка сервисов
        services_list: список названий сервисов для проверки
        """
        return self.check_applications_status(services_list)
    
    def get_process_info(self, top_n=10):
        """Получение информации о топ процессах по CPU и памяти"""
        try:
            processes = []
            for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent', 'status', 'create_time']):
                try:
                    proc_info = proc.info
                    proc_info['create_time'] = datetime.fromtimestamp(proc_info['create_time']).strftime('%Y-%m-%d %H:%M:%S')
                    processes.append(proc_info)
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
        
        # Информация о пользователях
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
        print("🔍 Сбор информации о системе Linux...\n")
        
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
    
    def print_report(self):
        """Печать отчета в консоль"""
        if not self.system_info:
            self.collect_all_info()
        
        print("="*70)
        print(f"📊 ОТЧЕТ ПО СИСТЕМЕ LINUX")
        print("="*70)
        print(f"📅 Время сбора: {self.system_info['timestamp']}")
        print(f"🖥️  Хост: {self.system_info['os_info']['hostname']}")
        print(f"🐧 ОС: {self.system_info['os_info']['os_full']}")
        print(f"🏗️ Архитектура: {self.system_info['os_info']['architecture']}")
        print(f"⏱️ Время работы: {self.system_info['system_stats']['uptime']}")
        print(f"👥 Пользователей онлайн: {self.system_info['system_stats']['logged_users']}")
        
        print("\n" + "="*70)
        print("🌐 IP-АДРЕСА")
        print("="*70)
        ip_info = self.system_info['ip_addresses']
        if 'error' not in ip_info:
            print(f"🌍 Публичный IP: {ip_info['public_ip']}")
            print(f"🔗 Основной интерфейс: {ip_info['default_interface'].get('interface', 'N/A')} - {ip_info['default_interface'].get('ip', 'N/A')}")
            
            if ip_info['ipv4']:
                print("\n📡 IPv4 адреса:")
                for ip in ip_info['ipv4']:
                    print(f"   • {ip['interface']}: {ip['ip']} / {ip['netmask']}")
            
            if ip_info['ipv6']:
                print("\n📡 IPv6 адреса:")
                for ip in ip_info['ipv6']:
                    print(f"   • {ip['interface']}: {ip['ip']}")
        
        print("\n" + "="*70)
        print("💻 CPU ИНФОРМАЦИЯ")
        print("="*70)
        cpu_info = self.system_info['cpu_info']
        if 'error' not in cpu_info:
            print(f"Ядер (физических): {cpu_info['physical_cores']}")
            print(f"Ядер (логических): {cpu_info['total_cores']}")
            print(f"Частота: {cpu_info['current_frequency']} / {cpu_info['max_frequency']}")
            print(f"Общая загрузка CPU: {cpu_info['total_cpu_usage']}")
            print(f"Load Average: {', '.join(cpu_info['load_average'])}")
        
        print("\n" + "="*70)
        print("🧠 ПАМЯТЬ")
        print("="*70)
        mem_info = self.system_info['memory_info']
        if 'error' not in mem_info:
            print(f"ОЗУ: {mem_info['ram_used']} / {mem_info['ram_total']} ({mem_info['ram_percentage']})")
            print(f"Swap: {mem_info['swap_used']} / {mem_info['swap_total']} ({mem_info['swap_percentage']})")
        
        print("\n" + "="*70)
        print("💾 ДИСКИ")
        print("="*70)
        for disk in self.system_info['disk_info']:
            if 'error' not in disk:
                print(f"{disk['device']} - {disk['mountpoint']}")
                print(f"  Использовано: {disk['used_space']} / {disk['total_space']} ({disk['usage_percentage']})")
                print(f"  ФС: {disk['file_system']}")
        
        print("\n" + "="*70)
        print("📦 СТАТУС ПРИЛОЖЕНИЙ")
        print("="*70)
        apps = self.system_info['applications_status']
        if 'error' not in apps:
            running_apps = []
            installed_apps = []
            not_installed_apps = []
            
            for app, status in apps.items():
                if status['is_running']:
                    ports_str = f" (порты: {', '.join(map(str, status['ports']))})" if status['ports'] else ""
                    running_apps.append(f"  ✅ {app}{ports_str}")
                elif status['status'] == 'installed_not_running':
                    installed_apps.append(f"  ⚠️ {app} (установлен, но не запущен)")
                elif status['status'] == 'not_installed':
                    not_installed_apps.append(f"  ❌ {app}")
            
            if running_apps:
                print("🟢 ЗАПУЩЕНЫ:")
                for app in running_apps[:10]:  # Показываем первые 10
                    print(app)
                if len(running_apps) > 10:
                    print(f"  ... и еще {len(running_apps) - 10}")
            
            if installed_apps:
                print("\n🟡 УСТАНОВЛЕНЫ (НЕ ЗАПУЩЕНЫ):")
                for app in installed_apps[:5]:
                    print(app)
            
            # Краткая статистика
            print(f"\n📊 Статистика: Запущено: {len(running_apps)}, Установлено: {len(installed_apps)}, Не установлено: {len(not_installed_apps)}")
        
        # Топ процессов (только запущенные)
        print("\n" + "="*70)
        print("🔥 ТОП 5 ПРОЦЕССОВ ПО CPU")
        print("="*70)
        for i, proc in enumerate(self.system_info['process_info']['top_cpu_processes'][:5], 1):
            cpu = proc['cpu_percent'] if proc['cpu_percent'] is not None else 0
            mem = proc['memory_percent'] if proc['memory_percent'] is not None else 0
            print(f"{i}. PID: {proc['pid']} - {proc['name']} (CPU: {cpu}%, MEM: {mem:.1f}%)")
    
    def save_to_json(self, filename=None):
        """Сохранение отчета в JSON файл"""
        if not self.system_info:
            self.collect_all_info()
        
        if filename is None:
            filename = f"linux_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(self.system_info, f, indent=2, ensure_ascii=False, default=str)
        
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
# Добавьте в конец файла dd.py после main()

def copy_reports_to_shared():
    """Копирование отчетов в общую папку"""
    import shutil
    import glob
    
    # Поиск общей папки
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
        # Создаем папку для отчетов
        reports_dir = os.path.join(shared_path, 'linux_reports')
        os.makedirs(reports_dir, exist_ok=True)
        
        # Копируем все JSON отчеты
        for report_file in glob.glob('linux_report_*.json'):
            dest = os.path.join(reports_dir, report_file)
            shutil.copy2(report_file, dest)
            print(f"📁 Отчет скопирован в общую папку: {dest}")
        
        # Также копируем последний отчет как current_report.json
        newest_report = max(glob.glob('linux_report_*.json'), key=os.path.getctime, default=None)
        if newest_report:
            shutil.copy2(newest_report, os.path.join(reports_dir, 'current_report.json'))
            print(f"📁 Обновлен current_report.json")
    else:
        print("⚠️ Общая папка не найдена, отчеты сохранены локально")

# Замените вызов main() на:
if __name__ == "__main__":
    main()
    copy_reports_to_shared()