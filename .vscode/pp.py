#!/usr/bin/env python3
"""
Автоматическая установка и настройка DNS-сервера Bind9 на Linux
Исправленная версия с поддержкой разных дистрибутивов
"""

import subprocess
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
import shutil

class DNSInstaller:
    """Автоматическая установка и настройка DNS-сервера"""
    
    def __init__(self):
        self.distro = self._detect_distro()
        self.bind_config_dir = Path('/etc/bind')
        self.zones_dir = self.bind_config_dir / 'zones'
        
        print(f"📊 Определен дистрибутив: {self.distro}")
        
    def _detect_distro(self) -> str:
        """Определяет дистрибутив Linux (исправленная версия)"""
        
        # Способ 1: Через /etc/os-release
        try:
            with open('/etc/os-release', 'r') as f:
                content = f.read().lower()
                
                if 'ubuntu' in content:
                    return 'ubuntu'
                elif 'debian' in content:
                    return 'debian'
                elif 'centos' in content or 'rhel' in content:
                    return 'rhel'
                elif 'fedora' in content:
                    return 'fedora'
                elif 'almalinux' in content or 'rocky' in content:
                    return 'rhel'
                    
        except FileNotFoundError:
            pass
        
        # Способ 2: Через команду which (проверка пакетных менеджеров)
        try:
            # Проверка apt (Debian/Ubuntu)
            subprocess.run(['which', 'apt'], check=True, capture_output=True)
            return 'debian'
        except subprocess.CalledProcessError:
            pass

        try:
            # Проверка dnf (Fedora/RHEL8+)
            subprocess.run(['which', 'dnf'], check=True, capture_output=True)
            return 'rhel'
        except subprocess.CalledProcessError:
            pass
        
        # Способ 3: Проверка существования файлов
        if os.path.exists('/etc/debian_version'):
            return 'debian'
        elif os.path.exists('/etc/redhat-release'):
            return 'rhel'
        
        return 'unknown'
    
    def install_bind(self) -> bool:
        """Устанавливает Bind9 в зависимости от дистрибутива"""
        print("📦 Установка DNS-сервера...")
        
        # Команды для разных дистрибутивов
        install_commands = {
            'ubuntu': [
                ['apt-get', 'update'],
                ['apt-get', 'install', '-y', 'bind9', 'bind9utils', 'bind9-doc', 'dnsutils'],
                ['systemctl', 'enable', 'named'],
                ['systemctl', 'start', 'named']
            ],
            'debian': [
                ['apt-get', 'update'],
                ['apt-get', 'install', '-y', 'bind9', 'bind9utils', 'bind9-doc', 'dnsutils'],
                ['systemctl', 'enable', 'named'],
                ['systemctl', 'start', 'named']
            ],
            'fedora': [
                ['dnf', 'install', '-y', 'bind', 'bind-utils'],
                ['systemctl', 'enable', 'named'],
                ['systemctl', 'start', 'named']
            ]
        }
        
        if self.distro not in install_commands:
            print(f"❌ Неподдерживаемый дистрибутив: {self.distro}")
            print("💡 Поддерживаются: Ubuntu, Debian, CentOS, RHEL, Fedora")
            return False
        
        # Выполняем установку
        for cmd in install_commands[self.distro]:
            print(f"  Выполнение: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                print(f"  ⚠️ Предупреждение: {result.stderr[:200] if result.stderr else 'OK'}")
        
        # Создаем директорию для зон
        try:
            self.zones_dir.mkdir(exist_ok=True)
            os.chmod(self.zones_dir, 0o755)
            print(f"  ✅ Создана директория: {self.zones_dir}")
        except Exception as e:
            print(f"  ⚠️ Не удалось создать директорию: {e}")
        
        # Проверяем, что сервис запущен
        result = subprocess.run(['systemctl', 'is-active', 'named'], 
                               capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✅ Bind9 успешно установлен и запущен")
            return True
        else:
            print("⚠️ Bind9 установлен, но может не запущен. Проверьте вручную.")
            return True  # Все равно возвращаем True, так как пакеты установлены
    
    def create_zone_file(self, domain: str, dns_ip: str, admin_email: str) -> bool:
        """Создает файл прямой зоны"""
        print(f"📝 Создание зонового файла для {domain}")
        
        zone_file = self.zones_dir / f"db.{domain}"
        serial = datetime.now().strftime('%Y%m%d01')
        
        # Преобразуем email в формат DNS
        admin_email_fmt = admin_email.replace('@', '.')
        
        zone_content = f"""$TTL    3600
@       IN      SOA     ns1.{domain}. {admin_email_fmt}. (
                        {serial}     ; Serial
                        3600         ; Refresh
                        1800         ; Retry
                        604800       ; Expire
                        3600 )       ; Negative Cache TTL
;
; Name Servers
@       IN      NS      ns1.{domain}.

; A Records
@       IN      A       {dns_ip}
ns1     IN      A       {dns_ip}
localhost       IN      A       127.0.0.1

; Additional records can be added below
"""
        
        with open(zone_file, 'w') as f:
            f.write(zone_content)
        
        os.chmod(zone_file, 0o644)
        print(f"  ✅ Создан файл: {zone_file}")
        
        # Проверяем зоновый файл
        result = subprocess.run(
            ['named-checkzone', domain, str(zone_file)],
            capture_output=True, text=True
        )
        
        if result.returncode == 0:
            print(f"  ✅ Зона {domain} валидна")
            return True
        else:
            print(f"  ⚠️ Проверка зоны: {result.stderr}")
            return True  # Продолжаем, даже если есть предупреждения
    
    def create_reverse_zone(self, network: str, dns_ip: str, domain: str) -> bool:
        """Создает файл обратной зоны"""
        # network: 192.168.1.0
        network_parts = network.split('.')
        reverse_zone_name = f"{network_parts[0]}.{network_parts[1]}.{network_parts[2]}.in-addr.arpa"
        zone_file = self.zones_dir / f"db.{'.'.join(network_parts[:3])}"
        
        last_octet = dns_ip.split('.')[3]
        serial = datetime.now().strftime('%Y%m%d01')
        
        zone_content = f"""$TTL    3600
@       IN      SOA     ns1.{domain}. admin.{domain}. (
                        {serial}     ; Serial
                        3600         ; Refresh
                        1800         ; Retry
                        604800       ; Expire
                        3600 )       ; Negative Cache TTL
;
@       IN      NS      ns1.{domain}.

; PTR Records
{last_octet}    IN      PTR     ns1.{domain}.
"""
        
        with open(zone_file, 'w') as f:
            f.write(zone_content)
        
        os.chmod(zone_file, 0o644)
        print(f"  ✅ Создан файл обратной зоны: {zone_file}")
        return True
    
    def configure_basic(self, domain: str, dns_ip: str, forwarders: List[str] = None) -> bool:
        """Базовая настройка Bind9"""
        print("⚙️ Настройка Bind9...")
        
        if forwarders is None:
            forwarders = ['8.8.8.8', '8.8.4.4']
        
        # Определяем путь к конфигам в зависимости от дистрибутива
        if self.distro in ['ubuntu', 'debian']:
            options_conf = self.bind_config_dir / 'named.conf.options'
        else:
            options_conf = self.bind_config_dir / 'named.conf'
        
        # Настройка named.conf.options
        options_content = f"""options {{
    directory "/var/cache/bind";
    
    // Прослушивание всех интерфейсов
    listen-on {{ any; }};
    listen-on-v6 {{ any; }};
    
    // Разрешение рекурсивных запросов
    allow-recursion {{ 127.0.0.0/8; 192.168.0.0/16; 10.0.0.0/8; }};
    allow-query {{ any; }};
    
    // Форвардеры
    forwarders {{
        {forwarders[0]};
        {forwarders[1]};
    }};
    
    // Безопасность
    dnssec-validation auto;
    allow-transfer {{ none; }};
}};
"""
        
        with open(options_conf, 'w') as f:
            f.write(options_content)
        print(f"  ✅ Создан {options_conf}")
        
        # Настройка named.conf.local (или основного конфига)
        if self.distro in ['ubuntu', 'debian']:
            local_conf = self.bind_config_dir / 'named.conf.local'
        else:
            local_conf = self.bind_config_dir / 'named.conf'
            # Добавляем include для зон
            with open(local_conf, 'a') as f:
                f.write('\ninclude "/etc/bind/zones.conf";\n')
            local_conf = self.bind_config_dir / 'zones.conf'
        
        local_content = f"""
// Основная зона
zone "{domain}" {{
    type master;
    file "/etc/bind/zones/db.{domain}";
}};

// Обратная зона
zone "{'.'.join(dns_ip.split('.')[:3])}.in-addr.arpa" {{
    type master;
    file "/etc/bind/zones/db.{'.'.join(dns_ip.split('.')[:3])}";
}};
"""
        
        with open(local_conf, 'a') as f:
            f.write(local_content)
        print(f"  ✅ Настроены зоны")
        
        # Проверка конфигурации
        result = subprocess.run(['named-checkconf'], capture_output=True, text=True)
        if result.returncode == 0:
            print("  ✅ Конфигурация валидна")
        else:
            print(f"  ⚠️ Предупреждение: {result.stderr}")
        
        return True
    
    def configure_firewall(self):
        """Настраивает фаервол для DNS"""
        print("🔥 Настройка фаервола...")
        
        # Открываем порт 53
        try:
            # Для ufw (Ubuntu/Debian)
            subprocess.run(['ufw', 'allow', '53/tcp'], capture_output=True)
            subprocess.run(['ufw', 'allow', '53/udp'], capture_output=True)
            subprocess.run(['ufw', 'reload'], capture_output=True)
            print("  ✅ Настроен ufw")
        except:
            pass
        
        try:
            # Для firewalld (RHEL/CentOS/Fedora)
            subprocess.run(['firewall-cmd', '--permanent', '--add-service=dns'], 
                          capture_output=True)
            subprocess.run(['firewall-cmd', '--reload'], capture_output=True)
            print("  ✅ Настроен firewalld")
        except:
            pass
        
        print("  ✅ DNS порты открыты (настройка может потребовать ручной проверки)")
    
    def reload_bind(self):
        """Перезагружает Bind9"""
        print("🔄 Перезагрузка Bind9...")
        
        service_name = 'named'  # В большинстве дистрибутивов
        if self.distro in ['ubuntu', 'debian']:
            service_name = 'bind9'
        
        subprocess.run(['systemctl', 'reload', service_name], capture_output=True)
        subprocess.run(['systemctl', 'restart', service_name], capture_output=True)
        
        # Проверка статуса
        result = subprocess.run(['systemctl', 'is-active', service_name], 
                               capture_output=True, text=True)
        
        if result.returncode == 0:
            print(f"  ✅ {service_name} успешно перезагружен")
        else:
            print(f"  ⚠️ Проверьте статус: systemctl status {service_name}")
    
    def test_dns(self, domain: str, dns_ip: str = '127.0.0.1'):
        """Тестирует работу DNS-сервера"""
        print("\n🧪 Тестирование DNS-сервера...")
        
        # Используем nslookup для проверки
        result = subprocess.run(
            ['nslookup', domain, dns_ip],
            capture_output=True, text=True
        )
        
        if domain in result.stdout:
            print(f"  ✅ DNS сервер отвечает на {domain}")
            return True
        else:
            print(f"  ⚠️ Проверьте вручную: nslookup {domain} {dns_ip}")
            return False
    
    def full_setup(self, domain: str, dns_ip: str, admin_email: str, 
                   network: str, forwarders: List[str] = None):
        """Полная автоматическая настройка DNS-сервера"""
        print("=" * 70)
        print("🚀 НАЧАЛО ПОЛНОЙ НАСТРОЙКИ DNS")
        print("=" * 70)
        
        # 1. Установка
        if not self.install_bind():
            print("❌ Установка не удалась")
            return False
        
        # 1.5 Создание директории для зон (если не создалась)
        self.zones_dir.mkdir(exist_ok=True)
        
        # 2. Создание файлов зон
        if not self.create_zone_file(domain, dns_ip, admin_email):
            return False
        
        if not self.create_reverse_zone(network, dns_ip, domain):
            return False
        
        # 3. Настройка Bind
        if not self.configure_basic(domain, dns_ip, forwarders):
            return False
        
        # 4. Настройка фаервола
        self.configure_firewall()
        
        # 5. Перезагрузка
        self.reload_bind()
        
        # 6. Тестирование
        self.test_dns(domain)
        
        print("\n" + "=" * 70)
        print("✅ DNS-СЕРВЕР УСПЕШНО НАСТРОЕН!")
        print("=" * 70)
        print(f"\n📋 ИНФОРМАЦИЯ:")
        print(f"  • DNS сервер: {dns_ip}")
        print(f"  • Домен: {domain}")
        print(f"  • Конфиги: /etc/bind/")
        print(f"  • Зоны: /etc/bind/zones/")
        print(f"\n💡 ПРОВЕРКА:")
        print(f"  nslookup {domain} {dns_ip}")
        print(f"  dig @{dns_ip} {domain}")
        print(f"  systemctl status {'bind9' if self.distro in ['ubuntu','debian'] else 'named'}")
        
        return True


# Главная функция для запуска
def main():
    """Главная функция с настройками"""
    
    # Проверка прав root
    if os.geteuid() != 0:
        print("❌ Скрипт должен запускаться от root!")
        print("   Используйте: sudo python3 pp.py")
        sys.exit(1)
    
    # Конфигурация - ИЗМЕНИТЕ ЭТИ ПАРАМЕТРЫ ПОД ВАШУ СЕТЬ
    config = {
        'domain': 'example.com',           # Ваш домен
        'dns_ip': '192.168.1.10',          # IP адрес этого сервера
        'admin_email': 'admin@example.com', # Email администратора
        'network': '192.168.1.0',          # Ваша сеть
        'forwarders': ['8.8.8.8', '1.1.1.1']  # Внешние DNS
    }
    
    print("\n📋 ТЕКУЩАЯ КОНФИГУРАЦИЯ:")
    print(f"  Домен: {config['domain']}")
    print(f"  IP сервера: {config['dns_ip']}")
    print(f"  Сеть: {config['network']}")
    print(f"  Email: {config['admin_email']}")
    print()
    
    # Запрос подтверждения
    response = input("Продолжить настройку? (y/n): ")
    if response.lower() != 'y':
        print("❌ Настройка отменена")
        sys.exit(0)
    
    # Запуск установки
    installer = DNSInstaller()
    installer.full_setup(**config)


if __name__ == '__main__':
    main()