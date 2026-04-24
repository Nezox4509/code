#!/usr/bin/env python3
"""
Настройка DHCP для сетевого интерфейса в Linux
Работает с различными дистрибутивами (ALT Linux, Ubuntu, Debian, CentOS)
"""

import os
import subprocess
import sys
import platform

def run_cmd(cmd, sudo=True):
    """Выполняет команду в терминале"""
    if sudo and os.geteuid() != 0:
        cmd = f"sudo {cmd}"
    
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return result.returncode == 0, result.stdout.strip(), result.stderr.strip()
    except Exception as e:
        return False, "", str(e)

def get_network_interfaces():
    """Получает список сетевых интерфейсов"""
    success, stdout, _ = run_cmd("ip link show | grep -E '^[0-9]+:' | grep -v lo | cut -d: -f2", sudo=False)
    if success and stdout:
        interfaces = [iface.strip() for iface in stdout.split('\n') if iface.strip()]
        return interfaces
    return ['eth0', 'ens33', 'ens192']

def get_interface_status(interface):
    """Получает статус интерфейса и IP"""
    success, stdout, _ = run_cmd(f"ip addr show {interface} | grep 'inet ' | awk '{{print $2}}'", sudo=False)
    if success and stdout:
        return "up", stdout.split('/')[0]
    return "down", "нет IP"

def setup_dhcp_netplan(interface):
    """Настройка DHCP через Netplan (Ubuntu 18.04+)"""
    netplan_dir = '/etc/netplan'
    config_files = [f for f in os.listdir(netplan_dir) if f.endswith(('.yaml', '.yml'))]
    
    if config_files:
        config_file = f"{netplan_dir}/{config_files[0]}"
    else:
        config_file = f"{netplan_dir}/01-netcfg.yaml"
    
    # Создаем резервную копию
    run_cmd(f"cp {config_file} {config_file}.backup.$(date +%Y%m%d_%H%M%S)")
    
    # Конфигурация для DHCP
    config = f"""network:
  version: 2
  renderer: networkd
  ethernets:
    {interface}:
      dhcp4: true
      dhcp6: false
"""
    
    with open('/tmp/netplan.yaml', 'w') as f:
        f.write(config)
    
    run_cmd(f"cp /tmp/netplan.yaml {config_file}")
    success, _, err = run_cmd("netplan apply")
    
    if success:
        return True, f"Интерфейс {interface} настроен на DHCP через Netplan"
    else:
        return False, f"Ошибка: {err}"

def setup_dhcp_altlinux(interface):
    """Настройка DHCP для ALT Linux (через /etc/network/ifaces)"""
    iface_dir = f"/etc/network/ifaces/{interface}"
    
    # Создаем директорию
    run_cmd(f"mkdir -p {iface_dir}")
    
    # Создаем файл options для DHCP
    options_content = """BOOTPROTO=dhcp"""
    with open('/tmp/options', 'w') as f:
        f.write(options_content)
    run_cmd(f"cp /tmp/options {iface_dir}/options")
    
    # Удаляем статические настройки если есть
    run_cmd(f"rm -f {iface_dir}/ipv4")
    run_cmd(f"rm -f {iface_dir}/ipv4_route")
    
    # Перезапускаем сеть
    run_cmd("systemctl restart network")
    run_cmd("/etc/init.d/network restart")
    
    # Запрашиваем IP по DHCP
    run_cmd(f"dhclient {interface}")
    
    return True, f"Интерфейс {interface} настроен на DHCP (ALT Linux)"

def setup_dhcp_interfaces(interface):
    """Настройка DHCP через /etc/network/interfaces (Debian/Ubuntu)"""
    config_file = '/etc/network/interfaces'
    
    # Создаем резервную копию
    run_cmd(f"cp {config_file} {config_file}.backup.$(date +%Y%m%d_%H%M%S)")
    
    # Читаем текущий файл
    with open(config_file, 'r') as f:
        content = f.read()
    
    # Удаляем старые настройки для интерфейса
    import re
    pattern = rf"auto {interface}\s*iface {interface} inet.*?\n(?:[ \t]+.*\n)*"
    content = re.sub(pattern, '', content, flags=re.MULTILINE)
    
    # Добавляем настройки DHCP
    new_config = f"""
auto {interface}
iface {interface} inet dhcp
"""
    content += new_config
    
    with open('/tmp/interfaces', 'w') as f:
        f.write(content)
    run_cmd(f"cp /tmp/interfaces {config_file}")
    
    # Перезапускаем сеть
    run_cmd("systemctl restart networking")
    
    return True, f"Интерфейс {interface} настроен на DHCP через /etc/network/interfaces"

def setup_dhcp_nmcli(interface):
    """Настройка DHCP через NetworkManager"""
    # Проверяем существует ли подключение
    success, connections, _ = run_cmd(f"nmcli connection show | grep {interface}", sudo=False)
    
    if success and connections:
        conn_name = connections.split()[0]
        run_cmd(f"nmcli connection modify {conn_name} ipv4.method auto")
        run_cmd(f"nmcli connection up {conn_name}")
    else:
        # Создаем новое подключение
        run_cmd(f"nmcli connection add type ethernet con-name {interface} ifname {interface}")
        run_cmd(f"nmcli connection modify {interface} ipv4.method auto")
        run_cmd(f"nmcli connection up {interface}")
    
    return True, f"Интерфейс {interface} настроен на DHCP через NetworkManager"

def setup_dhcp_sysconfig(interface):
    """Настройка DHCP через /etc/sysconfig/network-scripts (CentOS/RHEL)"""
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
    run_cmd("systemctl restart network")
    
    return True, f"Интерфейс {interface} настроен на DHCP через network-scripts"

def renew_dhcp_lease(interface):
    """Обновляет DHCP аренду"""
    print(f"\n🔄 Обновление DHCP аренды для {interface}...")
    
    # Освобождаем старый IP
    run_cmd(f"dhclient -r {interface}")
    
    # Запрашиваем новый IP
    run_cmd(f"dhclient {interface}")
    
    # Проверяем новый IP
    success, stdout, _ = run_cmd(f"ip addr show {interface} | grep 'inet ' | awk '{{print $2}}'", sudo=False)
    if success and stdout:
        return True, stdout.split('/')[0]
    return False, "Не удалось получить IP"

def show_current_config():
    """Показывает текущую сетевую конфигурацию"""
    print("\n" + "="*50)
    print("ТЕКУЩАЯ КОНФИГУРАЦИЯ СЕТИ")
    print("="*50)
    
    interfaces = get_network_interfaces()
    for iface in interfaces:
        status, ip = get_interface_status(iface)
        print(f"{iface}: {status}, IP: {ip}")
    
    # Показываем маршруты
    success, stdout, _ = run_cmd("ip route | grep default", sudo=False)
    if success and stdout:
        print(f"\nШлюз по умолчанию: {stdout}")
    
    # Показываем DNS
    if os.path.exists('/etc/resolv.conf'):
        with open('/etc/resolv.conf', 'r') as f:
            dns_servers = []
            for line in f:
                if line.startswith('nameserver'):
                    dns_servers.append(line.split()[1])
            if dns_servers:
                print(f"DNS серверы: {', '.join(dns_servers)}")
    
    print("="*50)

def detect_os_and_setup(interface):
    """Определяет ОС и настраивает DHCP"""
    print(f"\n🔍 Определение системы для настройки {interface}...")
    
    # Проверяем ALT Linux
    if os.path.exists('/etc/altlinux-release') or os.path.exists('/etc/network/ifaces'):
        print("   Обнаружен ALT Linux")
        return setup_dhcp_altlinux(interface)
    
    # Проверяем Netplan (Ubuntu 18.04+)
    if os.path.exists('/etc/netplan'):
        print("   Обнаружен Netplan (Ubuntu 18.04+)")
        return setup_dhcp_netplan(interface)
    
    # Проверяем network-scripts (CentOS/RHEL)
    if os.path.exists('/etc/sysconfig/network-scripts'):
        print("   Обнаружен CentOS/RHEL")
        return setup_dhcp_sysconfig(interface)
    
    # Проверяем /etc/network/interfaces (Debian/Ubuntu старые)
    if os.path.exists('/etc/network/interfaces'):
        print("   Обнаружен Debian/Ubuntu (старая схема)")
        return setup_dhcp_interfaces(interface)
    
    # Проверяем NetworkManager
    success, _, _ = run_cmd("which nmcli", sudo=False)
    if success:
        print("   Обнаружен NetworkManager")
        return setup_dhcp_nmcli(interface)
    
    return False, "Не удалось определить тип системы"

def main():
    """Главная функция"""
    print("""
╔══════════════════════════════════════════════════════════╗
║           НАСТРОЙКА DHCP В VS CODE                      ║
║   Автоматическая настройка DHCP для Linux               ║
╚══════════════════════════════════════════════════════════╝
    """)
    
    # Проверяем права
    if os.geteuid() != 0:
        print("⚠️  Для настройки DHCP нужны права root!")
        print("   Перезапустите скрипт с sudo:")
        print("   sudo python3 dhcp_setup.py")
        print("\n   Или запустите VS Code от имени root")
        
        # Пробуем перезапустить с sudo
        restart = input("\nПерезапустить с sudo? (y/n): ").strip().lower()
        if restart == 'y':
            os.execvp('sudo', ['sudo', 'python3'] + sys.argv)
        else:
            sys.exit(0)
    
    # Показываем текущую конфигурацию
    show_current_config()
    
    # Получаем список интерфейсов
    interfaces = get_network_interfaces()
    
    if not interfaces:
        print("❌ Сетевые интерфейсы не найдены!")
        sys.exit(1)
    
    print("\n📡 Доступные сетевые интерфейсы:")
    for i, iface in enumerate(interfaces, 1):
        status, ip = get_interface_status(iface)
        print(f"   {i}. {iface} - статус: {status}, IP: {ip}")
    
    # Выбор интерфейса
    while True:
        try:
            choice = int(input(f"\n🔹 Выберите интерфейс для DHCP (1-{len(interfaces)}): ").strip())
            if 1 <= choice <= len(interfaces):
                interface = interfaces[choice - 1]
                break
            else:
                print(f"❌ Введите число от 1 до {len(interfaces)}")
        except ValueError:
            print("❌ Введите корректное число")
    
    print(f"\n✅ Выбран интерфейс: {interface}")
    
    # Подтверждение
    confirm = input(f"\nНастроить {interface} на DHCP? (y/n): ").strip().lower()
    if confirm != 'y':
        print("❌ Отменено")
        sys.exit(0)
    
    # Настраиваем DHCP
    print(f"\n🚀 Настройка DHCP на {interface}...")
    success, message = detect_os_and_setup(interface)
    
    if success:
        print(f"✅ {message}")
        
        # Обновляем DHCP аренду
        success, new_ip = renew_dhcp_lease(interface)
        
        if success:
            print(f"✅ Получен новый IP: {new_ip}")
        else:
            print(f"⚠️ {new_ip}")
        
        # Проверяем интернет
        print("\n🔍 Проверка интернета...")
        success, _, _ = run_cmd("ping -c 3 8.8.8.8 > /dev/null 2>&1")
        if success:
            print("✅ Интернет работает!")
        else:
            print("⚠️ Проблема с интернетом, проверьте настройки")
        
        # Показываем финальную конфигурацию
        print("\n📋 ИТОГОВАЯ КОНФИГУРАЦИЯ:")
        status, ip = get_interface_status(interface)
        print(f"   Интерфейс: {interface}")
        print(f"   Статус: {status}")
        print(f"   IP адрес: {ip}")
        
        success, stdout, _ = run_cmd("ip route | grep default", sudo=False)
        if success and stdout:
            print(f"   Шлюз: {stdout}")
        
        print("\n💡 Для применения настроек перезагрузка не требуется")
        
    else:
        print(f"❌ {message}")
        print("\nПопробуйте настроить вручную:")
        print(f"   sudo dhclient {interface}")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n❌ Прервано пользователем")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        sys.exit(1)