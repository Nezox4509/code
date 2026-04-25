#!/usr/bin/env python3
"""
01_monitor.py - Система мониторинга серверов
Собирает метрики: CPU, RAM, HDD, Network, Processes
Отправляет алерты при превышении порогов
"""

import os
import sys
import json
import time
import socket
import subprocess
import logging
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from concurrent.futures import ThreadPoolExecutor

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/monitor.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


@dataclass
class ServerMetrics:
    """Класс для хранения метрик"""
    timestamp: str
    hostname: str
    cpu_percent: float
    cpu_cores: int
    memory_total_gb: float
    memory_used_gb: float
    memory_percent: float
    disk_total_gb: float
    disk_used_gb: float
    disk_percent: float
    network_rx_mb: float
    network_tx_mb: float
    uptime_days: float
    processes_count: int
    status: str = "OK"


class ServerMonitor:
    """Основной класс мониторинга"""
    
    def __init__(self, config_path: str = "config/config.yaml"):
        self.config = self._load_config(config_path)
        self.history = []
        self.alerts = []
        
        # Создание директорий
        Path("logs").mkdir(exist_ok=True)
        Path("data").mkdir(exist_ok=True)
        
        logger.info(f"Монитор запущен на {socket.gethostname()}")
    
    def _load_config(self, config_path: str) -> Dict:
        """Загрузка конфигурации"""
        default_config = {
            'monitoring_interval': 60,
            'thresholds': {
                'cpu_warning': 80,
                'cpu_critical': 90,
                'memory_warning': 85,
                'memory_critical': 95,
                'disk_warning': 85,
                'disk_critical': 95
            },
            'services': ['nginx', 'mysql', 'sshd'],
            'notification': {
                'telegram_bot_token': None,
                'telegram_chat_id': None
            }
        }
        
        if os.path.exists(config_path):
            import yaml
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
                default_config.update(config)
        
        return default_config
    
    def get_cpu_usage(self) -> Dict:
        """Получение загрузки CPU"""
        try:
            # Чтение /proc/stat
            with open('/proc/stat', 'r') as f:
                cpu_line = f.readline()
            
            parts = cpu_line.split()
            user = int(parts[1])
            nice = int(parts[2])
            system = int(parts[3])
            idle = int(parts[4])
            iowait = int(parts[5])
            
            total = user + nice + system + idle + iowait
            idle_time = idle + iowait
            
            # Получение load average
            with open('/proc/loadavg', 'r') as f:
                load_data = f.read().split()
                load_1min = float(load_data[0])
                load_5min = float(load_data[1])
                load_15min = float(load_data[2])
            
            return {
                'percent': round((total - idle_time) / total * 100, 1) if total > 0 else 0,
                'cores': os.cpu_count(),
                'load_1min': load_1min,
                'load_5min': load_5min,
                'load_15min': load_15min
            }
        except Exception as e:
            logger.error(f"Ошибка получения CPU: {e}")
            return {'percent': 0, 'cores': 1}
    
    def get_memory_usage(self) -> Dict:
        """Получение использования памяти"""
        try:
            with open('/proc/meminfo', 'r') as f:
                meminfo = {}
                for line in f:
                    parts = line.split(':')
                    if len(parts) == 2:
                        key = parts[0].strip()
                        value = parts[1].strip().split()[0]
                        meminfo[key] = int(value)
            
            total = meminfo.get('MemTotal', 0) / 1024 / 1024  # GB
            available = meminfo.get('MemAvailable', 0) / 1024 / 1024
            used = total - available
            percent = (used / total) * 100 if total > 0 else 0
            
            return {
                'total_gb': round(total, 2),
                'used_gb': round(used, 2),
                'free_gb': round(available, 2),
                'percent': round(percent, 1)
            }
        except Exception as e:
            logger.error(f"Ошибка получения памяти: {e}")
            return {'total_gb': 0, 'used_gb': 0, 'free_gb': 0, 'percent': 0}
    
    def get_disk_usage(self, path: str = '/') -> Dict:
        """Получение использования диска"""
        try:
            stat = os.statvfs(path)
            block_size = stat.f_frsize
            total = (stat.f_blocks * block_size) / 1024 / 1024 / 1024
            free = (stat.f_bfree * block_size) / 1024 / 1024 / 1024
            used = total - free
            percent = (used / total) * 100 if total > 0 else 0
            
            return {
                'path': path,
                'total_gb': round(total, 2),
                'used_gb': round(used, 2),
                'free_gb': round(free, 2),
                'percent': round(percent, 1)
            }
        except Exception as e:
            logger.error(f"Ошибка получения диска: {e}")
            return {}
    
    def get_network_stats(self) -> Dict:
        """Получение сетевой статистики"""
        try:
            with open('/proc/net/dev', 'r') as f:
                lines = f.readlines()[2:]
            
            rx_total = 0
            tx_total = 0
            
            for line in lines:
                parts = line.split(':')
                if len(parts) >= 2 and parts[0].strip() != 'lo':
                    stats = parts[1].split()
                    rx_bytes = int(stats[0])
                    tx_bytes = int(stats[8])
                    rx_total += rx_bytes
                    tx_total += tx_bytes
            
            return {
                'rx_mb': round(rx_total / 1024 / 1024, 2),
                'tx_mb': round(tx_total / 1024 / 1024, 2)
            }
        except Exception as e:
            logger.error(f"Ошибка получения сети: {e}")
            return {'rx_mb': 0, 'tx_mb': 0}
    
    def get_uptime(self) -> float:
        """Получение времени работы"""
        try:
            with open('/proc/uptime', 'r') as f:
                uptime_seconds = float(f.read().split()[0])
                return round(uptime_seconds / 86400, 1)
        except:
            return 0
    
    def get_processes_count(self) -> int:
        """Подсчет процессов"""
        try:
            return len([p for p in os.listdir('/proc') if p.isdigit()])
        except:
            return 0
    
    def get_service_status(self, service_name: str) -> str:
        """Проверка статуса сервиса"""
        try:
            result = subprocess.run(
                ['systemctl', 'is-active', service_name],
                capture_output=True, text=True, timeout=5
            )
            return result.stdout.strip()
        except:
            return 'unknown'
    
    def check_thresholds(self, metrics: Dict) -> List[Dict]:
        """Проверка пороговых значений"""
        alerts = []
        thresholds = self.config['thresholds']
        
        cpu = metrics.get('cpu', {}).get('percent', 0)
        if cpu >= thresholds['cpu_critical']:
            alerts.append({'level': 'CRITICAL', 'metric': 'CPU', 'value': cpu})
        elif cpu >= thresholds['cpu_warning']:
            alerts.append({'level': 'WARNING', 'metric': 'CPU', 'value': cpu})
        
        memory = metrics.get('memory', {}).get('percent', 0)
        if memory >= thresholds['memory_critical']:
            alerts.append({'level': 'CRITICAL', 'metric': 'Memory', 'value': memory})
        elif memory >= thresholds['memory_warning']:
            alerts.append({'level':'WARNING', 'metric': 'Memory', 'value': memory})
        
        return alerts
    
    def collect_metrics(self) -> Dict:
        """Сбор всех метрик"""
        metrics = {
            'timestamp': datetime.now().isoformat(),
            'hostname': socket.gethostname(),
            'cpu': self.get_cpu_usage(),
            'memory': self.get_memory_usage(),
            'disk': self.get_disk_usage(),
            'network': self.get_network_stats(),
            'uptime_days': self.get_uptime(),
            'processes': self.get_processes_count(),
            'services': {s: self.get_service_status(s) for s in self.config['services']}
        }
        
        metrics['alerts'] = self.check_thresholds(metrics)
        metrics['status'] = 'CRITICAL' if any(a['level'] == 'CRITICAL' for a in metrics['alerts']) \
            else 'WARNING' if metrics['alerts'] else 'OK'
        
        # Сохранение в историю
        self.history.append(metrics)
        if len(self.history) > 1440:
            self.history.pop(0)
        
        # Сохранение в файл
        self._save_metrics(metrics)
        
        return metrics
    
    def _save_metrics(self, metrics: Dict):
        """Сохранение метрик в файл"""
        filename = f"data/metrics_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, 'w') as f:
            json.dump(metrics, f, indent=2)
    
    def generate_report(self, metrics: Dict = None) -> str:
        """Генерация отчета"""
        if metrics is None:
            metrics = self.collect_metrics()
        
        report = []
        report.append("=" * 70)
        report.append(f"📊 ОТЧЕТ ПО МОНИТОРИНГУ - {metrics['hostname']}")
        report.append(f"📅 Время: {metrics['timestamp']}")
        report.append(f"🔴 Статус: {metrics['status']}")
        report.append("=" * 70)
        
        # CPU
        cpu = metrics['cpu']
        report.append(f"\n💻 CPU:")
        report.append(f"   Загрузка: {cpu['percent']}%")
        report.append(f"   Ядра: {cpu['cores']}")
        report.append(f"   Load Average: {cpu['load_1min']}, {cpu['load_5min']}, {cpu['load_15min']}")
        
        # Память
        mem = metrics['memory']
        report.append(f"\n🧠 ПАМЯТЬ:")
        report.append(f"   Всего: {mem['total_gb']} GB")
        report.append(f"   Использовано: {mem['used_gb']} GB ({mem['percent']}%)")
        report.append(f"   Свободно: {mem['free_gb']} GB")
        
        # Диск
        disk = metrics['disk']
        report.append(f"\n💾 ДИСК:")
        report.append(f"   Всего: {disk['total_gb']} GB")
        report.append(f"   Использовано: {disk['used_gb']} GB ({disk['percent']}%)")
        report.append(f"   Свободно: {disk['free_gb']} GB")
        
        # Сеть
        net = metrics['network']
        report.append(f"\n🌐 СЕТЬ:")
        report.append(f"   RX: {net['rx_mb']} MB")
        report.append(f"   TX: {net['tx_mb']} MB")
        
        # Сервисы
        report.append(f"\n🔧 СЕРВИСЫ:")
        for service, status in metrics['services'].items():
            icon = "✅" if status == 'active' else "❌"
            report.append(f"   {icon} {service}: {status}")
        
        # Алерты
        if metrics['alerts']:
            report.append(f"\n⚠️ АКТИВНЫЕ АЛЕРТЫ:")
            for alert in metrics['alerts']:
                report.append(f"   [{alert['level']}] {alert['metric']}: {alert['value']}%")
        
        report.append("\n" + "=" * 70)
        
        return "\n".join(report)
    
    def run_once(self):
        """Однократный запуск"""
        metrics = self.collect_metrics()
        report = self.generate_report(metrics)
        print(report)
        
        # Сохранение отчета
        with open(f"logs/report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt", 'w') as f:
            f.write(report)
        
        return metrics
    
    def run_daemon(self):
        """Запуск в режиме демона"""
        logger.info(f"Запуск демона. Интервал: {self.config['monitoring_interval']} сек")
        
        while True:
            try:
                self.run_once()
                time.sleep(self.config['monitoring_interval'])
            except KeyboardInterrupt:
                logger.info("Остановка демона")
                break
            except Exception as e:
                logger.error(f"Ошибка: {e}")
                time.sleep(10)


def main():
    """Точка входа"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Система мониторинга серверов')
    parser.add_argument('--mode', choices=['once', 'daemon'], default='once')
    parser.add_argument('--config', default='config/config.yaml')
    
    args = parser.parse_args()
    
    monitor = ServerMonitor(args.config)
    
    if args.mode == 'once':
        monitor.run_once()
    else:
        monitor.run_daemon()


if __name__ == '__main__':
    main()