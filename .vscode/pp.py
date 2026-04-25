#!/usr/bin/env python3
"""
Исправленная автоматическая настройка DNS-сервера
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
        """Определяет пакетный менеджер с диагностикой"""
        print("🔍 Диагностика системы...")
        
        # Проверка наличия команд
        commands_to_check = ['dnf', 'yum', 'apt', 'apt-get', 'microdnf']
        
        for cmd in commands_to_check:
            result = subprocess.run(['which', cmd], capture_output=True, text=True)
            if result.returncode == 0:
                print(f"  ✅ Найден: {cmd}")
                return cmd
        
        # Дополнительная диагностика
        print("\n📋 Информация о системе:")
        
        # Проверка /etc/os-release
        if os.path.exists('/etc/os-release'):
            subprocess.run(['cat', '/etc/os-release'], capture_output=False)
        
        # Проверка /etc/redhat-release
        if os.path.exists('/etc/redhat-release'):
            subprocess.run(['cat', '/etc/redhat-release'], capture_output=False)
        
        # Проверка PATH
        print(f"\nPATH: {os.environ.get('PATH', 'Not set')}")
        
        return None
    
    def install_bind(self):
        """Устанавливает DNS сервер"""
        print("\n" + "=" * 60)
        print("1. УСТАНОВКА DNS СЕРВЕРА")
        print("=" * 60)
        
        if not self.package_manager:
            print("❌ Не удалось определить пакетный менеджер")
            print("\n💡 Установите вручную одной из команд:")
            print("   sudo dnf install -y bind bind-utils      # RHEL/CentOS/Fedora")
            print("   sudo yum install -y bind bind-utils      # CentOS 7")
            print("   sudo apt install -y bind9 bind9utils     # Ubuntu/Debian")
            
            response = input("\nУстановить вручную? (y/n): ")
            if response.lower() == 'y':
                print("\nПожалуйста, выполните установку в другом терминале,")
                print("затем вернитесь и нажмите Enter")
                input("Нажмите Enter после установки...")
                
                # Проверяем, установлен ли bind
                if os.path.exists('/usr/sbin/named') or os.path.exists('/usr/sbin/named-checkconf'):
                    print("✅ Bind установлен")
                    return True
                else:
                    print("❌ Bind не обнаружен")
                    return False
            return False
        
        # Установка через пакетный менеджер
        if self.package_manager in ['dnf', 'yum', 'microdnf']:
            cmd = [self.package_manager, 'install', '-y', 'bind', 'bind-utils']
        else:
            subprocess.run(['apt', 'update'], capture_output=True)
            cmd = ['apt', 'install', '-y', 'bind9', 'bind9utils', 'dnsutils']
            self.service_name = 'bind9'
        
        print(f"  📦 Установка через {self.package_manager}...")
        print(f"  Команда: {' '.join(cmd)}")
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            print("  ✅ Установка завершена")
            return True
        else:
            print(f"  ❌ Ошибка: {result.stderr}")
            return False
    
    def create_directories(self):
        """Создает необходимые директории"""
        print("\n" + "=" * 60)
        print("2. СОЗДАНИЕ ДИРЕКТОРИЙ")
        print("=" * 60)
        
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
        print("\n" + "=" * 60)
        print("3. СОЗДАНИЕ ЗОНОВОГО ФАЙЛА")
        print("=" * 60)
        
        serial = datetime.now().strftime('%Y%m%d01')
        admin_email = admin_email.replace('@', '.')
        
        # Корректируем домен - убираем www если он есть
        if domain.startswith('www.'):
            domain = domain[4:]
            print(f"  ℹ️ Домен скорректирован: {domain}")
        
        zone_content = f"""$TTL 3600
@       IN SOA  ns1.{domain}. {admin_email}. (
    {serial}
    3600
    1800
    604800
    3600
)

; Name Servers
@       IN NS   ns1.{domain}.

; A Records
@       IN A    {dns_ip}
ns1     IN A    {dns_ip}
www     IN A    {dns_ip}

; Additional records (add more as needed)
; mail    IN A    192.168.1.30
; files   IN A    192.168.1.40
"""
        
        zone_file = f"/etc/bind/zones/db.{domain}"
        with open(zone_file, 'w') as f:
            f.write(zone_content)
        
        print(f"  ✅ Создан: {zone_file}")
        
        # Проверка зоны
        result = subprocess.run(['named-checkzone', domain, zone_file], 
                               capture_output=True, text=True)
        
        if result.returncode == 0:
            print("  ✅ Зона валидна")
        else:
            print(f"  ⚠️ {result.stderr}")
        
        return True
    
    def create_reverse_zone(self, network, dns_ip, domain):
        """Создает файл обратной зоны"""
        print("\n" + "=" * 60)
        print("4. СОЗДАНИЕ ОБРАТНОЙ ЗОНЫ")
        print("=" * 60)
        
        # Корректируем сеть - убираем последний октет если есть
        if network.count('.') == 3:
            network_parts = network.split('.')
            network = f"{network_parts[0]}.{network_parts[1]}.{network_parts[2]}"
            print(f"  ℹ️ Сеть скорректирована: {network}")
        else:
            network_parts = network.split('.')
        
        last_octet = dns_ip.split('.')[3]
        serial = datetime.now().strftime('%Y%m%d01')
        
        reverse_content = f"""$TTL 3600
@       IN SOA  ns1.{domain}. admin.{domain}. (
    {serial}
    3600
    1800
    604800
    3600
)

@       IN NS   ns1.{domain}.

{last_octet} IN PTR ns1.{domain}.
"""
        
        reverse_file = f"/etc/bind/zones/db.{network}"
        with open(reverse_file, 'w') as f:
            f.write(reverse_content)
        
        print(f"  ✅ Создан: {reverse_file}")
        return True
    
    def configure_named(self, domain, dns_ip, network):
        """Настраивает named.conf"""
        print("\n" + "=" * 60)
        print("5. НАСТРОЙКА named.conf")
        print("=" * 60)
        
        # Корректируем сеть для обратной зоны
        if network.count('.') == 3:
            network_parts = network.split('.')
            network_prefix = f"{network_parts[0]}.{network_parts[1]}.{network_parts[2]}"
        
        # Бэкап существующего конфига
        if os.path.exists('/etc/named.conf'):
            backup = f"/etc/named.conf.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            os.rename('/etc/named.conf', backup)
            print(f"  📁 Бэкап: {backup}")
        
        config_content = f"""options {{
    listen-on port 53 {{ any; }};
    listen-on-v6 port 53 {{ none; }};
    directory "/var/named";
    allow-recursion {{ 127.0.0.0/8; {network}.0/24; }};
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
        result = subprocess.run(['named-checkconf'], capture_output=True, text=True)
        if result.returncode == 0:
            print("  ✅ Конфигурация валидна")
        else:
            print(f"  ⚠️ {result.stderr}")
        
        return True
    
    def configure_firewall(self):
        """Настраивает фаервол"""
        print("\n" + "=" * 60)
        print("6. НАСТРОЙКА ФАЕРВОЛА")
        print("=" * 60)
        
        # Firewalld
        if os.path.exists('/usr/bin/firewall-cmd'):
            subprocess.run(['firewall-cmd', '--permanent', '--add-service=dns'], 
                          capture_output=True)
            subprocess.run(['firewall-cmd', '--reload'], capture_output=True)
            print("  ✅ Настроен firewalld")
            return True
        
        # UFW
        if os.path.exists('/usr/bin/ufw'):
            subprocess.run(['ufw', 'allow', '53/tcp'], capture_output=True)
            subprocess.run(['ufw', 'allow', '53/udp'], capture_output=True)
            print("  ✅ Настроен ufw")
            return True
        
        # iptables
        subprocess.run(['iptables', '-A', 'INPUT', '-p', 'tcp', '--dport', '53', '-j', 'ACCEPT'], 
                      capture_output=True)
        subprocess.run(['iptables', '-A', 'INPUT', '-p', 'udp', '--dport', '53', '-j', 'ACCEPT'],
                      capture_output=True)
        print("  ✅ Настроен iptables")
        
        return True
    
    def start_service(self):
        """Запускает DNS сервис"""
        print("\n" + "=" * 60)
        print("7. ЗАПУСК DNS СЕРВЕРА")
        print("=" * 60)
        
        # Определяем правильное имя сервиса
        if os.path.exists('/usr/lib/systemd/system/named.service'):
            service = 'named'
        elif os.path.exists('/usr/lib/systemd/system/bind9.service'):
            service = 'bind9'
        else:
            service = self.service_name
        
        print(f"  Сервис: {service}")
        
        # Enable and start
        subprocess.run(['systemctl', 'enable', service], capture_output=True)
        subprocess.run(['systemctl', 'restart', service], capture_output=True)
        
        # Check status
        result = subprocess.run(['systemctl', 'is-active', service], 
                               capture_output=True, text=True)
        
        if result.returncode == 0:
            print(f"  ✅ {service} запущен")
            return True
        else:
            print(f"  ❌ {service} не запущен")
            # Показываем статус для диагностики
            subprocess.run(['systemctl', 'status', service], capture_output=False)
            return False
    
    def test_dns(self, domain, dns_ip):
        """Тестирует DNS сервер"""
        print("\n" + "=" * 60)
        print("8. ТЕСТИРОВАНИЕ")
        print("=" * 60)
        
        # Корректируем домен
        if domain.startswith('www.'):
            domain = domain[4:]
        
        # Ждем немного для запуска сервера
        import time
        time.sleep(2)
        
        # Тест с nslookup
        result = subprocess.run(['nslookup', domain, '127.0.0.1'], 
                               capture_output=True, text=True)
        
        if domain in result.stdout:
            print(f"  ✅ nslookup: {domain} -> OK")
        else:
            print(f"  ⚠️ nslookup: {result.stdout[:200] if result.stdout else 'No output'}")
        
        # Тест с dig
        result = subprocess.run(['dig', f'@{dns_ip}', domain, '+short'], 
                               capture_output=True, text=True)
        
        if result.stdout.strip():
            print(f"  ✅ dig: {domain} -> {result.stdout.strip()}")
        
        # Тест www
        result = subprocess.run(['dig', f'@{dns_ip}', f'www.{domain}', '+short'], 
                               capture_output=True, text=True)
        
        if result.stdout.strip():
            print(f"  ✅ dig: www.{domain} -> {result.stdout.strip()}")
        
        return True
    
    def run(self):
        """Запуск полной автоматизации"""
        print("\n" + "=" * 60)
        print("🚀 АВТОМАТИЧЕСКАЯ НАСТРОЙКА DNS СЕРВЕРА")
        print("=" * 60)
        
        # Проверка прав
        if os.geteuid() != 0:
            print("❌ Запустите с правами root: sudo python3 pp.py")
            return False
        
        # Ввод параметров с подсказками
        print("\n📋 ВВЕДИТЕ ПАРАМЕТРЫ:")
        print("-" * 40)
        print("Пример: домен = mycompany.local, IP = 192.168.1.10, сеть = 192.168.1")
        print()
        
        domain = input("Домен (например, mycompany.local): ").strip()
        if not domain:
            domain = "mycompany.local"
        
        # Убираем www если ввели
        if domain.startswith('www.'):
            domain = domain[4:]
            print(f"  (исправлено: {domain})")
        
        dns_ip = input(f"IP адрес этого сервера: ").strip()
        if not dns_ip:
            dns_ip = "192.168.1.10"
        
        admin_email = input("Email администратора: ").strip()
        if not admin_email:
            admin_email = "admin@example.com"
        
        network = input("Сеть (первые 3 октета, например 192.168.1): ").strip()
        if not network:
            network = "192.168.1"
        
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
                print("\n💡 Попробуйте установить вручную:")
                print("   sudo dnf install -y bind bind-utils")
                print("   sudo systemctl start named")
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

💡 ПРОВЕРКА РАБОТЫ:
  nslookup {domain} {dns_ip}
  nslookup www.{domain} {dns_ip}
  dig @{dns_ip} {domain}

🔧 НАСТРОЙКА КЛИЕНТОВ:
  На других компьютерах укажите DNS: {dns_ip}
""")
        
        return True


if __name__ == '__main__':
    dns = DNSAutomation()
    dns.run()