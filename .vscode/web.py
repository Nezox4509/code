#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для обнаружения всех устройств в локальной сети
Выводит IP-адреса, MAC-адреса и имена устройств
"""

import subprocess
import ipaddress
import socket
import threading
import time
from datetime import datetime

class NetworkScanner:
    """Класс для сканирования сети и обнаружения устройств"""
    
    def __init__(self):
        self.devices = []
        self.network = None
        
    def get_network_info(self):
        """Получение информации о сети (IP и маска)"""
        try:
            # Получаем IP и маску через ip команду
            result = subprocess.run(
                ['ip', '-4', 'addr', 'show'],
                capture_output=True,
                text=True
            )
            
            for line in result.stdout.split('\n'):
                if 'inet ' in line and 'scope global' in line:
                    # Извлекаем IP и маску
                    parts = line.strip().split()
                    ip_with_mask = parts[1]
                    
                    # Определяем сеть
                    network = ipaddress.ip_network(ip_with_mask, strict=False)
                    return network
                    
        except Exception as e:
            print(f"❌ Ошибка получения информации о сети: {e}")
            return None
    
    def ping_host(self, ip):
        """Пинг одного хоста"""
        try:
            # Для Linux
            result = subprocess.run(
                ['ping', '-c', '1', '-W', '1', str(ip)],
                capture_output=True,
                text=True,
                timeout=2
            )
            return result.returncode == 0
        except:
            return False
    
    def get_hostname(self, ip):
        """Получение имени хоста по IP"""
        try:
            hostname = socket.gethostbyaddr(str(ip))[0]
            return hostname
        except:
            return "Unknown"
    
    def get_mac_address(self, ip):
        """Получение MAC-адреса по IP через ARP таблицу"""
        try:
            result = subprocess.run(
                ['arp', '-n', str(ip)],
                capture_output=True,
                text=True
            )
            
            for line in result.stdout.split('\n'):
                if str(ip) in line:
                    parts = line.split()
                    if len(parts) >= 3:
                        mac = parts[2]
                        if mac != 'incomplete':
                            return mac
        except:
            pass
        return "N/A"
    
    def scan_network(self, network=None):
        """Сканирование всей сети"""
        if network is None:
            network = self.get_network_info()
        
        if network is None:
            print("❌ Не удалось определить сеть")
            return []
        
        print(f"\n🔍 Сканирование сети: {network}")
        print(f"📡 Диапазон IP: {network.network_address} - {network.broadcast_address}")
        print(f"📊 Всего адресов: {network.num_addresses}")
        print("\n⏳ Сканирование... (это может занять некоторое время)\n")
        
        self.devices = []
        threads = []
        
        # Сканируем все IP в сети (исключая сетевой и широковещательный)
        for ip in network.hosts():
            thread = threading.Thread(target=self.scan_host, args=(ip,))
            thread.start()
            threads.append(thread)
            
            # Ограничиваем количество потоков
            if len(threads) >= 100:
                for t in threads:
                    t.join()
                threads = []
        
        # Ждем завершения всех потоков
        for t in threads:
            t.join()
        
        return self.devices
    
    def scan_host(self, ip):
        """Сканирование одного хоста"""
        if self.ping_host(ip):
            hostname = self.get_hostname(ip)
            mac = self.get_mac_address(ip)
            
            device = {
                'ip': str(ip),
                'hostname': hostname,
                'mac': mac,
                'status': 'online'
            }
            self.devices.append(device)
            
            # Выводим результат сразу
            print(f"✅ Найдено: {ip:15} | {hostname:30} | {mac}")
    
    def print_results(self):
        """Вывод результатов сканирования"""
        if not self.devices:
            print("\n❌ Устройства не найдены")
            return
        
        print("\n" + "="*80)
        print(f"📊 РЕЗУЛЬТАТЫ СКАНИРОВАНИЯ")
        print("="*80)
        print(f"📅 Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"📡 Найдено устройств: {len(self.devices)}")
        print("-"*80)
        print(f"{'№':<3} {'IP АДРЕС':<15} {'ИМЯ ХОСТА':<30} {'MAC АДРЕС':<18}")
        print("-"*80)
        
        for i, device in enumerate(self.devices, 1):
            print(f"{i:<3} {device['ip']:<15} {device['hostname']:<30} {device['mac']:<18}")
        
        print("="*80)
    
    def save_to_file(self, filename=None):
        """Сохранение результатов в файл"""
        if filename is None:
            filename = f"network_scan_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write("РЕЗУЛЬТАТЫ СКАНИРОВАНИЯ СЕТИ\n")
            f.write("="*80 + "\n")
            f.write(f"Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Найдено устройств: {len(self.devices)}\n")
            f.write("-"*80 + "\n")
            f.write(f"{'IP АДРЕС':<15} {'ИМЯ ХОСТА':<30} {'MAC АДРЕС':<18}\n")
            f.write("-"*80 + "\n")
            
            for device in self.devices:
                f.write(f"{device['ip']:<15} {device['hostname']:<30} {device['mac']:<18}\n")
        
        print(f"\n💾 Результаты сохранены в файл: {filename}")
        return filename

def main():
    """Основная функция"""
    print("="*60)
    print("🔍 СКАНЕР СЕТИ - ПОИСК УСТРОЙСТВ")
    print("="*60)
    
    scanner = NetworkScanner()
    
    # Определяем сеть
    network = scanner.get_network_info()
    
    if network:
        print(f"\n✅ Определена сеть: {network}")
        
        # Сканируем
        devices = scanner.scan_network(network)
        
        # Выводим результаты
        scanner.print_results()
        
        # Сохраняем в файл
        scanner.save_to_file()
        
        # Показываем статистику
        print(f"\n📊 Статистика:")
        print(f"   Всего IP в сети: {network.num_addresses}")
        print(f"   Активных устройств: {len(devices)}")
        print(f"   Процент активности: {len(devices)/network.num_addresses*100:.1f}%")
        
    else:
        print("\n❌ Не удалось определить сеть")
        print("Проверьте подключение к сети")

if __name__ == "__main__":
    main()