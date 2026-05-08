#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для обнаружения всех устройств в локальной сети
Выводит IP-адреса, MAC-адреса, имена устройств и их тип
"""

import subprocess
import ipaddress
import socket
import threading
import time
from datetime import datetime
import re

class NetworkScanner:
    """Класс для сканирования сети и обнаружения устройств"""
    
    def __init__(self):
        self.devices = []
        self.network = None
        
        # База OUI для определения производителя по MAC
        self.oui_database = self.load_oui_database()
        
        # Известные порты для определения типа устройства
        self.service_ports = {
            22: 'ssh', 20: 'ftp', 21: 'ftp', 23: 'telnet',
            80: 'http', 443: 'https', 445: 'smb', 3389: 'rdp',
            5900: 'vnc', 8080: 'http-alt', 8443: 'https-alt'
        }
        
    def load_oui_database(self):
        """Загрузка базы OUI (производителей по MAC)"""
        # Сокращенная база OUI
        return {
            '00:00:0C': 'Cisco',
            '00:01:42': 'Juniper',
            '00:01:97': 'Huawei',
            '00:0C:29': 'VMware',
            '00:14:22': 'Dell',
            '00:15:5D': 'Hyper-V',
            '00:1B:21': 'Sony',
            '00:1E:C2': 'Apple',
            '00:25:9C': 'HP',
            '08:00:27': 'VirtualBox',
            '10:DD:B1': 'Apple',
            '28:D2:44': 'Apple',
            '34:36:3B': 'Raspberry Pi',
            '40:32:A8': 'Realtek',
            '44:65:0D': 'Samsung',
            '50:2B:73': 'Intel',
            '52:54:00': 'QEMU',
            '64:D1:A3': 'Xiaomi',
            '70:5E:AC': 'TP-Link',
            '7C:2E:BD': 'Google',
            '84:1B:77': 'Sony',
            '8C:29:37': 'Intel',
            '90:9F:33': 'Microsoft',
            '94:DE:80': 'Asus',
            'A4:AE:12': 'Huawei',
            'B4:6D:83': 'Ubiquiti',
            'BC:5F:F4': 'Acer',
            'C0:25:E9': 'Zyxel',
            'C8:FF:28': 'D-Link',
            'CC:46:FE': 'Epson',
            'D0:17:C2': 'Buffalo',
            'D4:3B:8E': 'Atheros',
            'E0:D5:5E': 'ASIX',
            'EC:1A:59': 'Dell',
            'F0:4D:A2': 'Samsung',
            'F8:95:EA': 'Intel'
        }
    
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
                        if mac != 'incomplete' and re.match(r'([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})', mac):
                            return mac
        except:
            pass
        return "N/A"
    
    def get_manufacturer(self, mac):
        """Определение производителя по MAC адресу"""
        if mac == "N/A":
            return "Unknown"
        
        mac_upper = mac.upper()
        for oui, manufacturer in self.oui_database.items():
            if mac_upper.startswith(oui):
                return manufacturer
        
        return "Unknown"
    
    def scan_ports(self, ip, ports=[22, 80, 443, 445, 3389]):
        """Быстрое сканирование портов для определения типа устройства"""
        open_ports = []
        
        for port in ports:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(0.5)
                result = sock.connect_ex((str(ip), port))
                if result == 0:
                    service = self.service_ports.get(port, f'port{port}')
                    open_ports.append({'port': port, 'service': service})
                sock.close()
            except:
                pass
        
        return open_ports
    
    def detect_device_type(self, hostname, mac, open_ports, manufacturer):
        """Определение типа устройства на основе различных признаков"""
        
        # Приоритет определения по типу (сначала специфичные признаки)
        
        hostname_lower = hostname.lower()
        mac_lower = mac.lower()
        
        # 1. Маршрутизаторы и сетевые устройства
        router_keywords = ['router', 'routeros', 'mikrotik', 'routerboard', 'gateway', 'ap', 'accesspoint', 'wifi']
        switch_keywords = ['switch', 'cisco', 'juniper', 'huawei', 'zte', 'dlink', 'tplink']
        
        for keyword in router_keywords:
            if keyword in hostname_lower:
                return "🔄 Маршрутизатор", "\033[94m"
        
        for keyword in switch_keywords:
            if keyword in hostname_lower:
                return "🔌 Сетевой коммутатор", "\033[94m"
        
        # 2. IoT устройства и умный дом
        iot_keywords = ['raspberry', 'rpi', 'homeassistant', 'hass', 'smart', 'sensor', 'camera', 'ipcam']
        for keyword in iot_keywords:
            if keyword in hostname_lower:
                return "📷 IoT устройство", "\033[95m"
        
        # 3. Принтеры и МФУ
        printer_keywords = ['printer', 'print', 'hp', 'canon', 'epson', 'brother', 'kyocera', 'xerox']
        for keyword in printer_keywords:
            if keyword in hostname_lower:
                return "🖨️ Принтер/МФУ", "\033[96m"
        
        # 4. Медиаустройства
        media_keywords = ['tv', 'samsungtv', 'lgtv', 'sony', 'chromecast', 'apple tv', 'roku', 'firetv']
        for keyword in media_keywords:
            if keyword in hostname_lower:
                return "📺 Медиаплеер/TV", "\033[95m"
        
        # 5. Анализ портов
        if open_ports:
            services = [p['service'] for p in open_ports]
            services_str = ' '.join(services)
            
            # Серверные порты
            if 'smb' in services_str or 'ssh' in services_str and 'http' in services_str:
                return "🖥️ Сервер", "\033[92m"
            
            # Веб-сервер
            if 'http' in services_str and len(open_ports) >= 2:
                return "🌐 Веб-сервер", "\033[92m"
            
            # Рабочая станция
            if 'rdp' in services_str or 'vnc' in services_str:
                return "💻 Рабочая станция", "\033[93m"
        
        # 6. Определение по производителю
        manufacturer_lower = manufacturer.lower()
        
        if manufacturer == "VMware" or manufacturer == "Hyper-V" or manufacturer == "VirtualBox" or manufacturer == "QEMU":
            return "🖥️ Виртуальная машина", "\033[93m"
        
        if manufacturer in ["Cisco", "Juniper", "Huawei", "TP-Link", "D-Link", "Zyxel", "Ubiquiti"]:
            return "🔌 Сетевое устройство", "\033[94m"
        
        if manufacturer in ["Raspberry Pi"]:
            return "🥧 Raspberry Pi", "\033[95m"
        
        if manufacturer in ["Apple"]:
            return "🍎 Mac/iDevice", "\033[93m"
        
        # 7. По умолчанию - ПК или неизвестное устройство
        # Попытка определить по имени хоста
        if any(word in hostname_lower for word in ['pc', 'desktop', 'workstation', 'win']):
            return "💻 Персональный компьютер", "\033[93m"
        
        if any(word in hostname_lower for word in ['laptop', 'notebook', 'thinkpad', 'latitude']):
            return "💻 Ноутбук", "\033[93m"
        
        if any(word in hostname_lower for word in ['server', 'srv', 'nas', 'storage']):
            return "🖥️ Сервер/Хранилище", "\033[92m"
        
        # 8. Мобильные устройства (обычно имеют специфические имена)
        mobile_keywords = ['iphone', 'ipad', 'android', 'galaxy', 'mi', 'redmi', 'pixel']
        for keyword in mobile_keywords:
            if keyword in hostname_lower:
                return "📱 Мобильное устройство", "\033[96m"
        
        return "🔍 Неизвестное устройство", "\033[90m"
    
    def get_device_icon(self, device_type):
        """Получение иконки для типа устройства"""
        icons = {
            "Маршрутизатор": "🔄",
            "Сетевой коммутатор": "🔌",
            "Сетевое устройство": "🔌",
            "Сервер": "🖥️",
            "Веб-сервер": "🌐",
            "Сервер/Хранилище": "🖥️",
            "Рабочая станция": "💻",
            "Персональный компьютер": "💻",
            "Ноутбук": "💻",
            "Виртуальная машина": "🖥️",
            "Mac/iDevice": "🍎",
            "Raspberry Pi": "🥧",
            "Медиаплеер/TV": "📺",
            "Принтер/МФУ": "🖨️",
            "Мобильное устройство": "📱",
            "IoT устройство": "📷",
            "Неизвестное устройство": "🔍"
        }
        
        for key, icon in icons.items():
            if key in device_type:
                return icon
        return "🔌"
    
    def scan_network(self, network=None, scan_ports=False):
        """Сканирование всей сети"""
        if network is None:
            network = self.get_network_info()
        
        if network is None:
            print("❌ Не удалось определить сеть")
            return []
        
        print(f"\n🔍 Сканирование сети: {network}")
        print(f"📡 Диапазон IP: {network.network_address} - {network.broadcast_address}")
        print(f"📊 Всего адресов: {network.num_addresses}")
        print(f"{'🔍 Сканирование портов:' if scan_ports else ''}")
        print("\n⏳ Сканирование... (это может занять некоторое время)\n")
        
        self.devices = []
        threads = []
        
        # Сканируем все IP в сети (исключая сетевой и широковещательный)
        for ip in network.hosts():
            thread = threading.Thread(target=self.scan_host, args=(ip, scan_ports))
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
        
        # Сортируем устройства по IP
        self.devices.sort(key=lambda x: ipaddress.ip_address(x['ip']))
        
        return self.devices
    
    def scan_host(self, ip, scan_ports=False):
        """Сканирование одного хоста"""
        if self.ping_host(ip):
            hostname = self.get_hostname(ip)
            mac = self.get_mac_address(ip)
            manufacturer = self.get_manufacturer(mac)
            
            device = {
                'ip': str(ip),
                'hostname': hostname,
                'mac': mac,
                'manufacturer': manufacturer,
                'status': 'online'
            }
            
            # Сканирование портов если нужно
            if scan_ports:
                open_ports = self.scan_ports(ip)
                device['open_ports'] = open_ports
            else:
                device['open_ports'] = []
            
            # Определяем тип устройства
            device_type, color = self.detect_device_type(
                hostname, mac, device['open_ports'], manufacturer
            )
            device['type'] = device_type
            device['color'] = color
            
            self.devices.append(device)
            
            # Выводим результат сразу
            icon = self.get_device_icon(device_type)
            print(f"{color}✅ {icon} {ip:15} | {hostname:30} | {device_type:20} | {manufacturer:12} | {mac}{color}")
    
    def print_results(self):
        """Вывод результатов сканирования"""
        if not self.devices:
            print("\n❌ Устройства не найдены")
            return
        
        print("\n" + "="*110)
        print(f"📊 РЕЗУЛЬТАТЫ СКАНИРОВАНИЯ СЕТИ")
        print("="*110)
        print(f"📅 Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"📡 Найдено устройств: {len(self.devices)}")
        
        # Группировка по типам устройств
        devices_by_type = {}
        for device in self.devices:
            device_type = device['type']
            if device_type not in devices_by_type:
                devices_by_type[device_type] = []
            devices_by_type[device_type].append(device)
        
        print(f"\n📋 РАСПРЕДЕЛЕНИЕ ПО ТИПАМ:")
        print("-"*110)
        for device_type, devices in sorted(devices_by_type.items()):
            icon = self.get_device_icon(device_type)
            print(f"   {icon} {device_type}: {len(devices)} устройств")
        
        print("\n" + "-"*110)
        print(f"{'№':<3} {'IP АДРЕС':<15} {'ИМЯ ХОСТА':<30} {'ТИП УСТРОЙСТВА':<25} {'ПРОИЗВОДИТЕЛЬ':<15} {'MAC АДРЕС':<18}")
        print("-"*110)
        
        for i, device in enumerate(self.devices, 1):
            icon = self.get_device_icon(device['type'])
            print(f"{i:<3} {device['ip']:<15} {device['hostname']:<30} {icon} {device['type']:<22} {device['manufacturer']:<15} {device['mac']:<18}")
        
        print("="*110)
        
        # Дополнительная информация о портах (если есть)
        devices_with_ports = [d for d in self.devices if d.get('open_ports')]
        if devices_with_ports:
            print(f"\n🔌 ДЕТАЛИ ПОРТОВ:")
            print("-"*110)
            for device in devices_with_ports[:10]:  # Показываем первые 10
                if device['open_ports']:
                    ports_str = ', '.join([f"{p['port']}({p['service']})" for p in device['open_ports']])
                    print(f"   {device['hostname']:30} → Открытые порты: {ports_str}")
    
    def save_to_file(self, filename=None):
        """Сохранение результатов в файл"""
        if filename is None:
            filename = f"network_scan_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write("="*100 + "\n")
            f.write("РЕЗУЛЬТАТЫ СКАНИРОВАНИЯ СЕТИ\n")
            f.write("="*100 + "\n")
            f.write(f"Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Найдено устройств: {len(self.devices)}\n")
            
            # Группировка по типам
            devices_by_type = {}
            for device in self.devices:
                device_type = device['type']
                if device_type not in devices_by_type:
                    devices_by_type[device_type] = []
                devices_by_type[device_type].append(device)
            
            f.write("\nРАСПРЕДЕЛЕНИЕ ПО ТИПАМ:\n")
            f.write("-"*100 + "\n")
            for device_type, devices in sorted(devices_by_type.items()):
                f.write(f"   {device_type}: {len(devices)} устройств\n")
            
            f.write("\n" + "-"*100 + "\n")
            f.write(f"{'IP АДРЕС':<15} {'ИМЯ ХОСТА':<35} {'ТИП УСТРОЙСТВА':<30} {'ПРОИЗВОДИТЕЛЬ':<15} {'MAC АДРЕС':<18}\n")
            f.write("-"*100 + "\n")
            
            for device in self.devices:
                f.write(f"{device['ip']:<15} {device['hostname']:<35} {device['type']:<30} {device['manufacturer']:<15} {device['mac']:<18}\n")
            
            # Детали портов
            devices_with_ports = [d for d in self.devices if d.get('open_ports')]
            if devices_with_ports:
                f.write("\n" + "="*100 + "\n")
                f.write("ДЕТАЛИ ПОРТОВ:\n")
                f.write("-"*100 + "\n")
                for device in devices_with_ports:
                    if device['open_ports']:
                        ports_str = ', '.join([f"{p['port']}({p['service']})" for p in device['open_ports']])
                        f.write(f"{device['hostname']:<35} → {ports_str}\n")
        
        print(f"\n💾 Результаты сохранены в файл: {filename}")
        
        # Также сохраняем в JSON для машинной обработки
        json_filename = filename.replace('.txt', '.json')
        import json
        with open(json_filename, 'w', encoding='utf-8') as f:
            json.dump(self.devices, f, indent=2, ensure_ascii=False)
        print(f"💾 JSON версия сохранена в файл: {json_filename}")
        
        return filename

def main():
    """Основная функция"""
    print("="*70)
    print("🔍 СКАНЕР СЕТИ - ПОИСК УСТРОЙСТВ С ОПРЕДЕЛЕНИЕМ ТИПА")
    print("="*70)
    
    scanner = NetworkScanner()
    
    # Определяем сеть
    network = scanner.get_network_info()
    
    if network:
        print(f"\n✅ Определена сеть: {network}")
        
        # Спрашиваем о глубоком сканировании
        print("\nВыберите режим сканирования:")
        print("  1. Быстрое сканирование (только обнаружение устройств)")
        print("  2. Полное сканирование (+ определение открытых портов)")
        
        choice = input("\nВаш выбор (1/2 по умолчанию 1): ").strip()
        scan_ports = choice == '2'
        
        # Сканируем
        devices = scanner.scan_network(network, scan_ports=scan_ports)
        
        # Выводим результаты
        scanner.print_results()
        
        # Сохраняем в файл
        scanner.save_to_file()
        
        # Показываем статистику
        print(f"\n📊 Статистика:")
        print(f"   Всего IP в сети: {network.num_addresses}")
        print(f"   Найдено устройств: {len(devices)}")
        print(f"   Процент активности: {len(devices)/network.num_addresses*100:.1f}%")
        
        # Показываем ТОП производителей
        manufacturers = {}
        for device in devices:
            manuf = device['manufacturer']
            if manuf != "Unknown":
                manufacturers[manuf] = manufacturers.get(manuf, 0) + 1
        
        if manufacturers:
            print(f"\n🏭 ТОП производителей:")
            for manuf, count in sorted(manufacturers.items(), key=lambda x: x[1], reverse=True)[:5]:
                print(f"   {manuf}: {count} устройств")
        
    else:
        print("\n❌ Не удалось определить сеть")
        print("Проверьте подключение к сети")

if __name__ == "__main__":
    main()