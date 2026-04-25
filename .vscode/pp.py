#!/usr/bin/env python3
"""
monitor.py - Система мониторинга серверов для Linux
Собирает метрики: CPU, RAM, HDD, Network, процессы
"""

import os
import sys
import json
import time
import socket
import subprocess
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/monitor.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class SystemMonitor:
    """Мониторинг состояния системы"""
    
    def __init__(self):
        self.hostname = socket.gethostname()
        self.create_dirs()
    
    def create_dirs(self):
        """Создание директорий"""
        Path('/opt/monitor/logs').mkdir(parents=True, exist_ok=True)
        Path('/opt/monitor/data').mkdir(parents=True, exist_ok=True)
        Path('/opt/monitor/reports').mkdir(parents=True, exist_ok=True)
    
    def get_cpu(self) -> Dict:
        """Получение метрик CPU"""
        try:
            with open('/proc/stat', 'r') as f:
                line = f.readline()
            
            parts = line.split()
            user = int(parts[1])
            nice = int(parts[2])
            system = int(parts[3])
            idle = int(parts[4])
            iowait = int(parts[5])
            
            total = user + nice + system + idle + iowait
            busy = total - idle - iowait
            percent = round((busy / total) * 100, 1) if total > 0 else 0
            
            with open('/proc/loadavg', 'r') as f:
                load = f.read().split()
            
            return {
                'percent': percent,
                'cores': os.cpu_count(),
                'load_1min': float(load[0]),
                'load_5min': float(load[1]),
                'load_15min': float(load[2])
            }
        except Exception as e:
            logger.error(f"CPU error: {e}")
            return {'percent': 0, 'cores': 1, 'load_1min': 0, 'load_5min': 0, 'load_15min': 0}
    
    def get_memory(self) -> Dict:
        """Получение метрик памяти"""
        try:
            with open('/proc/meminfo', 'r') as f:
                mem = {}
                for line in f:
                    parts = line.split(':')
                    if len(parts) == 2:
                        mem[parts[0]] = int(parts[1].split()[0])
            
            total = mem.get('MemTotal', 0) / 1024 / 1024
            available = mem.get('MemAvailable', 0) / 1024 / 1024
            used = total - available
            percent = round((used / total) * 100, 1) if total > 0 else 0
            
            return {
                'total_gb': round(total, 2),
                'used_gb': round(used, 2),
                'free_gb': round(available, 2),
                'percent': percent
            }
        except Exception as e:
            logger.error(f"Memory error: {e}")
            return {'total_gb': 0, 'used_gb': 0, 'free_gb': 0, 'percent': 0}
    
    def get_disks(self) -> List[Dict]:
        """Получение метрик дисков"""
        disks = []
        try:
            result = subprocess.run(['df', '-h'], capture_output=True, text=True)
            lines = result.stdout.strip().split('\n')[1:]
            
            for line in lines:
                parts = line.split()
                if len(parts) >= 6:
                    disks.append({
                        'device': parts[0],
                        'size': parts[1],
                        'used': parts[2],
                        'available': parts[3],
                        'percent': int(parts[4].replace('%', '')),
                        'mount': parts[5]
                    })
        except Exception as e:
            logger.error(f"Disks error: {e}")
        
        return disks
    
    def get_network(self) -> Dict:
        """Получение сетевых метрик"""
        try:
            with open('/proc/net/dev', 'r') as f:
                lines = f.readlines()[2:]
            
            rx = 0
            tx = 0
            
            for line in lines:
                parts = line.split(':')
                if len(parts) >= 2 and parts[0].strip() != 'lo':
                    stats = parts[1].split()
                    rx += int(stats[0])
                    tx += int(stats[8])
            
            return {
                'rx_mb': round(rx / 1024 / 1024, 2),
                'tx_mb': round(tx / 1024 / 1024, 2)
            }
        except Exception as e:
            logger.error(f"Network error: {e}")
            return {'rx_mb': 0, 'tx_mb': 0}
    
    def get_top_processes(self, limit: int = 5) -> List[Dict]:
        """Получение топ процессов по CPU"""
        processes = []
        try:
            result = subprocess.run(
                ['ps', 'aux', '--sort=-%cpu', '--no-headers'],
                capture_output=True, text=True
            )
            lines = result.stdout.strip().split('\n')[:limit]
            
            for line in lines:
                parts = line.split(None, 10)
                if len(parts) >= 11:
                    processes.append({
                        'user': parts[0],
                        'pid': int(parts[1]),
                        'cpu': float(parts[2]),
                        'mem': float(parts[3]),
                        'command': parts[10][:50]
                    })
        except Exception as e:
            logger.error(f"Processes error: {e}")
        
        return processes
    
    def get_uptime(self) -> str:
        """Получение времени работы"""
        try:
            with open('/proc/uptime', 'r') as f:
                seconds = float(f.read().split()[0])
            
            days = int(seconds // 86400)
            hours = int((seconds % 86400) // 3600)
            minutes = int((seconds % 3600) // 60)
            
            return f"{days}д {hours}ч {minutes}м"
        except:
            return "N/A"
    
    def check_alerts(self, cpu: float, mem: float, disk: int) -> List[Dict]:
        """Проверка пороговых значений"""
        alerts = []
        
        if cpu > 90:
            alerts.append({'level': 'CRITICAL', 'type': 'CPU', 'value': cpu})
        elif cpu > 80:
            alerts.append({'level': 'WARNING', 'type': 'CPU', 'value': cpu})
        
        if mem > 95:
            alerts.append({'level': 'CRITICAL', 'type': 'MEMORY', 'value': mem})
        elif mem > 85:
            alerts.append({'level': 'WARNING', 'type': 'MEMORY', 'value': mem})
        
        for d in self.get_disks():
            if d['mount'] == '/' and d['percent'] > 90:
                alerts.append({'level': 'CRITICAL', 'type': 'DISK', 'value': d['percent']})
            elif d['mount'] == '/' and d['percent'] > 80:
                alerts.append({'level': 'WARNING', 'type': 'DISK', 'value': d['percent']})
        
        return alerts
    
    def collect(self) -> Dict:
        """Сбор всех метрик"""
        cpu = self.get_cpu()
        memory = self.get_memory()
        disks = self.get_disks()
        network = self.get_network()
        
        main_disk = next((d for d in disks if d['mount'] == '/'), {'percent': 0})
        alerts = self.check_alerts(cpu['percent'], memory['percent'], main_disk['percent'])
        
        status = 'CRITICAL' if any(a['level'] == 'CRITICAL' for a in alerts) \
            else 'WARNING' if alerts else 'OK'
        
        metrics = {
            'timestamp': datetime.now().isoformat(),
            'hostname': self.hostname,
            'status': status,
            'cpu': cpu,
            'memory': memory,
            'disks': disks,
            'network': network,
            'top_processes': self.get_top_processes(),
            'uptime': self.get_uptime(),
            'alerts': alerts
        }
        
        return metrics
    
    def save(self, metrics: Dict):
        """Сохранение метрик в файл"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Сохранение JSON
        json_file = f"/opt/monitor/data/metrics_{timestamp}.json"
        with open(json_file, 'w') as f:
            json.dump(metrics, f, indent=2)
        
        # Сохранение отчета
        report_file = f"/opt/monitor/reports/report_{timestamp}.txt"
        with open(report_file, 'w') as f:
            f.write(self.format_report(metrics))
        
        logger.info(f"Metrics saved to {json_file}")
        
        # Ротация старых файлов
        self.rotate_files('/opt/monitor/data', days=30)
        self.rotate_files('/opt/monitor/reports', days=30)
    
    def format_report(self, metrics: Dict) -> str:
        """Форматирование отчета"""
        report = []
        report.append("=" * 70)
        report.append(f"📊 СИСТЕМНЫЙ МОНИТОРИНГ - {metrics['hostname']}")
        report.append(f"📅 {metrics['timestamp']}")
        report.append(f"🔴 СТАТУС: {metrics['status']}")
        report.append("=" * 70)
        
        # CPU
        cpu = metrics['cpu']
        report.append(f"\n💻 CPU:")
        report.append(f"   Загрузка: {cpu['percent']}%")
        report.append(f"   Ядра: {cpu['cores']}")
        report.append(f"   Load: {cpu['load_1min']}, {cpu['load_5min']}, {cpu['load_15min']}")
        
        # Память
        mem = metrics['memory']
        report.append(f"\n🧠 ПАМЯТЬ:")
        report.append(f"   Всего: {mem['total_gb']} GB")
        report.append(f"   Использовано: {mem['used_gb']} GB ({mem['percent']}%)")
        report.append(f"   Свободно: {mem['free_gb']} GB")
        
        # Диски
        report.append(f"\n💾 ДИСКИ:")
        for disk in metrics['disks']:
            if disk['percent'] > 85:
                icon = "🔴"
            elif disk['percent'] > 70:
                icon = "🟡"
            else:
                icon = "🟢"
            report.append(f"   {icon} {disk['mount']}: {disk['used']} / {disk['size']} ({disk['percent']}%)")
        
        # Сеть
        net = metrics['network']
        report.append(f"\n🌐 СЕТЬ:")
        report.append(f"   RX: {net['rx_mb']} MB")
        report.append(f"   TX: {net['tx_mb']} MB")
        
        # Процессы
        report.append(f"\n📈 ТОП ПРОЦЕССОВ:")
        for proc in metrics['top_processes']:
            report.append(f"   {proc['command'][:40]} - CPU: {proc['cpu']}% MEM: {proc['mem']}%")
        
        # Алерты
        if metrics['alerts']:
            report.append(f"\n⚠️ АКТИВНЫЕ АЛЕРТЫ:")
            for alert in metrics['alerts']:
                report.append(f"   [{alert['level']}] {alert['type']}: {alert['value']}%")
        
        report.append("\n" + "=" * 70)
        
        return "\n".join(report)
    
    def rotate_files(self, directory: str, days: int):
        """Ротация старых файлов"""
        cutoff = time.time() - (days * 86400)
        for file in Path(directory).glob('*'):
            if file.stat().st_mtime < cutoff:
                file.unlink()
                logger.info(f"Deleted old file: {file}")
    
    def run_once(self):
        """Однократный запуск"""
        metrics = self.collect()
        self.save(metrics)
        print(self.format_report(metrics))
        return metrics
    
    def run_daemon(self, interval: int = 60):
        """Запуск в режиме демона"""
        logger.info(f"Starting monitor daemon, interval={interval}s")
        
        try:
            while True:
                self.run_once()
                time.sleep(interval)
        except KeyboardInterrupt:
            logger.info("Monitor stopped")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='System Monitor')
    parser.add_argument('--mode', choices=['once', 'daemon'], default='once')
    parser.add_argument('--interval', type=int, default=60)
    
    args = parser.parse_args()
    
    # Проверка прав
    if os.geteuid() != 0:
        print("Warning: Some metrics may require root privileges")
    
    monitor = SystemMonitor()
    
    if args.mode == 'once':
        monitor.run_once()
    else:
        monitor.run_daemon(args.interval)


if __name__ == '__main__':
    main()