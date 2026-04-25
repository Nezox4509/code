#!/usr/bin/env python3
# modules/monitor.py

"""
Модуль мониторинга состояния серверов
Собирает метрики: CPU, RAM, HDD, Network, uptime, активные процессы
"""

import psutil
import socket
import subprocess
import json
from datetime import datetime
from typing import Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
import paramiko

class ServerMonitor:
    """Класс для мониторинга серверов"""
    
    def __init__(self, config: Dict):
        """
        Инициализация монитора
        :param config: конфигурация с серверами и порогами
        """
        self.config = config
        self.thresholds = config.get('thresholds', {})
        self.results = {}
        
    def get_local_metrics(self) -> Dict:
        """Сбор метрик локального сервера"""
        metrics = {
            'timestamp': datetime.now().isoformat(),
            'hostname': socket.gethostname(),
            'cpu': {
                'percent': psutil.cpu_percent(interval=1),
                'cores': psutil.cpu_count(),
                'per_cpu': psutil.cpu_percent(interval=1, percpu=True)
            },
            'memory': {
                'total_gb': round(psutil.virtual_memory().total / (1024**3), 2),
                'available_gb': round(psutil.virtual_memory().available / (1024**3), 2),
                'percent': psutil.virtual_memory().percent
            },
            'disk': [],
            'network': [],
            'processes': self._get_top_processes(5),
            'uptime': self._get_uptime()
        }
        
        # Сбор информации о дисках
        for partition in psutil.disk_partitions():
            try:
                usage = psutil.disk_usage(partition.mountpoint)
                metrics['disk'].append({
                    'device': partition.device,
                    'mountpoint': partition.mountpoint,
                    'total_gb': round(usage.total / (1024**3), 2),
                    'used_gb': round(usage.used / (1024**3), 2),
                    'free_gb': round(usage.free / (1024**3), 2),
                    'percent': usage.percent
                })
            except PermissionError:
                continue
        
        # Сбор сетевой информации
        for iface, stats in psutil.net_io_counters(pernic=True).items():
            metrics['network'].append({
                'interface': iface,
                'bytes_sent_mb': round(stats.bytes_sent / (1024**2), 2),
                'bytes_recv_mb': round(stats.bytes_recv / (1024**2), 2),
                'packets_sent': stats.packets_sent,
                'packets_recv': stats.packets_recv
            })
        
        return metrics
    
    def _get_top_processes(self, count: int = 5) -> List[Dict]:
        """Получение топ процессов по CPU"""
        processes = []
        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
            try:
                pinfo = proc.info
                processes.append(pinfo)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        
        processes.sort(key=lambda x: x.get('cpu_percent', 0), reverse=True)
        return processes[:count]
    
    def _get_uptime(self) -> str:
        """Получение времени работы системы"""
        boot_time = datetime.fromtimestamp(psutil.boot_time())
        uptime = datetime.now() - boot_time
        days = uptime.days
        hours = uptime.seconds // 3600
        minutes = (uptime.seconds % 3600) // 60
        
        return f"{days}д {hours}ч {minutes}м"
    
    def get_remote_metrics(self, host: str, port: int, username: str, 
                           key_path: str) -> Optional[Dict]:
        """Сбор метрик с удаленного сервера через SSH"""
        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(host, port=port, username=username, key_filename=key_path)
            
            # Сбор команд для выполнения
            commands = {
                'cpu': "top -bn1 | grep 'Cpu(s)' | awk '{print $2}' | cut -d'%' -f1",
                'memory': "free -m | awk 'NR==2{printf \"%.2f\", $3*100/$2 }'",
                'disk': "df -h / | awk 'NR==2{print $5}' | tr -d '%'",
                'uptime': "uptime -p",
                'hostname': "hostname",
                'load': "uptime | awk -F'load average:' '{print $2}'"
            }
            
            metrics = {
                'timestamp': datetime.now().isoformat(),
                'host': host,
            }
            
            for key, cmd in commands.items():
                stdin, stdout, stderr = ssh.exec_command(cmd)
                metrics[key] = stdout.read().decode().strip()
            
            ssh.close()
            return metrics
            
        except Exception as e:
            print(f"Ошибка подключения к {host}: {e}")
            return None
    
    def check_thresholds(self, metrics: Dict) -> List[Dict]:
        """Проверка метрик на превышение порогов"""
        alerts = []
        
        # Проверка CPU
        cpu_percent = metrics.get('cpu', {}).get('percent', 0)
        if cpu_percent > self.thresholds.get('cpu_warning', 80):
            alerts.append({
                'level': 'WARNING',
                'metric': 'CPU',
                'value': cpu_percent,
                'threshold': self.thresholds.get('cpu_warning'),
                'message': f"CPU usage is {cpu_percent}%"
            })
        
        if cpu_percent > self.thresholds.get('cpu_critical', 90):
            alerts[-1]['level'] = 'CRITICAL'
        
        # Проверка памяти
        mem_percent = metrics.get('memory', {}).get('percent', 0)
        if mem_percent > self.thresholds.get('memory_warning', 85):
            alerts.append({
                'level': 'WARNING',
                'metric': 'Memory',
                'value': mem_percent,
                'threshold': self.thresholds.get('memory_warning'),
                'message': f"Memory usage is {mem_percent}%"
            })
        
        # Проверка дисков
        for disk in metrics.get('disk', []):
            if disk.get('percent', 0) > self.thresholds.get('disk_warning', 85):
                alerts.append({
                    'level': 'WARNING',
                    'metric': f"Disk {disk.get('mountpoint')}",
                    'value': disk.get('percent'),
                    'threshold': self.thresholds.get('disk_warning'),
                    'message': f"Disk {disk.get('mountpoint')} is {disk.get('percent')}% full"
                })
        
        return alerts
    
    def monitor_all_servers(self) -> Dict:
        """Мониторинг всех серверов из конфигурации"""
        results = {}
        
        # Локальный мониторинг
        local_metrics = self.get_local_metrics()
        hostname = local_metrics['hostname']
        results[hostname] = {
            'metrics': local_metrics,
            'alerts': self.check_thresholds(local_metrics)
        }
        
        # Удаленный мониторинг (параллельно)
        remote_servers = self.config.get('servers', [])
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {}
            for server in remote_servers:
                future = executor.submit(
                    self.get_remote_metrics,
                    server['host'],
                    server.get('port', 22),
                    server['username'],
                    server['key_path']
                )
                futures[future] = server['host']
            
            for future in as_completed(futures):
                host = futures[future]
                try:
                    metrics = future.result(timeout=30)
                    if metrics:
                        results[host] = {
                            'metrics': metrics,
                            'alerts': self._check_remote_thresholds(metrics)
                        }
                except Exception as e:
                    results[host] = {
                        'error': str(e),
                        'alerts': [{
                            'level': 'CRITICAL',
                            'message': f"Connection failed: {e}"
                        }]
                    }
        
        return results
    
    def _check_remote_thresholds(self, metrics: Dict) -> List[Dict]:
        """Проверка порогов для удаленных метрик"""
        alerts = []
        
        try:
            cpu = float(metrics.get('cpu', 0))
            if cpu > self.thresholds.get('cpu_warning', 80):
                alerts.append({
                    'level': 'WARNING',
                    'metric': 'CPU',
                    'value': cpu,
                    'message': f"Remote CPU usage is {cpu}%"
                })
        except:
            pass
        
        return alerts
    
    def generate_report(self, monitor_results: Dict) -> str:
        """Генерация отчета по результатам мониторинга"""
        report = []
        report.append("=" * 80)
        report.append("ОТЧЕТ ПО МОНИТОРИНГУ СЕРВЕРОВ")
        report.append(f"Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("=" * 80)
        
        for server, data in monitor_results.items():
            report.append(f"\n📊 СЕРВЕР: {server}")
            report.append("-" * 40)
            
            if 'error' in data:
                report.append(f"❌ ОШИБКА: {data['error']}")
                continue
            
            metrics = data.get('metrics', {})
            report.append(f"  CPU: {metrics.get('cpu', 'N/A')}%")
            report.append(f"  Память: {metrics.get('memory', 'N/A')}%")
            report.append(f"  Диск: {metrics.get('disk', 'N/A')}%")
            report.append(f"  Uptime: {metrics.get('uptime', 'N/A')}")
            
            # Алерты
            alerts = data.get('alerts', [])
            if alerts:
                report.append("  ⚠️ АКТИВНЫЕ АЛЕРТЫ:")
                for alert in alerts:
                    report.append(f"    - [{alert['level']}] {alert['message']}")
        
        report.append("\n" + "=" * 80)
        
        return "\n".join(report)


# Скрипт для cron запуска
def main():
    """Точка входа для периодического мониторинга"""
    import yaml
    
    # Загрузка конфигурации
    with open('/opt/automation/config/config.yaml', 'r') as f:
        config = yaml.safe_load(f)
    
    # Инициализация монитора
    monitor = ServerMonitor(config)
    
    # Запуск мониторинга
    results = monitor.monitor_all_servers()
    
    # Сохранение результатов
    report = monitor.generate_report(results)
    with open(f'/opt/automation/logs/monitor_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log', 'w') as f:
        f.write(report)
    
    # Отправка алертов через notifier
    all_alerts = []
    for server, data in results.items():
        all_alerts.extend(data.get('alerts', []))
    
    if all_alerts:
        from modules.notifier import Notifier
        notifier = Notifier(config.get('notifications', {}))
        notifier.send_alerts(all_alerts)


if __name__ == '__main__':
    main()