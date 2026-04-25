#!/usr/bin/env python3
"""
Автоматическая установка и настройка DNS-сервера Bind9 на Linux
"""

import subprocess
import os
import re
from pathlib import Path
from typing import Dict, List, Optional
import shutil

class DNSInstaller:
    """Автоматическая установка и настройка DNS-сервера"""
    
    def __init__(self):
        self.distro = self._detect_distro()
        self.bind_config_dir = Path('/etc/bind')
        self.zones_dir = self.bind_config_dir / 'zones'
        
    def _detect_distro(self) -> str:
        """Определяет дистрибутив Linux"""
        with open('/etc/os-release', 'r') as f:
            content = f.read()
            if 'ubuntu' in content.lower():
                return 'ubuntu'
            elif 'debian' in content.lower():
                return 'debian'
            elif 'centos' in content.lower() or 'rhel' in content.lower():
                return 'rhel'
        return 'unknown'
    
    def install_bind(self) -> bool:
        """Устанавливает Bind9 в зависимости от дистрибутива"""
        print("📦 Установка DNS-сервера...")
        
        if self.distro in ['ubuntu', 'debian']:
            commands = [
                'apt-get update',
                'apt-get install -y bind9 bind9utils bind9-doc dnsutils',
                'systemctl enable named',
                'systemctl start named'
            ]
        elif self.distro == 'rhel':
            commands = [
                'yum install -y bind bind-utils',
                'systemctl enable named',
                'systemctl start named'
            ]
        else:
            print("❌ Неподдерживаемый дистрибутив")
            return False
        
        for cmd in commands:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            if result.returncode != 0:
                print(f"❌ Ошибка: {cmd}")
                print(result.stderr)
                return False
            print(f"  ✅ {cmd}")
        
        # Создаем директорию для зон
        self.zones_dir.mkdir(exist_ok=True)
        os.chmod(self.zones_dir, 0o755)
        
        print("✅ Bind9 успешно установлен")
        return True
    
    def configure_basic(self, domain: str, dns_ip: str, forwarders: List[str] = None):
        """Базовая настройка Bind9"""
        print(f"⚙️ Настройка DNS-сервера для домена {domain}")
        
        if forwarders is None:
            forwarders = ['8.8.8.8', '8.8.4.4']
        
        # Настройка named.conf.options
        options_conf = self.bind_config_dir / 'named.conf.options'
        options_content = f"""
options {{
    directory "/var/cache/bind";
    
    // Прослушивание всех интерфейсов
    listen-on {{ any; }};
    listen-on-v6 {{ any; }};
    
    // Разрешение рекурсивных запросов для локальной сети
    allow-recursion {{ 127.0.0.0/8; 192.168.0.0/16; 10.0.0.0/8; }};
    allow-query {{ any; }};
    
    // Форвардеры (внешние DNS)
    forwarders {{
        {forwarders[0]};
        {forwarders[1]};
    }};
    
    // Безопасность
    dnssec-validation auto;
    auth-nxdomain no;
    
    // Логирование
    version "DNS Server";
    
    // Разрешить зонные трансферы только для slave-серверов
    allow-transfer {{ none; }};
}};

// Логирование запросов
logging {{
    channel query.log {{
        file "/var/log/named/queries.log" versions 3 size 20m;
        severity info;
        print-time yes;
    }};
    category queries {{ query.log; }};
}};
"""
        
        with open(options_conf, 'w') as f:
            f.write(options_content)
        
        # Настройка named.conf.local
        local_conf = self.bind_config_dir / 'named.conf.local'
        local_content = f"""
// Основная зона
zone "{domain}" {{
    type master;
    file "/etc/bind/zones/db.{domain}";
    allow-update {{ none; }};
}};

// Обратная зона (для сети {dns_ip.rsplit('.', 1)[0]}.0)
zone "{'.'.join(dns_ip.split('.')[:3])}.in-addr.arpa" {{
    type master;
    file "/etc/bind/zones/db.{'.'.join(dns_ip.split('.')[:3])}";
    allow-update {{ none; }};
}};
"""
        
        with open(local_conf, 'w') as f:
            f.write(local_content)
        
        # Проверка конфигурации
        result = subprocess.run(['named-checkconf'], capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ Конфигурация валидна")
            subprocess.run(['systemctl', 'reload', 'named'])
            return True
        else:
            print(f"❌ Ошибка конфигурации: {result.stderr}")
            return False
    
    def create_zone_file(self, domain: str, dns_ip: str, admin_email: str, 
                         ns_server: str = None) -> bool:
        """Создает файл прямой зоны"""
        if ns_server is None:
            ns_server = f"ns1.{domain}"
        
        # Преобразование email в формат DNS (user@domain -> user.domain)
        admin_email = admin_email.replace('@', '.')
        serial = self._generate_serial()
        
        zone_file = self.zones_dir / f"db.{domain}"
        zone_content = f"""
$TTL    3600
@       IN      SOA     {ns_server}. {admin_email}. (
                        {serial}     ; Serial
                        3600         ; Refresh
                        1800         ; Retry
                        604800       ; Expire
                        3600 )       ; Negative Cache TTL
;
; Name Servers
@       IN      NS      {ns_server}.

; A Records
@       IN      A       {dns_ip}
{ns_server.split('.')[0]}   IN      A       {dns_ip}

; Additional Records
localhost       IN      A       127.0.0.1
"""
        
        with open(zone_file, 'w') as f:
            f.write(zone_content)
        
        # Установка прав
        os.chmod(zone_file, 0o644)
        
        print(f"✅ Создан файл зоны: {zone_file}")
        return True
    
    def create_reverse_zone(self, network: str, dns_ip: str) -> bool:
        """Создает файл обратной зоны"""
        # network: 192.168.1.0
        network_parts = network.split('.')
        reverse_zone = f"{network_parts[0]}.{network_parts[1]}.{network_parts[2]}.in-addr.arpa"
        
        zone_file = self.zones_dir / f"db.{'.'.join(network_parts[:3])}"
        last_octet = dns_ip.split('.')[3]
        
        serial = self._generate_serial()
        
        zone_content = f"""
$TTL    3600
@       IN      SOA     ns1.{network}. {admin_email}. (
                        {serial}     ; Serial
                        3600         ; Refresh
                        1800         ; Retry
                        604800       ; Expire
                        3600 )       ; Negative Cache TTL
;
@       IN      NS      ns1.{network}.

; PTR Records
{last_octet}    IN      PTR     ns1.{network}.
"""
        
        with open(zone_file, 'w') as f:
            f.write(zone_content)
        
        print(f"✅ Создан файл обратной зоны: {zone_file}")
        return True
    
    def _generate_serial(self) -> str:
        """Генерирует серийный номер в формате YYYYMMDDNN"""
        from datetime import datetime
        return datetime.now().strftime('%Y%m%d01')
    
    def configure_firewall(self):
        """Настраивает фаервол для DNS (порт 53)"""
        print("🔥 Настройка фаервола...")
        
        if self.distro in ['ubuntu', 'debian']:
            # ufw
            subprocess.run(['ufw', 'allow', '53/tcp'], capture_output=True)
            subprocess.run(['ufw', 'allow', '53/udp'], capture_output=True)
            subprocess.run(['ufw', 'reload'], capture_output=True)
        else:
            # firewalld
            subprocess.run(['firewall-cmd', '--permanent', '--add-service=dns'], 
                          capture_output=True)
            subprocess.run(['firewall-cmd', '--reload'], capture_output=True)
        
        print("✅ DNS порты открыты")
    
    def full_setup(self, domain: str, dns_ip: str, admin_email: str, 
                   network: str, forwarders: List[str] = None):
        """Полная автоматическая настройка DNS-сервера"""
        print("🚀 НАЧАЛО ПОЛНОЙ НАСТРОЙКИ DNS")
        print("=" * 50)
        
        # 1. Установка
        if not self.install_bind():
            return False
        
        # 2. Создание зон
        if not self.create_zone_file(domain, dns_ip, admin_email):
            return False
        
        if not self.create_reverse_zone(network, dns_ip):
            return False
        
        # 3. Базовая конфигурация
        if not self.configure_basic(domain, dns_ip, forwarders):
            return False
        
        # 4. Настройка фаервола
        self.configure_firewall()
        
        # 5. Проверка
        self.test_dns_server(domain, dns_ip)
        
        print("\n✅ DNS-сервер полностью настроен и готов к работе!")
        return True
    
    def test_dns_server(self, domain: str, dns_ip: str):
        """Тестирует работу DNS-сервера"""
        print("\n🧪 Тестирование DNS-сервера...")
        
        # Проверка на localhost
        result = subprocess.run(
            f'nslookup {domain} localhost',
            shell=True, capture_output=True, text=True
        )
        
        if domain in result.stdout:
            print(f"✅ DNS сервер отвечает на {domain}")
        else:
            print(f"⚠️ Проверьте конфигурацию: {result.stdout}")

# Использование
if __name__ == '__main__':
    installer = DNSInstaller()
    
    # Полная настройка с нуля
    installer.full_setup(
        domain='example.com',
        dns_ip='192.168.1.10',
        admin_email='admin@example.com',
        network='192.168.1.0/24',
        forwarders=['8.8.8.8', '1.1.1.1']
    )