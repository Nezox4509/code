#!/usr/bin/env python3
"""
Простой скрипт для настройки сети
Работает на Windows, Linux и Mac
"""

import os
import sys
import subprocess
import re
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

def run_cmd(cmd):
    """Выполняет команду в терминале"""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return result.returncode == 0, result.stdout, result.stderr
    except Exception as e:
        return False, "", str(e)

def get_user_input():
    """Собирает данные от пользователя"""
    print("\n" + "="*50)
    print(" НАСТРОЙКА СЕТИ")
    print("="*50)
    
    print("\n--- ОСНОВНЫЕ ПАРАМЕТРЫ ---")
    
    username = input("🔹 Имя пользователя: ").strip()
    hostname = input("🔹 Имя компьютера (hostname): ").strip()
    
    print("\n--- СЕТЕВЫЕ НАСТРОЙКИ ---")
    
    interface = input("🔹 Сетевой интерфейс (eth0/ens33): ").strip()
    ip_address = input("🔹 IP адрес (например: 192.168.1.100): ").strip()
    netmask = input("🔹 Маска подсети (например: 255.255.255.0): ").strip()
    gateway = input("🔹 Шлюз (gateway) (например: 192.168.1.1): ").strip()
    dns1 = input("🔹 DNS сервер 1 (например: 8.8.8.8): ").strip()
    dns2 = input("🔹 DNS сервер 2 (например: 8.8.4.4): ").strip()
    
    return {
        'username': username,
        'hostname': hostname,
        'interface': interface,
        'ip': ip_address,
        'netmask': netmask,
        'gateway': gateway,
        'dns1': dns1,
        'dns2': dns2
    }

def show_summary(data):
    """Показывает введенные данные"""
    print("\n" + "="*50)
    print(" ПРОВЕРЬТЕ ВВЕДЕННЫЕ ДАННЫЕ")
    print("="*50)
    print(f"Имя пользователя: {data['username']}")
    print(f"Имя компьютера:  {data['hostname']}")
    print(f"Интерфейс:       {data['interface']}")
    print(f"IP адрес:        {data['ip']}")
    print(f"Маска:           {data['netmask']}")
    print(f"Шлюз:            {data['gateway']}")
    print(f"DNS1:            {data['dns1']}")
    print(f"DNS2:            {data['dns2']}")
    print("="*50)

def mask_to_cidr(netmask):
    """Переводит маску в CIDR формат (255.255.255.0 -> 24)"""
    try:
        return sum(bin(int(x)).count('1') for x in netmask.split('.'))
    except:
        return 24

def setup_network_linux(data):
    """Настраивает сеть на Linux"""
    print("\n🚀 Настройка сети на Linux...")
    
    cidr = mask_to_cidr(data['netmask'])
    ip_cidr = f"{data['ip']}/{cidr}"
    
    system = platform.system()
    
    if system == 'Linux':
        if os.path.exists('/etc/netplan'):
            # Ubuntu с Netplan
            config_file = '/etc/netplan/01-netcfg.yaml'
            run_cmd(f"sudo cp {config_file} {config_file}.backup 2>/dev/null || true")
            
            config = f"""network:
  version: 2
  renderer: networkd
  ethernets:
    {data['interface']}:
      dhcp4: no
      addresses:
        - {ip_cidr}
      routes:
        - to: default
          via: {data['gateway']}
      nameservers:
        addresses: [{data['dns1']}, {data['dns2']}]
"""
            with open('/tmp/netplan.yaml', 'w') as f:
                f.write(config)
            
            run_cmd(f"sudo cp /tmp/netplan.yaml {config_file}")
            run_cmd("sudo netplan apply")
            print("✅ Сеть настроена через Netplan")
            
        elif os.path.exists('/etc/sysconfig/network-scripts'):
            # CentOS/RHEL
            config_file = f"/etc/sysconfig/network-scripts/ifcfg-{data['interface']}"
            config = f"""TYPE=Ethernet
BOOTPROTO=none
NAME={data['interface']}
DEVICE={data['interface']}
ONBOOT=yes
IPADDR={data['ip']}
NETMASK={data['netmask']}
GATEWAY={data['gateway']}
DNS1={data['dns1']}
DNS2={data['dns2']}
"""
            with open('/tmp/ifcfg', 'w') as f:
                f.write(config)
            
            run_cmd(f"sudo cp /tmp/ifcfg {config_file}")
            run_cmd("sudo systemctl restart network")
            print("✅ Сеть настроена через Network Scripts")
        else:
            print("⚠️  Автоматическая настройка сети не поддерживается на этой системе")
            print("Настройте сеть вручную")

def setup_network_windows(data):
    """Настраивает сеть на Windows"""
    print("\n🚀 Настройка сети на Windows...")
    print("⚠️  На Windows используйте ручную настройку через Панель управления")
    print(f"   IP: {data['ip']}")
    print(f"   Маска: {data['netmask']}")
    print(f"   Шлюз: {data['gateway']}")
    print(f"   DNS: {data['dns1']}, {data['dns2']}")
    
    # Альтернативный способ через netsh
    confirm = input("\nХотите применить настройки через netsh? (y/n): ").strip().lower()
    if confirm == 'y':
        # Для Windows нужно запустить от администратора
        netsh_cmd = f'netsh interface ip set address "{data["interface"]}" static {data["ip"]} {data["netmask"]} {data["gateway"]}'
        success, _, error = run_cmd(f'"{netsh_cmd}"')
        
        if success:
            # Настройка DNS
            run_cmd(f'netsh interface ip set dns "{data["interface"]}" static {data["dns1"]}')
            run_cmd(f'netsh interface ip add dns "{data["interface"]}" {data["dns2"]} index=2')
            print("✅ Сеть настроена через netsh")
        else:
            print(f"❌ Ошибка: {error}")

def setup_hostname_linux(data):
    """Настраивает имя хоста на Linux"""
    print("\n🏷️  Настройка имени хоста...")
    
    # Временная установка
    run_cmd(f"sudo hostname {data['hostname']}")
    
    # Постоянная установка
    with open('/tmp/hostname', 'w') as f:
        f.write(f"{data['hostname']}\n")
    run_cmd("sudo cp /tmp/hostname /etc/hostname")
    
    # Обновляем /etc/hosts
    run_cmd(f"sudo sed -i '/127.0.1.1/d' /etc/hosts")
    run_cmd(f"echo '127.0.1.1 {data['hostname']}' | sudo tee -a /etc/hosts")
    
    print(f"✅ Имя хоста установлено: {data['hostname']}")

def setup_hostname_windows(data):
    """Настраивает имя компьютера на Windows"""
    print("\n🏷️  Настройка имени компьютера...")
    
    # Проверяем права администратора
    if not is_admin():
        print("❌ Для смены имени компьютера нужны права администратора")
        print("Запустите скрипт от имени администратора")
        return
    
    # Меняем имя компьютера
    cmd = f'wmic computersystem where name="%computername%" call rename name="{data["hostname"]}"'
    success, stdout, error = run_cmd(cmd)
    
    if success:
        print(f"✅ Имя компьютера изменено на {data['hostname']}")
        print("⚠️  Для применения изменений потребуется перезагрузка")
    else:
        print(f"❌ Ошибка: {error}")

def create_user_linux(data):
    """Создает пользователя на Linux"""
    print("\n👤 Настройка пользователя...")
    
    # Проверяем существует ли пользователь
    exists, _, _ = run_cmd(f"id {data['username']} 2>/dev/null")
    
    if exists:
        print(f"⚠️  Пользователь {data['username']} уже существует")
        change_pass = input("Хотите сменить пароль? (y/n): ").strip().lower()
        if change_pass == 'y':
            run_cmd(f"sudo passwd {data['username']}")
    else:
        # Создаем пользователя
        run_cmd(f"sudo useradd -m -s /bin/bash {data['username']}")
        print(f"✅ Пользователь {data['username']} создан")
        print("🔐 Установите пароль:")
        run_cmd(f"sudo passwd {data['username']}")
        
        # Добавляем в группу sudo
        run_cmd(f"sudo usermod -aG sudo {data['username']}")
        print(f"✅ Пользователь {data['username']} добавлен в группу sudo")

def create_user_windows(data):
    """Создает пользователя на Windows"""
    print("\n👤 Настройка пользователя...")
    
    if not is_admin():
        print("❌ Для создания пользователя нужны права администратора")
        return
    
    # Проверяем существует ли пользователь
    exists, _, _ = run_cmd(f'net user {data["username"]} 2>nul')
    
    if exists:
        print(f"⚠️  Пользователь {data['username']} уже существует")
    else:
        # Создаем пользователя
        run_cmd(f'net user {data["username"]} * /add')
        print(f"✅ Пользователь {data['username']} создан")
        
        # Добавляем в группу администраторов
        run_cmd(f'net localgroup administrators {data["username"]} /add')
        print(f"✅ Пользователь {data['username']} добавлен в группу администраторов")

def test_connection():
    """Проверяет соединение"""
    print("\n🔍 Проверка соединения...")
    
    # Проверяем интерфейсы
    system = platform.system()
    
    if system == 'Windows':
        success, stdout, _ = run_cmd("ipconfig")
        if success:
            print("📡 IP конфигурация:")
            for line in stdout.split('\n'):
                if 'IPv4' in line or 'IP Address' in line:
                    print(f"   {line.strip()}")
    else:
        success, stdout, _ = run_cmd("ip addr show | grep inet")
        if success:
            print("📡 IP адреса:")
            for line in stdout.split('\n'):
                if 'inet ' in line and '127.0.0.1' not in line:
                    print(f"   {line.strip()}")
    
    # Проверяем пинг
    success, _, _ = run_cmd("ping -c 2 8.8.8.8 > /dev/null 2>&1")
    if success:
        print("✅ Интернет соединение работает")
    else:
        print("⚠️  Нет соединения с интернетом")

def save_config(data):
    """Сохраняет конфигурацию в файл"""
    system = platform.system()
    
    if system == 'Windows':
        save_path = os.path.expanduser("~/Desktop/network_config.txt")
    else:
        save_path = "/root/network_backup.txt"
    
    with open(save_path, 'w') as f:
        f.write("="*50 + "\n")
        f.write("КОНФИГУРАЦИЯ СЕТИ\n")
        f.write("="*50 + "\n")
        for key, value in data.items():
            f.write(f"{key}: {value}\n")
    
    print(f"✅ Конфигурация сохранена в {save_path}")

def main():
    """Главная функция"""
    print("""
    ╔══════════════════════════════════════════╗
    ║   ПРОСТАЯ НАСТРОЙКА СИСТЕМЫ             ║
    ║   Работает на Windows, Linux, Mac       ║
    ╚══════════════════════════════════════════╝
    """)
    
    # Проверяем права
    if not is_admin():
        print("⚠️  Некоторые операции требуют прав администратора/root")
        if platform.system() == 'Windows':
            print("Перезапустите скрипт от имени администратора")
        else:
            print("Перезапустите с sudo: sudo python3 script.py")
        
        proceed = input("\nПродолжить с ограниченными правами? (y/n): ").strip().lower()
        if proceed != 'y':
            return
    
    # Собираем данные
    data = get_user_input()
    
    # Показываем введенные данные
    show_summary(data)
    
    # Подтверждение
    confirm = input("\n✅ Всё верно? (y/n): ").strip().lower()
    if confirm != 'y':
        print("❌ Отменено. Запустите заново.")
        return
    
    system = platform.system()
    
    # Выполняем настройку в зависимости от ОС
    if system == 'Linux':
        setup_hostname_linux(data)
        setup_network_linux(data)
        create_user_linux(data)
    elif system == 'Windows':
        setup_hostname_windows(data)
        setup_network_windows(data)
        create_user_windows(data)
    else:  # Mac
        print(f"\n⚠️  Система {system} не полностью поддерживается")
        print("Настройки нужно будет выполнить вручную")
    
    test_connection()
    save_config(data)
    
    print("\n" + "="*50)
    print("🎉 НАСТРОЙКА ЗАВЕРШЕНА!")
    print("="*50)
    print("\n📌 Что было сделано:")
    print(f"   • Установлено имя хоста: {data['hostname']}")
    print(f"   • Настроен IP адрес: {data['ip']}")
    print(f"   • Настроен шлюз: {data['gateway']}")
    print(f"   • Настроены DNS: {data['dns1']}, {data['dns2']}")
    print(f"   • Создан/настроен пользователь: {data['username']}")
    
    if system == 'Windows':
        print("\n💡 Для применения изменений перезагрузите компьютер")
    else:
        print("\n💡 Рекомендуется перезагрузить систему: sudo reboot")
    print("="*50)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n❌ Программа прервана пользователем")
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        print("Пожалуйста, сообщите об ошибке разработчику")