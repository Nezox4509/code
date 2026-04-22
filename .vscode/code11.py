#!/usr/bin/env python3
"""
Автоматическая настройка сети и пользователя
Работает на Windows, Linux и Mac
Просто введите данные - всё настроится автоматически
"""

import os
import subprocess
import re
import sys
import platform

def is_admin():
    """Проверяет, запущен ли скрипт с правами администратора/root"""
    system = platform.system()
    
    if system == 'Windows':
        try:
            import ctypes
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        except:
            return False
    else:  # Linux/Mac
        try:
            return os.geteuid() == 0
        except AttributeError:
            return False

def run_cmd(cmd, sudo=True):
    """Выполняет команду в терминале"""
    system = platform.system()
    
    # Добавляем sudo только на Linux/Mac и если нужно
    if sudo and system != 'Windows' and not is_admin():
        cmd = f"sudo {cmd}"
    
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
        return result.returncode == 0, result.stdout.strip(), result.stderr.strip()
    except subprocess.TimeoutExpired:
        return False, "", "Timeout"
    except Exception as e:
        return False, "", str(e)

def get_network_interfaces():
    """Получает список сетевых интерфейсов"""
    system = platform.system()
    
    if system == 'Windows':
        success, stdout, _ = run_cmd("wmic nic where 'NetEnabled=True' get Name", sudo=False)
        if success and stdout:
            lines = stdout.split('\n')[1:]  # Пропускаем заголовок
            interfaces = [line.strip() for line in lines if line.strip() and 'Name' not in line]
            return interfaces if interfaces else ['Ethernet', 'Wi-Fi']
    else:  # Linux
        success, stdout, _ = run_cmd("ip link show | grep -E '^[0-9]+:' | grep -v lo | cut -d: -f2", sudo=False)
        if success and stdout:
            interfaces = [iface.strip() for iface in stdout.split('\n') if iface.strip()]
            return interfaces
    
    return ['eth0', 'ens33', 'ens192']  # значения по умолчанию

def get_current_ip(interface):
    """Получает текущий IP интерфейса"""
    system = platform.system()
    
    if system == 'Windows':
        success, stdout, _ = run_cmd(f"ipconfig", sudo=False)
        if success:
            # Ищем IP в выводе ipconfig
            lines = stdout.split('\n')
            found_interface = False
            for line in lines:
                if interface.lower() in line.lower():
                    found_interface = True
                if found_interface and 'IPv4' in line:
                    ip_match = re.search(r'(\d+\.\d+\.\d+\.\d+)', line)
                    if ip_match:
                        return ip_match.group(1)
        return "не настроен"
    else:  # Linux
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
    # Простая проверка маски
    parts = netmask.split('.')
    valid_masks = ['255.255.255.255', '255.255.255.0', '255.255.0.0', '255.0.0.0',
                   '255.255.254.0', '255.255.252.0', '255.255.248.0', '255.255.240.0']
    return netmask in valid_masks or all(p == '255' or p == '0' for p in parts)

def setup_hostname_windows(hostname):
    """Настраивает имя компьютера на Windows"""
    if not is_admin():
        return False, "Требуются права администратора"
    
    # Меняем имя компьютера
    success, _, err = run_cmd(f'wmic computersystem where name="%computername%" call rename name="{hostname}"')
    if success:
        return True, f"Имя компьютера изменено на {hostname} (требуется перезагрузка)"
    else:
        return False, f"Ошибка: {err}"

def setup_hostname_linux(hostname):
    """Настраивает имя хоста на Linux"""
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

def setup_network_windows(interface, ip, netmask, gateway, dns1, dns2):
    """Настраивает сеть на Windows"""
    if not is_admin():
        return False, "Требуются права администратора"
    
    print(f"   Настройка интерфейса: {interface}")
    
    # Настройка IP через netsh
    cmd_ip = f'netsh interface ip set address "{interface}" static {ip} {netmask} {gateway}'
    success, _, err = run_cmd(cmd_ip)
    
    if not success:
        return False, f"Ошибка настройки IP: {err}"
    
    # Настройка DNS
    cmd_dns = f'netsh interface ip set dns "{interface}" static {dns1}'
    run_cmd(cmd_dns)
    
    if dns2:
        cmd_dns2 = f'netsh interface ip add dns "{interface}" {dns2} index=2'
        run_cmd(cmd_dns2)
    
    return True, f"Сеть настроена: {ip}"

def setup_network_linux(interface, ip, netmask, gateway, dns1, dns2):
    """Настраивает сеть на Linux"""
    cidr = sum(bin(int(x)).count('1') for x in netmask.split('.'))
    ip_cidr = f"{ip}/{cidr}"
    
    # Пробуем разные способы
    if os.path.exists('/etc/netplan'):
        # Ubuntu с Netplan
        netplan_dir = '/etc/netplan'
        config_files = [f for f in os.listdir(netplan_dir) if f.endswith(('.yaml', '.yml'))]
        config_file = f"{netplan_dir}/{config_files[0]}" if config_files else f"{netplan_dir}/01-netcfg.yaml"
        
        config = f"""network:
  version: 2
  renderer: networkd
  ethernets:
    {interface}:
      dhcp4: no
      addresses:
        - {ip_cidr}
      routes:
        - to: default
          via: {gateway}
      nameservers:
        addresses: [{dns1}, {dns2}]
"""
        with open('/tmp/netplan.yaml', 'w') as f:
            f.write(config)
        
        run_cmd(f"cp /tmp/netplan.yaml {config_file}")
        success, _, err = run_cmd("netplan apply")
        if success:
            return True, "Сеть настроена через Netplan"
        
    elif os.path.exists('/etc/sysconfig/network-scripts'):
        # CentOS/RHEL
        config_file = f"/etc/sysconfig/network-scripts/ifcfg-{interface}"
        config = f"""TYPE=Ethernet
BOOTPROTO=none
NAME={interface}
DEVICE={interface}
ONBOOT=yes
IPADDR={ip}
NETMASK={netmask}
GATEWAY={gateway}
DNS1={dns1}
DNS2={dns2}
"""
        with open('/tmp/ifcfg', 'w') as f:
            f.write(config)
        
        run_cmd(f"cp /tmp/ifcfg {config_file}")
        run_cmd("systemctl restart network")
        return True, "Сеть настроена через network-scripts"
    
    else:
        # Пробуем через nmcli
        success, _, _ = run_cmd(f"nmcli connection modify {interface} ipv4.method manual")
        run_cmd(f"nmcli connection modify {interface} ipv4.addresses {ip_cidr}")
        run_cmd(f"nmcli connection modify {interface} ipv4.gateway {gateway}")
        run_cmd(f"nmcli connection modify {interface} ipv4.dns \"{dns1} {dns2}\"")
        success, _, err = run_cmd(f"nmcli connection up {interface}")
        if success:
            return True, "Сеть настроена через NetworkManager"
    
    return False, "Не удалось настроить сеть"

def setup_user_windows(username):
    """Создает пользователя на Windows"""
    if not is_admin():
        return False, "Требуются права администратора"
    
    # Проверяем существует ли пользователь
    success, stdout, _ = run_cmd(f'net user {username}', sudo=False)
    
    if success:
        print(f"   ⚠️  Пользователь {username} уже существует")
        change_pass = input("   Хотите сменить пароль? (y/n): ").strip().lower()
        if change_pass == 'y':
            run_cmd(f'net user {username} *')
            return True, f"Пароль для {username} обновлен"
        return True, f"Пользователь {username} уже существует"
    else:
        # Создаем пользователя
        run_cmd(f'net user {username} * /add')
        # Добавляем в группу администраторов
        run_cmd(f'net localgroup administrators {username} /add')
        return True, f"Пользователь {username} создан и добавлен в администраторы"

def setup_user_linux(username):
    """Создает пользователя на Linux"""
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
    system = platform.system()
    print("\n🔍 Проверка сети...")
    
    if system == 'Windows':
        success, stdout, _ = run_cmd("ping -n 2 8.8.8.8", sudo=False)
        if success:
            print("   ✅ Интернет соединение работает")
            return True
        else:
            print("   ⚠️  Нет соединения с интернетом")
            return False
    else:
        success, _, _ = run_cmd("ping -c 2 8.8.8.8 > /dev/null 2>&1")
        if success:
            print("   ✅ Интернет соединение работает")
            return True
        else:
            print("   ⚠️  Нет соединения с интернетом")
            return False

def show_menu():
    """Показывает главное меню"""
    system = platform.system()
    print(f"""
╔══════════════════════════════════════════════════════════╗
║     АВТОМАТИЧЕСКАЯ НАСТРОЙКА СИСТЕМЫ                    ║
║     Работает на Windows, Linux, Mac                     ║
║     Обнаружена ОС: {system:<40} ║
╚══════════════════════════════════════════════════════════╝
    """)

def main():
    """Главная функция"""
    show_menu()
    
    system = platform.system()
    
    # Проверяем права
    if not is_admin():
        print("⚠️  ВНИМАНИЕ: Для полной настройки требуются права администратора/root!")
        if system == 'Windows':
            print("   Пожалуйста, запустите скрипт от имени администратора")
            print("   (Правый клик -> Запуск от имени администратора)")
        else:
            print("   Используйте: sudo python3 script.py")
        
        proceed = input("\nПродолжить с ограниченными правами? (y/n): ").strip().lower()
        if proceed != 'y':
            sys.exit(0)
    
    # Показываем текущие интерфейсы
    interfaces = get_network_interfaces()
    print("📡 Доступные сетевые интерфейсы:")
    for i, iface in enumerate(interfaces, 1):
        current_ip = get_current_ip(iface)
        print(f"   {i}. {iface} (текущий IP: {current_ip})")
    
    # Сбор данных
    print("\n" + "="*50)
    print("ВВЕДИТЕ НАСТРОЙКИ")
    print("="*50)
    
    # Выбор интерфейса
    while True:
        iface_num = input(f"\n🔹 Выберите интерфейс (1-{len(interfaces)}): ").strip()
        try:
            interface = interfaces[int(iface_num) - 1]
            break
        except (ValueError, IndexError):
            print("❌ Неверный выбор, попробуйте снова")
    
    # Имя пользователя
    username = input("🔹 Имя пользователя: ").strip()
    while not username:
        print("❌ Имя пользователя не может быть пустым")
        username = input("🔹 Имя пользователя: ").strip()
    
    # Имя хоста
    hostname = input("🔹 Имя компьютера/хоста: ").strip()
    if not hostname:
        hostname = username
    
    # IP адрес
    while True:
        ip = input("🔹 IP адрес (например: 192.168.1.100): ").strip()
        if validate_ip(ip):
            break
        print("❌ Неверный формат IP адреса")
    
    # Маска подсети
    while True:
        netmask = input("🔹 Маска подсети (например: 255.255.255.0): ").strip()
        if validate_netmask(netmask):
            break
        print("❌ Неверный формат маски")
    
    # Шлюз
    while True:
        gateway = input("🔹 Шлюз (gateway) (например: 192.168.1.1): ").strip()
        if validate_ip(gateway):
            break
        print("❌ Неверный формат IP адреса")
    
    # DNS
    dns1 = input("🔹 DNS сервер 1 (например: 8.8.8.8): ").strip()
    if not dns1:
        dns1 = "8.8.8.8"
    
    dns2 = input("🔹 DNS сервер 2 (например: 8.8.4.4): ").strip()
    if not dns2:
        dns2 = "8.8.4.4"
    
    # Показываем сводку
    print("\n" + "="*50)
    print("ПРОВЕРЬТЕ ВВЕДЕННЫЕ ДАННЫЕ")
    print("="*50)
    print(f"🔹 Операционная система: {system}")
    print(f"🔹 Интерфейс:           {interface}")
    print(f"🔹 Пользователь:        {username}")
    print(f"🔹 Имя компьютера:      {hostname}")
    print(f"🔹 IP адрес:            {ip}")
    print(f"🔹 Маска:               {netmask}")
    print(f"🔹 Шлюз:                {gateway}")
    print(f"🔹 DNS:                 {dns1}, {dns2}")
    print("="*50)
    
    # Подтверждение
    confirm = input("\n✅ Всё верно? (y/n): ").strip().lower()
    if confirm != 'y':
        print("❌ Настройка отменена")
        sys.exit(0)
    
    print("\n🚀 НАЧИНАЮ НАСТРОЙКУ...\n")
    
    # Выполняем настройку в зависимости от ОС
    steps = []
    
    if system == 'Windows':
        # Windows настройка
        print("1. Настройка имени компьютера...")
        success, msg = setup_hostname_windows(hostname)
        print(f"   {'✅' if success else '❌'} {msg}")
        steps.append(("Имя компьютера", success))
        
        print("\n2. Настройка сети...")
        success, msg = setup_network_windows(interface, ip, netmask, gateway, dns1, dns2)
        print(f"   {'✅' if success else '❌'} {msg}")
        steps.append(("Сеть", success))
        
        print("\n3. Настройка пользователя...")
        success, msg = setup_user_windows(username)
        print(f"   {'✅' if success else '❌'} {msg}")
        steps.append(("Пользователь", success))
        
    else:
        # Linux настройка
        print("1. Настройка имени хоста...")
        success, msg = setup_hostname_linux(hostname)
        print(f"   {'✅' if success else '❌'} {msg}")
        steps.append(("Имя хоста", success))
        
        print("\n2. Настройка сети...")
        success, msg = setup_network_linux(interface, ip, netmask, gateway, dns1, dns2)
        print(f"   {'✅' if success else '❌'} {msg}")
        steps.append(("Сеть", success))
        
        print("\n3. Настройка пользователя...")
        success, msg = setup_user_linux(username)
        print(f"   {'✅' if success else '❌'} {msg}")
        steps.append(("Пользователь", success))
    
    # 4. Проверка сети
    print("\n4. Проверка сети...")
    network_ok = test_network()
    steps.append(("Проверка сети", network_ok))
    
    # Итоги
    print("\n" + "="*50)
    print("РЕЗУЛЬТАТЫ НАСТРОЙКИ")
    print("="*50)
    
    all_success = True
    for step, success in steps:
        status = "✅ УСПЕШНО" if success else "❌ ОШИБКА"
        print(f"{status}: {step}")
        if not success:
            all_success = False
    
    print("="*50)
    
    if all_success:
        print("\n🎉 ВСЕ НАСТРОЙКИ ВЫПОЛНЕНЫ УСПЕШНО!")
        print("\n📋 Что было настроено:")
        print(f"   • Имя компьютера: {hostname}")
        print(f"   • IP адрес: {ip}")
        print(f"   • Маска: {netmask}")
        print(f"   • Шлюз: {gateway}")
        print(f"   • DNS: {dns1}, {dns2}")
        print(f"   • Пользователь: {username}")
        
        if system == 'Windows':
            print("\n💡 ВАЖНО: Для применения всех изменений")
            print("   перезагрузите компьютер!")
        else:
            print("\n💡 Рекомендуется перезагрузить систему:")
            print("   sudo reboot")
    else:
        print("\n❌ Некоторые настройки не удались")
        print("   Проверьте ошибки выше и попробуйте снова")
    
    print("="*50)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n❌ Настройка прервана пользователем")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Критическая ошибка: {e}")
        print(f"   Тип ошибки: {type(e).__name__}")
        sys.exit(1)