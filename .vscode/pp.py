#!/usr/bin/env python3
"""
Автоматическая настройка DNS-сервера (Bind9) на Linux
Поддерживает: dnf (RHEL 8+, CentOS 8+, Fedora, AlmaLinux, Rocky)
"""

import subprocess
import os
import sys
from pathlib import Path
from datetime import datetime

class DNSAutomation:
    def __init__(self):
        self.package_manager = self._detect_package_manager()
        self.service_name = 'named'
        
    def _detect_package_manager(self):
        """Определяет пакетный менеджер"""
        if os.path.exists('/usr/bin/dnf') or os.path.exists('/bin/dnf'):
            return 'dnf'
        if os.path.exists('/usr/bin/yum') or os.path.exists('/bin/yum'):
            return 'yum'
        if os.path.exists('/usr/bin/apt') or os.path.exists('/bin/apt'):
            return 'apt'
        return None
    
    def _run_command(self, cmd, check=False):
        """Выполняет команду и возвращает результат"""
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            return result
        except subprocess.TimeoutExpired:
            print(f"  ⚠️ Команда {' '.join(cmd)} превысила таймаут")
            return None
    
    def install_bind(self):
        """Устанавливает DNS сервер"""
        print("=" * 50)
        print("1. УСТАНОВКА DNS СЕРВЕРА")
        print("=" * 50)
        
        if not self.package_manager:
            print("❌ Не удалось определить пакетный менеджер")
            return False
        
        if self.package_manager in ['dnf', 'yum']:
            cmd = [self.package_manager, 'install', '-y', 'bind', 'bind-utils']
        else:
            cmd = ['apt', 'update']
            self._run_command(cmd)
            cmd = ['apt', 'install', '-y', 'bind9', 'bind9utils', 'dnsutils']
            self.service_name = 'bind9'
        
        print(f"  📦 Установка через {self.package_manager}...")
        result = self._run_command(cmd)
        
        if result and result.returncode == 0:
            print("  ✅ Установка завершена")
            return True
        else:
            print("  ❌ Ошибка установки")
            return False
    
    def create_directories(self):
        """Создает необходимые директории"""
        print("\n" + "=" * 50)
        print("2. СОЗДАНИЕ ДИРЕКТОРИЙ")
        print("=" * 50)
        
        dirs = [
            '/etc/bind',
            '/etc/bind/zones',
            '/var/log/named'
        ]
        
        for d in dirs:
            Path(d).mkdir(parents=True, exist_ok=True)
            print(f"  ✅ {d}")
        
        return True
    
    def create_zone_file(self, domain, dns_ip, admin_email):
        """Создает файл прямой зоны"""
        print("\n" + "=" * 50)
        print("3. СОЗДАНИЕ ЗОНОВОГО ФАЙЛА")
        print("=" * 50)
        
        serial = datetime.now().strftime('%Y%m%d01')
        admin_email = admin_email.replace('@', '.')
        
        zone_content = f"""$TTL 3600
@       IN SOA ns1.{domain}. {admin_email}. (
    {serial}
    3600
    1800
    604800
    3600
)

; Name Servers
@       IN NS ns1.{domain}.

; A Records
@       IN A {dns_ip}
ns1     IN A {dns_ip}
www     IN A {dns_ip}
mail    IN A {dns_ip}

; CNAME Records
ftp     IN CNAME www

; MX Record
@       IN MX 10 mail

; TXT Record
@       IN TXT "v=spf1 mx ~all"
"""
        
        zone_file = f"/etc/bind/zones/db.{domain}"
        with open(zone_file, 'w') as f:
            f.write(zone_content)
        
        print(f"  ✅ Создан: {zone_file}")
        
        # Проверка зоны
        result = self._run_command(['named-checkzone', domain, zone_file])
        if result and result.returncode == 0:
            print("  ✅ Зона валидна")
        else:
            print(f"  ⚠️ {result.stderr if result else 'Ошибка проверки'}")
        
        return True
    
    def create_reverse_zone(self, network, dns_ip, domain):
        """Создает файл обратной зоны"""
        print("\n" + "=" * 50)
        print("4. СОЗДАНИЕ ОБРАТНОЙ ЗОНЫ")
        print("=" * 50)
        
        network_parts = network.split('.')
        network_prefix = f"{network_parts[0]}.{network_parts[1]}.{network_parts[2]}"
        last_octet = dns_ip.split('.')[3]
        serial = datetime.now().strftime('%Y%m%d01')
        
        reverse_content = f"""$TTL 3600
@       IN SOA ns1.{domain}. admin.{domain}. (
    {serial}
    3600
    1800
    604800
    3600
)

@       IN NS ns1.{domain}.

{last_octet} IN PTR ns1.{domain}.
"""
        
        reverse_file = f"/etc/bind/zones/db.{network_prefix}"
        with open(reverse_file, 'w') as f:
            f.write(reverse_content)
        
        print(f"  ✅ Создан: {reverse_file}")
        return True
    
    def configure_named(self, domain, dns_ip, network):
        """Настраивает named.conf"""
        print("\n" + "=" * 50)
        print("5. НАСТРОЙКА named.conf")
        print("=" * 50)
        
        network_parts = network.split('.')
        network_prefix = f"{network_parts[0]}.{network_parts[1]}.{network_parts[2]}"
        
        # Бэкап существующего конфига
        if os.path.exists('/etc/named.conf'):
            backup = f"/etc/named.conf.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            os.rename('/etc/named.conf', backup)
            print(f"  📁 Бэкап: {backup}")
        
        config_content = f"""options {{
    listen-on port 53 {{ any; }};
    listen-on-v6 port 53 {{ any; }};
    directory "/var/named";
    dump-file "/var/named/data/cache_dump.db";
    statistics-file "/var/named/data/named_stats.txt";
    memstatistics-file "/var/named/data/named_mem_stats.txt";
    recursing-file "/var/named/data/named.recursing";
    secroots-file "/var/named/data/named.secroots";
    allow-recursion {{ 127.0.0.0/8; 192.168.0.0/16; 10.0.0.0/8; }};
    allow-query {{ any; }};
    forwarders {{
        8.8.8.8;
        8.8.4.4;
    }};
    dnssec-validation yes;
    allow-transfer {{ none; }};
}};

logging {{
    channel default_log {{
        file "/var/log/named/named.log" versions 3 size 20m;
        severity dynamic;
        print-time yes;
    }};
    category default {{ default_log; }};
}};

zone "{domain}" {{
    type master;
    file "/etc/bind/zones/db.{domain}";
}};

zone "{network_prefix}.in-addr.arpa" {{
    type master;
    file "/etc/bind/zones/db.{network_prefix}";
}};

include "/etc/named.root.key";
"""
        
        with open('/etc/named.conf', 'w') as f:
            f.write(config_content)
        
        print("  ✅ Создан /etc/named.conf")
        
        # Проверка конфигурации
        result = self._run_command(['named-checkconf'])
        if result and result.returncode == 0:
            print("  ✅ Конфигурация валидна")
        else:
            print(f"  ❌ Ошибка: {result.stderr if result else 'Unknown'}")
            return False
        
        return True
    
    def configure_firewall(self):
        """Настраивает фаервол"""
        print("\n" + "=" * 50)
        print("6. НАСТРОЙКА ФАЕРВОЛА")
        print("=" * 50)
        
        # Firewalld
        if os.path.exists('/usr/bin/firewall-cmd'):
            self._run_command(['firewall-cmd', '--permanent', '--add-service=dns'])
            self._run_command(['firewall-cmd', '--reload'])
            print("  ✅ Настроен firewalld")
            return True
        
        # UFW
        if os.path.exists('/usr/bin/ufw'):
            self._run_command(['ufw', 'allow', '53/tcp'])
            self._run_command(['ufw', 'allow', '53/udp'])
            print("  ✅ Настроен ufw")
            return True
        
        # iptables
        self._run_command(['iptables', '-A', 'INPUT', '-p', 'tcp', '--dport', '53', '-j', 'ACCEPT'])
        self._run_command(['iptables', '-A', 'INPUT', '-p', 'udp', '--dport', '53', '-j', 'ACCEPT'])
        print("  ✅ Настроен iptables")
        
        return True
    
    def start_service(self):
        """Запускает DNS сервис"""
        print("\n" + "=" * 50)
        print("7. ЗАПУСК DNS СЕРВЕРА")
        print("=" * 50)
        
        # Enable and start
        self._run_command(['systemctl', 'enable', self.service_name])
        self._run_command(['systemctl', 'restart', self.service_name])
        
        # Check status
        result = self._run_command(['systemctl', 'is-active', self.service_name])
        
        if result and result.returncode == 0:
            print(f"  ✅ {self.service_name} запущен")
            return True
        else:
            print(f"  ❌ {self.service_name} не запущен")
            return False
    
    def test_dns(self, domain, dns_ip):
        """Тестирует DNS сервер"""
        print("\n" + "=" * 50)
        print("8. ТЕСТИРОВАНИЕ")
        print("=" * 50)
        
        # Тест с nslookup
        result = self._run_command(['nslookup', domain, '127.0.0.1'])
        
        if result and domain in result.stdout:
            print(f"  ✅ nslookup: {domain} -> OK")
        else:
            print(f"  ⚠️ nslookup: {result.stdout if result else 'No output'}")
        
        # Тест с dig
        result = self._run_command(['dig', f'@{dns_ip}', domain, '+short'])
        
        if result and result.stdout.strip():
            print(f"  ✅ dig: {domain} -> {result.stdout.strip()}")
        
        return True
    
    def run(self):
        """Запуск полной автоматизации"""
        print("\n" + "=" * 60)
        print("🚀 АВТОМАТИЧЕСКАЯ НАСТРОЙКА DNS СЕРВЕРА")
        print("=" * 60)
        
        # Проверка прав
        if os.geteuid() != 0:
            print("❌ Запустите с правами root: sudo python3 dns_auto.py")
            return False
        
        # Ввод параметров
        print("\n📋 ВВЕДИТЕ ПАРАМЕТРЫ:")
        print("-" * 40)
        
        domain = input("Домен (например, example.com): ").strip()
        if not domain:
            domain = "example.com"
        
        dns_ip = input(f"IP адрес этого сервера (для {domain}): ").strip()
        if not dns_ip:
            dns_ip = "192.168.1.10"
        
        admin_email = input("Email администратора: ").strip()
        if not admin_email:
            admin_email = "admin@example.com"
        
        network = input("Ваша сеть (например, 192.168.1.0): ").strip()
        if not network:
            network = "192.168.1.0"
        
        print(f"\n📋 НАСТРОЙКИ:")
        print(f"  • Домен: {domain}")
        print(f"  • IP сервера: {dns_ip}")
        print(f"  • Email: {admin_email}")
        print(f"  • Сеть: {network}")
        
        confirm = input("\nПродолжить установку? (y/n): ").strip().lower()
        if confirm != 'y':
            print("❌ Установка отменена")
            return False
        
        # Выполнение шагов
        steps = [
            self.install_bind,
            self.create_directories,
            lambda: self.create_zone_file(domain, dns_ip, admin_email),
            lambda: self.create_reverse_zone(network, dns_ip, domain),
            lambda: self.configure_named(domain, dns_ip, network),
            self.configure_firewall,
            self.start_service,
            lambda: self.test_dns(domain, dns_ip)
        ]
        
        for step in steps:
            if not step():
                print("\n❌ Ошибка на одном из этапов")
                return False
        
        # Финальный вывод
        print("\n" + "=" * 60)
        print("✅ DNS СЕРВЕР УСПЕШНО НАСТРОЕН!")
        print("=" * 60)
        print(f"""
📋 ИНФОРМАЦИЯ:
  • DNS сервер: {dns_ip}
  • Домен: {domain}
  • Конфиг: /etc/named.conf
  • Зоны: /etc/bind/zones/
  • Логи: /var/log/named/

💡 ПРОВЕРКА РАБОТЫ:
  nslookup {domain} {dns_ip}
  dig @{dns_ip} {domain}
  systemctl status {self.service_name}

🔧 УПРАВЛЕНИЕ:
  sudo systemctl restart {service_name}
  sudo systemctl status {service_name}
  sudo tail -f /var/log/named/named.log
""")
        
        return True


if __name__ == '__main__':
    dns = DNSAutomation()
    dns.run()