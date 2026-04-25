# На вашем сервере
cat > dns_setup_fixed.py << 'EOF'
#!/usr/bin/env python3
"""
Исправленная версия для RHEL 8+ / CentOS 8+ / Fedora
Использует dnf вместо yum
"""

import subprocess
import os
import sys
from pathlib import Path
from datetime import datetime

class DNSInstaller:
    def __init__(self):
        self.distro = self._detect_distro()
        self.pkg_manager = self._detect_pkg_manager()
        print(f"📊 Дистрибутив: {self.distro}")
        print(f"📦 Пакетный менеджер: {self.pkg_manager}")
        
    def _detect_distro(self):
        try:
            with open('/etc/os-release', 'r') as f:
                content = f.read().lower()
                if 'rhel' in content:
                    return 'rhel'
                elif 'centos' in content:
                    return 'centos'
                elif 'fedora' in content:
                    return 'fedora'
                elif 'almalinux' in content:
                    return 'almalinux'
                elif 'rocky' in content:
                    return 'rocky'
        except:
            pass
        return 'rhel'
    
    def _detect_pkg_manager(self):
        # Проверяем dnf (RHEL 8+, CentOS 8+, Fedora)
        if os.path.exists('/usr/bin/dnf') or os.path.exists('/bin/dnf'):
            return 'dnf'
        # Проверяем yum (старые версии)
        if os.path.exists('/usr/bin/yum') or os.path.exists('/bin/yum'):
            return 'yum'
        return 'unknown'
    
    def install_bind(self):
        print("📦 Установка DNS сервера...")
        
        if self.pkg_manager == 'dnf':
            cmd = ['dnf', 'install', '-y', 'bind', 'bind-utils']
        elif self.pkg_manager == 'yum':
            cmd = ['yum', 'install', '-y', 'bind', 'bind-utils']
        else:
            print("❌ Не найден пакетный менеджер")
            return False
        
        print(f"  Выполнение: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"  Ошибка: {result.stderr}")
            return False
        
        print("  ✅ Установка завершена")
        
        # Запуск сервиса
        subprocess.run(['systemctl', 'enable', 'named'], capture_output=True)
        subprocess.run(['systemctl', 'start', 'named'], capture_output=True)
        
        return True
    
    def create_configs(self, domain, dns_ip, admin_email, network):
        print("📝 Создание конфигурационных файлов...")
        
        # Создаем директории
        zones_dir = Path('/etc/bind/zones')
        zones_dir.mkdir(parents=True, exist_ok=True)
        
        serial = datetime.now().strftime('%Y%m%d01')
        admin_email_fmt = admin_email.replace('@', '.')
        
        # Зоновый файл
        zone_file = zones_dir / f"db.{domain}"
        zone_content = f"""$TTL    3600
@       IN      SOA     ns1.{domain}. {admin_email_fmt}. (
                        {serial}
                        3600
                        1800
                        604800
                        3600 )

@       IN      NS      ns1.{domain}.
@       IN      A       {dns_ip}
ns1     IN      A       {dns_ip}
www     IN      A       {dns_ip}
"""
        zone_file.write_text(zone_content)
        print(f"  ✅ Создан: {zone_file}")
        
        # Обратная зона
        network_parts = network.split('.')
        reverse_file = zones_dir / f"db.{network_parts[0]}.{network_parts[1]}.{network_parts[2]}"
        last_octet = dns_ip.split('.')[3]
        
        reverse_content = f"""$TTL    3600
@       IN      SOA     ns1.{domain}. {admin_email_fmt}. (
                        {serial}
                        3600
                        1800
                        604800
                        3600 )

@       IN      NS      ns1.{domain}.
{last_octet}    IN      PTR     ns1.{domain}.
"""
        reverse_file.write_text(reverse_content)
        print(f"  ✅ Создан: {reverse_file}")
        
        # Конфиг named.conf
        named_conf = Path('/etc/named.conf')
        backup = named_conf.with_suffix('.conf.backup')
        if named_conf.exists():
            import shutil
            shutil.copy2(named_conf, backup)
            print(f"  📁 Бэкап создан: {backup}")
        
        network_prefix = f"{network_parts[0]}.{network_parts[1]}.{network_parts[2]}"
        
        config_content = f"""options {{
    listen-on port 53 {{ any; }};
    listen-on-v6 port 53 {{ any; }};
    directory "/var/named";
    allow-recursion {{ 127.0.0.0/8; 192.168.0.0/16; 10.0.0.0/8; }};
    allow-query {{ any; }};
    forwarders {{
        8.8.8.8;
        8.8.4.4;
    }};
    dnssec-validation yes;
    allow-transfer {{ none; }};
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
        named_conf.write_text(config_content)
        print(f"  ✅ Создан: {named_conf}")
        
        return True
    
    def reload_and_test(self, domain):
        print("🔄 Перезагрузка DNS сервера...")
        
        # Проверка конфигурации
        subprocess.run(['named-checkconf'], capture_output=True)
        
        # Перезагрузка
        subprocess.run(['systemctl', 'restart', 'named'], capture_output=True)
        
        # Проверка статуса
        result = subprocess.run(['systemctl', 'is-active', 'named'], 
                               capture_output=True, text=True)
        
        if result.returncode == 0:
            print("  ✅ DNS сервер запущен")
        else:
            print("  ⚠️ Проверьте статус: systemctl status named")
        
        # Тест
        print("\n🧪 Тестирование...")
        result = subprocess.run(['nslookup', domain, '127.0.0.1'], 
                               capture_output=True, text=True)
        
        if domain in result.stdout:
            print(f"  ✅ {domain} разрешается успешно")
        else:
            print(f"  ⚠️ Проверьте вручную: nslookup {domain} 127.0.0.1")
    
    def full_setup(self, domain, dns_ip, admin_email, network):
        print("=" * 60)
        print("🚀 НАЧАЛО НАСТРОЙКИ DNS")
        print("=" * 60)
        
        if not self.install_bind():
            return False
        
        if not self.create_configs(domain, dns_ip, admin_email, network):
            return False
        
        self.reload_and_test(domain)
        
        print("\n" + "=" * 60)
        print("✅ DNS СЕРВЕР НАСТРОЕН!")
        print("=" * 60)
        print(f"\n📋 ИНФОРМАЦИЯ:")
        print(f"  • DNS сервер: {dns_ip}")
        print(f"  • Домен: {domain}")
        print(f"\n💡 ПРОВЕРКА:")
        print(f"  nslookup {domain} {dns_ip}")
        print(f"  dig @{dns_ip} {domain}")
        
        return True

def main():
    # Проверка root
    if os.geteuid() != 0:
        print("❌ Запустите с sudo: sudo python3 dns_setup_fixed.py")
        sys.exit(1)
    
    # Конфигурация (измените под вашу сеть)
    config = {
        'domain': 'example.com',
        'dns_ip': '192.168.1.10',
        'admin_email': 'admin@example.com',
        'network': '192.168.1.0'
    }
    
    print("\n📋 ТЕКУЩАЯ КОНФИГУРАЦИЯ:")
    for key, value in config.items():
        print(f"  {key}: {value}")
    print()
    
    response = input("Продолжить? (y/n): ")
    if response.lower() != 'y':
        print("Отмена")
        sys.exit(0)
    
    installer = DNSInstaller()
    installer.full_setup(**config)

if __name__ == '__main__':
    main()
EOF

# Запуск исправленного скрипта
