#!/usr/bin/env python3
"""
Скрипт для настройки сети на ALT Linux / ALT Server
Используется директория /etc/network/ifaces
"""

import os
import subprocess
import sys
import re

def run_cmd(cmd, sudo=True):
    """Выполняет команду в терминале"""
    if sudo and os.geteuid() != 0:
        cmd = f"sudo {cmd}"
    
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return result.returncode == 0, result.stdout.strip(), result.stderr.strip()
    except Exception as e:
        return False, "", str(e)

def setup_network_altlinux_dhcp(interface):
    """Настраивает DHCP на ALT Linux через /etc/net/ifaces"""
    
    print(f"\n🚀 Настройка DHCP на ALT Linux...")
    print(f"   Интерфейс: {interface}")
    
    # Директория для настроек интерфейса
    iface_dir = f"/etc/net/ifaces/{interface}"
    
    # Создаем директорию если её нет
    run_cmd(f"mkdir -p {iface_dir}")
    
    # 1. Настройка DHCP (файл options)
    options_content = "TYPE=eth\nBOOTPROTO=dhcp\n\n# DHCP options\nDHCLIENT_ARGS='-4 -d'\n"
    with open('/tmp/options', 'w') as f:
        f.write(options_content)
    run_cmd(f"cp /tmp/options {iface_dir}/options")
    print(f"   ✅ DHCP настроен в {iface_dir}/options")
    
    # 2. Удаляем статические настройки если есть
    run_cmd(f"rm -f {iface_dir}/ipv4address")
    run_cmd(f"rm -f {iface_dir}/ipv4route")
    
    # 3. Настройка DNS (опционально)
    resolv_content = "# DNS will be obtained via DHCP\n"
    with open('/tmp/resolv.conf', 'w') as f:
        f.write(resolv_content)
    run_cmd(f"cp /tmp/resolv.conf {iface_dir}/resolv.conf")
    
    # 4. Перезапускаем сетевую службу
    print(f"\n🔄 Перезапуск сетевой службы...")
    run_cmd("systemctl restart network")
    run_cmd(f"ifup {interface}")
    run_cmd("/etc/init.d/network restart")
    
    return True, f"DHCP настроен на интерфейсе {interface}"

def setup_network_altlinux_static(interface, ip, netmask, gateway, dns1, dns2):
    """Настраивает статическую сеть на ALT Linux через /etc/net/ifaces"""
    
    print(f"\n🚀 Настройка статической сети на ALT Linux...")
    print(f"   Интерфейс: {interface}")
    print(f"   IP: {ip}/{sum(bin(int(x)).count('1') for x in netmask.split('.'))}")
    
    # Конвертируем маску в CIDR
    cidr = sum(bin(int(x)).count('1') for x in netmask.split('.'))
    
    # Директория для настроек интерфейса
    iface_dir = f"/etc/net/ifaces/{interface}"
    
    # Создаем директорию если её нет
    run_cmd(f"mkdir -p {iface_dir}")
    
    # 1. Настройка IP адреса (файл ipv4address)
    ipv4_content = f"{ip}/{cidr}\n"
    with open('/tmp/ipv4address', 'w') as f:
        f.write(ipv4_content)
    run_cmd(f"cp /tmp/ipv4address {iface_dir}/ipv4address")
    print(f"   ✅ IP адрес записан в {iface_dir}/ipv4address")
    
    # 2. Настройка маршрута по умолчанию (файл ipv4route)
    route_content = f"default {gateway} - -\n"
    with open('/tmp/ipv4route', 'w') as f:
        f.write(route_content)
    run_cmd(f"cp /tmp/ipv4route {iface_dir}/ipv4route")
    print(f"   ✅ Маршрут записан в {iface_dir}/ipv4route")
    
    # 3. Настройка DNS (файл resolv.conf)
    resolv_content = f"nameserver {dns1}\nnameserver {dns2}\n"
    with open('/tmp/resolv.conf', 'w') as f:
        f.write(resolv_content)
    run_cmd(f"cp /tmp/resolv.conf {iface_dir}/resolv.conf")
    print(f"   ✅ DNS записаны в {iface_dir}/resolv.conf")
    
    # 4. Настройка опций интерфейса (файл options)
    options_content = "TYPE=eth\nBOOTPROTO=static\n"
    with open('/tmp/options', 'w') as f:
        f.write(options_content)
    run_cmd(f"cp /tmp/options {iface_dir}/options")
    print(f"   ✅ Опции записаны в {iface_dir}/options")
    
    # 5. Перезапускаем сетевую службу
    print(f"\n🔄 Перезапуск сетевой службы...")
    run_cmd("systemctl restart network")
    run_cmd(f"ifup {interface}")
    run_cmd("/etc/init.d/network restart")
    
    return True, f"Статическая сеть настроена: {ip}/{cidr}"

def get_network_interfaces():
    """Получает список сетевых интерфейсов"""
    success, stdout, _ = run_cmd("ip link show | grep -E '^[0-9]+:' | grep -v lo | cut -d: -f2", sudo=False)
    if success and stdout:
        interfaces = [iface.strip() for iface in stdout.split('\n') if iface.strip()]
        return interfaces
    return ['eth0', 'ens33', 'ens192']

def get_current_ip(interface):
    """Получает текущий IP интерфейса"""
    success, stdout, _ = run_cmd(f"ip addr show {interface} | grep 'inet ' | awk '{{print $2}}'", sudo=False)
    if success and stdout:
        return stdout.split('/')[0]
    return "не настроен"

def validate_ip(ip):
    """Проверяет корректность IP адреса"""
    pattern = r'^(\d{1,3}\.){3}\d{1,3}$'
    if not re.match(pattern, ip):
        return False
    parts = ip.split('.')
    for part in parts:
        if int(part) < 0 or int(part) > 255:
            return False
    return True

def validate_netmask(netmask):
    """Проверяет корректность маски"""
    if not validate_ip(netmask):
        return False
    parts = netmask.split('.')
    for part in parts:
        if int(part) not in [0, 128, 192, 224, 240, 248, 252, 254, 255]:
            return False
    return True

def setup_hostname(hostname):
    """Настраивает имя хоста"""
    print(f"\n🏷️  Настройка имени хоста: {hostname}")
    
    # Временная установка
    run_cmd(f"hostname {hostname}")
    
    # Постоянная установка
    with open('/tmp/hostname', 'w') as f:
        f.write(f"{hostname}\n")
    run_cmd("cp /tmp/hostname /etc/hostname")
    
    # Обновляем /etc/hosts
    run_cmd("sed -i '/127.0.1.1/d' /etc/hosts")
    run_cmd(f"echo '127.0.1.1 {hostname}' >> /etc/hosts")
    
    return True, f"Имя хоста установлено: {hostname}"

def setup_user(username):
    """Создает пользователя"""
    print(f"\n👤 Настройка пользователя: {username}")
    
    # Проверяем существует ли пользователь
    success, _, _ = run_cmd(f"id {username} 2>/dev/null", sudo=False)
    
    if success:
        print(f"   ⚠️  Пользователь {username} уже существует")
        change_pass = input("   Хотите сменить пароль? (y/n): ").strip().lower()
        if change_pass == 'y':
            run_cmd(f"passwd {username}")
            return True, f"Пароль для {username} обновлен"
        return True, f"Пользователь {username} уже существует"
    else:
        # Создаем пользователя
        run_cmd(f"useradd -m -s /bin/bash {username}")
        print(f"   🔐 Установите пароль для {username}:")
        run_cmd(f"passwd {username}")
        
        # Добавляем в группу sudo
        run_cmd(f"usermod -aG sudo {username}")
        return True, f"Пользователь {username} создан и добавлен в sudo"

def test_network():
    """Проверяет работоспособность сети"""
    print("\n🔍 Проверка сети...")
    
    # Проверяем интерфейсы
    success, stdout, _ = run_cmd("ip -br addr show", sudo=False)
    if success:
        print("   📡 Сетевые интерфейсы:")
        for line in stdout.split('\n'):
            if line and 'UNKNOWN' not in line:
                print(f"      {line}")
    
    # Проверяем пинг
    success, _, _ = run_cmd("ping -c 2 8.8.8.8 > /dev/null 2>&1")
    if success:
        print("   ✅ Интернет соединение работает")
        return True
    else:
        print("   ⚠️  Нет соединения с интернетом")
        return False

def show_current_config():
    """Показывает текущую конфигурацию"""
    print("\n" + "="*50)
    print("ТЕКУЩАЯ КОНФИГУРАЦИЯ СЕТИ")
    print("="*50)
    
    interfaces = get_network_interfaces()
    for iface in interfaces:
        ip = get_current_ip(iface)
        print(f"{iface}: {ip}")
    
    # Показываем маршруты
    success, stdout, _ = run_cmd("ip route | grep default", sudo=False)
    if success and stdout:
        print(f"\nШлюз: {stdout}")
    
    # Показываем DNS
    if os.path.exists('/etc/resolv.conf'):
        with open('/etc/resolv.conf', 'r') as f:
            dns_servers = []
            for line in f:
                if line.startswith('nameserver'):
                    dns_servers.append(line.split()[1])
            if dns_servers:
                print(f"DNS: {', '.join(dns_servers)}")
    
    print("="*50)

def configure_network_interactive(interface):
    """Интерактивная настройка сети (статическая или DHCP)"""
    print("\n" + "="*50)
    print("ВЫБОР ТИПА НАСТРОЙКИ СЕТИ")
    print("="*50)
    print("   1. Статический IP адрес")
    print("   2. DHCP (автоматическое получение IP)")
    
    while True:
        choice = input("\n🔹 Выберите тип настройки (1 или 2): ").strip()
        if choice == '1':
            return configure_static(interface)
        elif choice == '2':
            return configure_dhcp(interface)
        else:
            print("❌ Неверный выбор. Введите 1 или 2")

def configure_dhcp(interface):
    """Настройка DHCP"""
    print("\n" + "="*50)
    print("НАСТРОЙКА DHCP")
    print("="*50)
    print(f"🔹 Интерфейс: {interface}")
    print("🔹 Тип: DHCP (адрес будет получен автоматически)")
    
    confirm = input("\n✅ Применить настройки DHCP? (y/n): ").strip().lower()
    if confirm != 'y':
        print("❌ Отменено")
        return None, None, None, None, None
    
    return "dhcp", interface, None, None, None, None

def configure_static(interface):
    """Настройка статического IP"""
    print("\n" + "="*50)
    print("ВВЕДИТЕ СТАТИЧЕСКИЕ НАСТРОЙКИ")
    print("="*50)
    
    while True:
        ip = input("🔹 IP адрес (например: 192.168.1.100): ").strip()
        if validate_ip(ip):
            break
        print("❌ Неверный формат IP")
    
    while True:
        netmask = input("🔹 Маска подсети (например: 255.255.255.0): ").strip()
        if validate_netmask(netmask):
            break
        print("❌ Неверный формат маски")
    
    while True:
        gateway = input("🔹 Шлюз (например: 192.168.1.1): ").strip()
        if validate_ip(gateway):
            break
        print("❌ Неверный формат IP")
    
    dns1 = input("🔹 DNS сервер 1 (8.8.8.8): ").strip()
    if not dns1:
        dns1 = "8.8.8.8"
    
    dns2 = input("🔹 DNS сервер 2 (8.8.4.4): ").strip()
    if not dns2:
        dns2 = "8.8.4.4"
    
    return "static", interface, ip, netmask, gateway, dns1, dns2

def main():
    """Главная функция"""
    while True:  # Основной цикл для возврата в начало
        print("""
╔══════════════════════════════════════════════════════════╗
║        НАСТРОЙКА ALT LINUX / ALT SERVER                 ║
║     Используется /etc/network/ifaces (без Netplan)      ║
╚══════════════════════════════════════════════════════════╝
        """)
        
        # Проверяем права
        if os.geteuid() != 0:
            print("❌ Скрипт должен запускаться с правами root!")
            print("   Используйте: sudo python3 script.py")
            sys.exit(1)
        
        # Показываем текущую конфигурацию
        show_current_config()
        
        # Получаем список интерфейсов
        interfaces = get_network_interfaces()
        print("\n📡 Доступные сетевые интерфейсы:")
        for i, iface in enumerate(interfaces, 1):
            current_ip = get_current_ip(iface)
            status = f"(текущий IP: {current_ip})"
            print(f"   {i}. {iface} {status}")
        
        # Выбор интерфейса
        while True:
            choice = input(f"\n🔹 Выберите интерфейс (1-{len(interfaces)}): ").strip()
            try:
                interface = interfaces[int(choice) - 1]
                break
            except (ValueError, IndexError):
                print("❌ Неверный выбор")
        
        # Сбор данных
        print("\n" + "="*50)
        print("ВВЕДИТЕ НАСТРОЙКИ")
        print("="*50)
        
        username = input("🔹 Имя пользователя: ").strip()
        while not username:
            username = input("🔹 Имя пользователя: ").strip()
        
        hostname = input("🔹 Имя хоста: ").strip()
        if not hostname:
            hostname = username
        
        # Выбор типа настройки сети (статическая или DHCP)
        network_config = configure_network_interactive(interface)
        if network_config[0] is None:  # Если отменено
            continue
        
        # Показываем сводку
        print("\n" + "="*50)
        print("ПРОВЕРЬТЕ ДАННЫЕ")
        print("="*50)
        print(f"🔹 Интерфейс:  {interface}")
        print(f"🔹 Пользователь: {username}")
        print(f"🔹 Имя хоста:  {hostname}")
        
        if network_config[0] == "static":
            _, _, ip, netmask, gateway, dns1, dns2 = network_config
            cidr = sum(bin(int(x)).count('1') for x in netmask.split('.'))
            print(f"🔹 Тип сети:   Статический IP")
            print(f"🔹 IP адрес:   {ip}/{cidr}")
            print(f"🔹 Маска:      {netmask}")
            print(f"🔹 Шлюз:       {gateway}")
            print(f"🔹 DNS:        {dns1}, {dns2}")
        else:
            print(f"🔹 Тип сети:   DHCP")
        
        print("="*50)
        
        confirm = input("\n✅ Всё верно? (y/n): ").strip().lower()
        if confirm != 'y':
            print("❌ Отменено")
            # Спрашиваем, хочет ли пользователь начать заново
            retry = input("\n🔄 Начать заново? (y/n): ").strip().lower()
            if retry == 'y':
                continue
            else:
                sys.exit(0)
        
        # Выполняем настройку
        print("\n🚀 НАЧИНАЮ НАСТРОЙКУ...")
        
        # 1. Настройка имени хоста
        success, msg = setup_hostname(hostname)
        print(f"{'✅' if success else '❌'} {msg}")
        
        # 2. Настройка сети
        if network_config[0] == "static":
            _, interface, ip, netmask, gateway, dns1, dns2 = network_config
            success, msg = setup_network_altlinux_static(interface, ip, netmask, gateway, dns1, dns2)
        else:
            _, interface = network_config[0], network_config[1]
            success, msg = setup_network_altlinux_dhcp(interface)
        print(f"{'✅' if success else '❌'} {msg}")
        
        # 3. Настройка пользователя
        success, msg = setup_user(username)
        print(f"{'✅' if success else '❌'} {msg}")
        
        # 4. Проверка сети
        test_network()
        
        # Итоги
        print("\n" + "="*50)
        print("НАСТРОЙКА ЗАВЕРШЕНА")
        print("="*50)
        print(f"\n📋 Что настроено:")
        print(f"   • Имя хоста: {hostname}")
        print(f"   • Интерфейс: {interface}")
        
        if network_config[0] == "static":
            cidr = sum(bin(int(x)).count('1') for x in netmask.split('.'))
            print(f"   • Тип: Статический IP")
            print(f"   • IP: {ip}/{cidr}")
            print(f"   • Шлюз: {gateway}")
            print(f"   • DNS: {dns1}, {dns2}")
        else:
            print(f"   • Тип: DHCP (адрес получен автоматически)")
        
        print(f"   • Пользователь: {username}")
        
        # Спрашиваем, нужно ли вернуться в начало
        print("\n" + "="*50)
        retry = input("🔄 Вернуться в начало и настроить другой интерфейс? (y/n): ").strip().lower()
        if retry == 'y':
            print("\n" + "🔄 Возвращаемся в начало...")
            continue
        else:
            print("\n👋 До свидания!")
            break

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n❌ Прервано пользователем")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        sys.exit(1)