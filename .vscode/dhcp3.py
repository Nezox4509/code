#!/usr/bin/env python3
"""
Скрипт для ALT Linux: меняет статический IP на DHCP
Работает с /etc/net/ifaces/
"""

import os
import subprocess
import sys
import time

def run_cmd(cmd, sudo=True):
    """Выполняет команду"""
    if sudo and os.geteuid() != 0:
        cmd = f"sudo {cmd}"
    
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return result.returncode == 0, result.stdout.strip(), result.stderr.strip()
    except Exception as e:
        return False, "", str(e)

def get_all_interfaces():
    """Получает все интерфейсы"""
    success, stdout, _ = run_cmd("ip link show | grep -E '^[0-9]+:' | cut -d: -f2", sudo=False)
    if success and stdout:
        interfaces = [iface.strip() for iface in stdout.split('\n') if iface.strip() and iface != 'lo']
        return interfaces
    return []

def get_interface_config(interface):
    """Читает текущую конфигурацию интерфейса"""
    config = {}
    
    # Путь к директории интерфейса
    iface_dir = f"/etc/net/ifaces/{interface}"
    
    # Читаем options файл
    options_file = f"{iface_dir}/options"
    if os.path.exists(options_file):
        with open(options_file, 'r') as f:
            for line in f:
                line = line.strip()
                if '=' in line:
                    key, value = line.split('=', 1)
                    config[key] = value
    
    # Читаем ipv4 файл (статический IP)
    ipv4_file = f"{iface_dir}/ipv4"
    if os.path.exists(ipv4_file):
        with open(ipv4_file, 'r') as f:
            ipv4 = f.read().strip()
            if ipv4:
                config['ipv4'] = ipv4
    
    # Читаем ipv4_route файл (шлюз)
    route_file = f"{iface_dir}/ipv4_route"
    if os.path.exists(route_file):
        with open(route_file, 'r') as f:
            route = f.read().strip()
            if route:
                config['gateway'] = route.split()[1] if route.split() else ''
    
    return config

def change_to_dhcp(interface):
    """Меняет статический IP на DHCP"""
    iface_dir = f"/etc/net/ifaces/{interface}"
    
    print(f"\n🔧 Меняю настройки {interface} со статического на DHCP...")
    
    # 1. Создаем резервные копии
    if os.path.exists(f"{iface_dir}/options"):
        run_cmd(f"cp {iface_dir}/options {iface_dir}/options.backup")
        print(f"   ✅ Бэкап options создан")
    
    if os.path.exists(f"{iface_dir}/ipv4"):
        run_cmd(f"cp {iface_dir}/ipv4 {iface_dir}/ipv4.backup")
        print(f"   ✅ Бэкап ipv4 создан")
    
    if os.path.exists(f"{iface_dir}/ipv4_route"):
        run_cmd(f"cp {iface_dir}/ipv4_route {iface_dir}/ipv4_route.backup")
        print(f"   ✅ Бэкап ipv4_route создан")
    
    # 2. Меняем BOOTPROTO на dhcp в options
    options_content = """ONBOOT=yes
BOOTPROTO=dhcp
TYPE=ethernet
"""
    with open('/tmp/options', 'w') as f:
        f.write(options_content)
    run_cmd(f"cp /tmp/options {iface_dir}/options")
    print(f"   ✅ BOOTPROTO изменен на dhcp")
    
    # 3. Удаляем статические настройки
    if os.path.exists(f"{iface_dir}/ipv4"):
        run_cmd(f"rm -f {iface_dir}/ipv4")
        print(f"   ✅ Удален статический IP")
    
    if os.path.exists(f"{iface_dir}/ipv4_route"):
        run_cmd(f"rm -f {iface_dir}/ipv4_route")
        print(f"   ✅ Удален статический маршрут")
    
    return True

def renew_dhcp(interface):
    """Обновляет DHCP аренду"""
    print(f"\n🔄 Получаю новый IP через DHCP...")
    
    # Освобождаем старый IP
    run_cmd(f"dhclient -r {interface}")
    time.sleep(1)
    
    # Включаем интерфейс
    run_cmd(f"ip link set {interface} up")
    time.sleep(1)
    
    # Запрашиваем IP
    run_cmd(f"dhclient {interface}")
    time.sleep(3)
    
    # Проверяем IP
    success, stdout, _ = run_cmd(f"ip addr show {interface} | grep 'inet ' | awk '{{print $2}}'", sudo=False)
    if success and stdout:
        ip = stdout.split('/')[0]
        print(f"   ✅ Получен IP: {ip}")
        return True, ip
    else:
        print(f"   ❌ Не удалось получить IP")
        return False, None

def show_current_config(interface):
    """Показывает текущую конфигурацию интерфейса"""
    print(f"\n📋 ТЕКУЩАЯ КОНФИГУРАЦИЯ {interface}:")
    print("-" * 50)
    
    config = get_interface_config(interface)
    
    if 'BOOTPROTO' in config:
        print(f"   Тип: {config['BOOTPROTO'].upper()}")
    else:
        print(f"   Тип: НЕ ЗАДАН")
    
    if 'ipv4' in config:
        print(f"   Статический IP: {config['ipv4']}")
    
    if 'gateway' in config:
        print(f"   Шлюз: {config['gateway']}")
    
    # Текущий IP от системы
    success, stdout, _ = run_cmd(f"ip addr show {interface} | grep 'inet ' | awk '{{print $2}}'", sudo=False)
    if success and stdout:
        print(f"   Текущий IP: {stdout}")
    else:
        print(f"   Текущий IP: НЕТ")
    
    # Статус интерфейса
    success, stdout, _ = run_cmd(f"ip link show {interface} | grep -o 'state [A-Z]*' | cut -d' ' -f2", sudo=False)
    if success:
        print(f"   Статус: {stdout}")
    
    print("-" * 50)

def restart_network():
    """Перезапускает сетевые службы"""
    print(f"\n🔄 Перезапуск сетевых служб...")
    
    commands = [
        "systemctl restart network",
        "/etc/init.d/network restart",
        "service network restart"
    ]
    
    for cmd in commands:
        success, _, _ = run_cmd(cmd)
        if success:
            print(f"   ✅ {cmd}")
            return True
    
    print(f"   ⚠️ Не удалось перезапустить сеть")
    return False

def test_internet(interface):
    """Проверяет интернет через интерфейс"""
    print(f"\n🔍 Проверка интернета через {interface}...")
    
    # Пинг до 8.8.8.8
    success, _, _ = run_cmd(f"ping -I {interface} -c 3 8.8.8.8 > /dev/null 2>&1")
    if success:
        print(f"   ✅ Интернет работает!")
        
        # Пинг до ya.ru (проверка DNS)
        success, _, _ = run_cmd(f"ping -I {interface} -c 2 ya.ru > /dev/null 2>&1")
        if success:
            print(f"   ✅ DNS работает")
        else:
            print(f"   ⚠️ Проблема с DNS")
            # Добавляем DNS если нужно
            if os.path.exists('/etc/resolv.conf'):
                with open('/etc/resolv.conf', 'r') as f:
                    if 'nameserver' not in f.read():
                        print(f"   Добавляю DNS...")
                        run_cmd("echo 'nameserver 8.8.8.8' >> /etc/resolv.conf")
        
        return True
    else:
        print(f"   ❌ Нет интернета")
        return False

def main():
    print("""
╔══════════════════════════════════════════════════════════╗
║     ИЗМЕНЕНИЕ СТАТИЧЕСКОГО IP НА DHCP                    ║
║     Специально для ALT Linux (/etc/net/ifaces/)         ║
╚══════════════════════════════════════════════════════════╝
    """)
    
    # Проверяем права
    if os.geteuid() != 0:
        print("❌ Запустите с правами root: sudo python3 change_to_dhcp.py")
        sys.exit(1)
    
    # Проверяем что это ALT Linux
    if not os.path.exists('/etc/net/ifaces'):
        print("❌ Эта система не похожа на ALT Linux")
        print("   (нет директории /etc/net/ifaces)")
        answer = input("Продолжить? (y/n): ").strip().lower()
        if answer != 'y':
            sys.exit(1)
    
    # Получаем интерфейсы
    interfaces = get_all_interfaces()
    
    if not interfaces:
        print("❌ Сетевые интерфейсы не найдены!")
        sys.exit(1)
    
    # Показываем все интерфейсы
    print("📡 ДОСТУПНЫЕ ИНТЕРФЕЙСЫ:")
    print("-" * 50)
    
    interface_info = []
    for i, iface in enumerate(interfaces, 1):
        config = get_interface_config(iface)
        bootproto = config.get('BOOTPROTO', 'НЕ НАСТРОЕН').upper()
        print(f"   {i}. {iface:10} - {bootproto}")
        interface_info.append(iface)
    
    print("-" * 50)
    
    # Выбор интерфейса
    while True:
        try:
            choice = int(input(f"\n🔹 Выберите интерфейс (1-{len(interface_info)}): ").strip())
            if 1 <= choice <= len(interface_info):
                interface = interface_info[choice - 1]
                break
            else:
                print(f"❌ Введите число от 1 до {len(interface_info)}")
        except ValueError:
            print("❌ Введите корректное число")
    
    # Показываем текущую конфигурацию
    show_current_config(interface)
    
    # Проверяем, не настроен ли уже DHCP
    config = get_interface_config(interface)
    if config.get('BOOTPROTO', '').lower() == 'dhcp':
        print(f"\n⚠️ На {interface} уже настроен DHCP!")
        renew = input("Хотите обновить DHCP аренду? (y/n): ").strip().lower()
        if renew == 'y':
            renew_dhcp(interface)
            test_internet(interface)
        sys.exit(0)
    
    # Подтверждение
    print(f"\n⚠️ ВНИМАНИЕ: Статические настройки {interface} будут удалены!")
    confirm = input(f"Изменить {interface} со STATIC на DHCP? (y/n): ").strip().lower()
    
    if confirm != 'y':
        print("❌ Отменено")
        sys.exit(0)
    
    # Меняем на DHCP
    success = change_to_dhcp(interface)
    
    if success:
        print(f"\n✅ Настройки {interface} изменены на DHCP")
        
        # Перезапускаем сеть
        restart_network()
        
        # Получаем IP по DHCP
        success, ip = renew_dhcp(interface)
        
        # Проверяем интернет
        test_internet(interface)
        
        # Показываем новую конфигурацию
        print("\n📋 НОВАЯ КОНФИГУРАЦИЯ:")
        print("-" * 50)
        config = get_interface_config(interface)
        print(f"   Интерфейс: {interface}")
        print(f"   Тип: {config.get('BOOTPROTO', 'DHCP').upper()}")
        
        success, stdout, _ = run_cmd(f"ip addr show {interface} | grep 'inet ' | awk '{{print $2}}'", sudo=False)
        if success and stdout:
            print(f"   IP: {stdout}")
        
        success, stdout, _ = run_cmd(f"ip route show | grep {interface} | grep default", sudo=False)
        if success and stdout:
            print(f"   Маршрут: {stdout}")
        
        print("-" * 50)
        
        print("\n💡 Файлы конфигурации:")
        print(f"   • {interface}/options - теперь BOOTPROTO=dhcp")
        print(f"   • Статические ipv4 и ipv4_route удалены")
        
    else:
        print(f"\n❌ Ошибка при изменении настроек")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n❌ Прервано пользователем")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        sys.exit(1)