#!/usr/bin/env python3
"""
Настройка DHCP для любого сетевого интерфейса в Linux
Поддерживает ALT Linux, Ubuntu, Debian, CentOS
Можно выбрать конкретный интерфейс (eth0, eth1, ens33 и т.д.)
"""

import os
import subprocess
import sys
import time

def run_cmd(cmd, sudo=True):
    """Выполняет команду в терминале"""
    if sudo and os.geteuid() != 0:
        cmd = f"sudo {cmd}"
    
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return result.returncode == 0, result.stdout.strip(), result.stderr.strip()
    except Exception as e:
        return False, "", str(e)

def get_all_interfaces():
    """Получает список ВСЕХ сетевых интерфейсов (включая выключенные)"""
    success, stdout, _ = run_cmd("ip link show | grep -E '^[0-9]+:' | cut -d: -f2", sudo=False)
    if success and stdout:
        interfaces = [iface.strip() for iface in stdout.split('\n') if iface.strip() and iface != 'lo']
        return interfaces
    return []

def get_interface_status(interface):
    """Получает статус интерфейса и IP"""
    # Проверяем статус (UP/DOWN)
    success, stdout, _ = run_cmd(f"ip link show {interface} | grep -o 'state [A-Z]*' | cut -d' ' -f2", sudo=False)
    status = stdout if success and stdout else "UNKNOWN"
    
    # Получаем IP адрес
    success, stdout, _ = run_cmd(f"ip addr show {interface} | grep 'inet ' | awk '{{print $2}}'", sudo=False)
    ip = stdout.split('/')[0] if success and stdout else "нет IP"
    
    return status, ip

def setup_dhcp_altlinux(interface):
    """Настройка DHCP для ALT Linux на конкретном интерфейсе"""
    print(f"\n🔧 Настройка DHCP для {interface} (ALT Linux)...")
    
    iface_dir = f"/etc/network/ifaces/{interface}"
    
    # Создаем директорию если её нет
    run_cmd(f"mkdir -p {iface_dir}")
    
    # Создаем файл options для DHCP
    options_content = f"""ONBOOT=yes
BOOTPROTO=dhcp
"""
    with open('/tmp/options', 'w') as f:
        f.write(options_content)
    run_cmd(f"cp /tmp/options {iface_dir}/options")
    
    # Удаляем статические настройки если есть
    run_cmd(f"rm -f {iface_dir}/ipv4")
    run_cmd(f"rm -f {iface_dir}/ipv4_route")
    
    # Включаем интерфейс
    run_cmd(f"ip link set {interface} up")
    
    # Перезапускаем сеть
    run_cmd("systemctl restart network")
    time.sleep(2)
    
    # Запрашиваем IP по DHCP
    run_cmd(f"dhclient -r {interface}")
    time.sleep(1)
    run_cmd(f"dhclient {interface}")
    
    return True, f"Интерфейс {interface} настроен на DHCP"

def setup_dhcp_netplan(interface):
    """Настройка DHCP через Netplan (Ubuntu)"""
    print(f"\n🔧 Настройка DHCP для {interface} (Netplan)...")
    
    netplan_dir = '/etc/netplan'
    config_files = [f for f in os.listdir(netplan_dir) if f.endswith(('.yaml', '.yml'))]
    
    if not config_files:
        return False, "Файлы Netplan не найдены"
    
    config_file = f"{netplan_dir}/{config_files[0]}"
    
    # Читаем текущий файл
    with open(config_file, 'r') as f:
        content = f.read()
    
    # Проверяем есть ли уже настройки для этого интерфейса
    if interface in content:
        # Заменяем настройки
        import re
        pattern = rf"({interface}:.*?)(?:\n\s+dhcp4:.*?)(?:\n\s+addresses:.*?)?(?=\n\s+\w+:|$)"
        content = re.sub(pattern, rf"\1\n      dhcp4: true", content, flags=re.DOTALL)
    else:
        # Добавляем новый интерфейс
        content = content.replace('ethernets:', f'ethernets:\n    {interface}:\n      dhcp4: true\n      dhcp6: false')
    
    with open('/tmp/netplan.yaml', 'w') as f:
        f.write(content)
    
    run_cmd(f"cp /tmp/netplan.yaml {config_file}")
    run_cmd("netplan apply")
    
    return True, f"Интерфейс {interface} настроен на DHCP"

def setup_dhcp_interfaces(interface):
    """Настройка DHCP через /etc/network/interfaces"""
    print(f"\n🔧 Настройка DHCP для {interface} (interfaces)...")
    
    config_file = '/etc/network/interfaces'
    
    # Читаем текущий файл
    with open(config_file, 'r') as f:
        lines = f.readlines()
    
    # Удаляем старые настройки для этого интерфейса
    new_lines = []
    skip = False
    for line in lines:
        if line.strip().startswith(f'auto {interface}') or line.strip().startswith(f'iface {interface}'):
            skip = True
            continue
        if skip and not line.startswith(' ') and not line.startswith('\t'):
            skip = False
        if not skip:
            new_lines.append(line)
    
    # Добавляем новые настройки
    new_lines.append(f'\nauto {interface}\n')
    new_lines.append(f'iface {interface} inet dhcp\n')
    
    with open('/tmp/interfaces', 'w') as f:
        f.writelines(new_lines)
    
    run_cmd(f"cp /tmp/interfaces {config_file}")
    run_cmd("systemctl restart networking")
    
    return True, f"Интерфейс {interface} настроен на DHCP"

def setup_dhcp_nmcli(interface):
    """Настройка DHCP через NetworkManager"""
    print(f"\n🔧 Настройка DHCP для {interface} (NetworkManager)...")
    
    # Проверяем существует ли подключение
    success, connections, _ = run_cmd(f"nmcli connection show | grep {interface}", sudo=False)
    
    if success and connections:
        conn_name = connections.split()[0]
        run_cmd(f"nmcli connection modify {conn_name} ipv4.method auto")
        run_cmd(f"nmcli connection modify {conn_name} connection.autoconnect yes")
        run_cmd(f"nmcli connection up {conn_name}")
    else:
        # Создаем новое подключение
        run_cmd(f"nmcli connection add type ethernet con-name {interface} ifname {interface}")
        run_cmd(f"nmcli connection modify {interface} ipv4.method auto")
        run_cmd(f"nmcli connection modify {interface} connection.autoconnect yes")
        run_cmd(f"nmcli connection up {interface}")
    
    return True, f"Интерфейс {interface} настроен на DHCP"

def setup_dhcp_sysconfig(interface):
    """Настройка DHCP через sysconfig (CentOS/RHEL)"""
    print(f"\n🔧 Настройка DHCP для {interface} (sysconfig)...")
    
    config_file = f"/etc/sysconfig/network-scripts/ifcfg-{interface}"
    
    config = f"""TYPE=Ethernet
BOOTPROTO=dhcp
NAME={interface}
DEVICE={interface}
ONBOOT=yes
"""
    
    with open('/tmp/ifcfg', 'w') as f:
        f.write(config)
    
    run_cmd(f"cp /tmp/ifcfg {config_file}")
    run_cmd(f"systemctl restart network")
    
    return True, f"Интерфейс {interface} настроен на DHCP"

def renew_dhcp_interface(interface):
    """Обновляет DHCP аренду для конкретного интерфейса"""
    print(f"\n🔄 Обновление DHCP для {interface}...")
    
    # Освобождаем старый IP
    run_cmd(f"dhclient -r {interface}")
    time.sleep(1)
    
    # Запрашиваем новый IP
    run_cmd(f"dhclient {interface}")
    time.sleep(2)
    
    # Проверяем новый IP
    status, ip = get_interface_status(interface)
    if ip != "нет IP":
        return True, ip
    return False, "Не удалось получить IP"

def test_interface_internet(interface):
    """Проверяет интернет через конкретный интерфейс"""
    print(f"\n🔍 Проверка интернета через {interface}...")
    
    # Проверяем пинг через интерфейс
    success, _, _ = run_cmd(f"ping -I {interface} -c 3 8.8.8.8 > /dev/null 2>&1")
    if success:
        print(f"   ✅ Интернет работает через {interface}")
        return True
    else:
        print(f"   ❌ Нет интернета через {interface}")
        return False

def detect_os_and_setup(interface):
    """Определяет ОС и настраивает DHCP на выбранном интерфейсе"""
    # ALT Linux
    if os.path.exists('/etc/altlinux-release') or os.path.exists('/etc/network/ifaces'):
        return setup_dhcp_altlinux(interface)
    
    # Netplan (Ubuntu 18.04+)
    if os.path.exists('/etc/netplan'):
        return setup_dhcp_netplan(interface)
    
    # network-scripts (CentOS/RHEL)
    if os.path.exists('/etc/sysconfig/network-scripts'):
        return setup_dhcp_sysconfig(interface)
    
    # /etc/network/interfaces (Debian/Ubuntu старые)
    if os.path.exists('/etc/network/interfaces'):
        return setup_dhcp_interfaces(interface)
    
    # NetworkManager
    success, _, _ = run_cmd("which nmcli", sudo=False)
    if success:
        return setup_dhcp_nmcli(interface)
    
    return False, "Не удалось определить тип системы"

def main():
    print("""
╔══════════════════════════════════════════════════════════╗
║         НАСТРОЙКА DHCP ДЛЯ ЛЮБОГО ИНТЕРФЕЙСА            ║
║     Можно выбрать eth0, eth1, ens33 и другие            ║
╚══════════════════════════════════════════════════════════╝
    """)
    
    # Проверяем права
    if os.geteuid() != 0:
        print("⚠️ Запустите с правами root: sudo python3 setup_dhcp.py")
        sys.exit(1)
    
    # Получаем ВСЕ интерфейсы
    interfaces = get_all_interfaces()
    
    if not interfaces:
        print("❌ Сетевые интерфейсы не найдены!")
        print("   Проверьте: ip link show")
        sys.exit(1)
    
    # Показываем все интерфейсы с их статусом
    print("📡 ДОСТУПНЫЕ СЕТЕВЫЕ ИНТЕРФЕЙСЫ:")
    print("-" * 50)
    
    interface_list = []
    for i, iface in enumerate(interfaces, 1):
        status, ip = get_interface_status(iface)
        print(f"   {i}. {iface:10} - статус: {status:5}, IP: {ip}")
        interface_list.append(iface)
    
    print("-" * 50)
    
    # Выбор интерфейса
    while True:
        try:
            choice = int(input(f"\n🔹 Выберите интерфейс для DHCP (1-{len(interface_list)}): ").strip())
            if 1 <= choice <= len(interface_list):
                interface = interface_list[choice - 1]
                break
            else:
                print(f"❌ Введите число от 1 до {len(interface_list)}")
        except ValueError:
            print("❌ Введите корректное число")
    
    print(f"\n✅ Выбран интерфейс: {interface}")
    
    # Показываем текущую конфигурацию выбранного интерфейса
    status, current_ip = get_interface_status(interface)
    print(f"\n📋 Текущая конфигурация {interface}:")
    print(f"   Статус: {status}")
    print(f"   IP: {current_ip}")
    
    # Подтверждение
    confirm = input(f"\nНастроить {interface} на DHCP? (y/n): ").strip().lower()
    if confirm != 'y':
        print("❌ Отменено")
        sys.exit(0)
    
    # Настраиваем DHCP на выбранном интерфейсе
    print(f"\n🚀 Настройка DHCP на {interface}...")
    success, message = detect_os_and_setup(interface)
    
    if success:
        print(f"✅ {message}")
        
        # Обновляем DHCP аренду
        success, new_ip = renew_dhcp_interface(interface)
        
        if success:
            print(f"✅ Получен новый IP: {new_ip}")
        else:
            print(f"⚠️ {new_ip}")
        
        # Проверяем интернет через этот интерфейс
        test_interface_internet(interface)
        
        # Показываем финальную конфигурацию
        print("\n📋 ИТОГОВАЯ КОНФИГУРАЦИЯ:")
        print("-" * 50)
        status, ip = get_interface_status(interface)
        print(f"   Интерфейс: {interface}")
        print(f"   Статус: {status}")
        print(f"   IP адрес: {ip}")
        
        # Показываем маршруты через этот интерфейс
        success, stdout, _ = run_cmd(f"ip route show | grep {interface}", sudo=False)
        if success and stdout:
            print(f"   Маршруты: {stdout}")
        
        print("\n💡 Для проверки выполните:")
        print(f"   ip addr show {interface}")
        print(f"   ping -I {interface} 8.8.8.8")
        
    else:
        print(f"❌ {message}")
        print("\nПопробуйте настроить вручную:")
        print(f"   sudo dhclient {interface}")
        print(f"   sudo ip link set {interface} up")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n❌ Прервано пользователем")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        sys.exit(1)