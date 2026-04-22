

import subprocess
import platform

def ping(host):
    param = '-n' if platform.system().lower() == 'windows' else '-c'
    result = subprocess.run(['ping', param, '1', host], 
                           capture_output=True)
    return result.returncode == 0

# Список серверов для проверки
servers = [
    '8.8.8.8',
    'google.com',
    '192.168.1.1',
    'yandex.ru'
]

print("🔍 ПРОВЕРКА ХОСТОВ")
print("-" * 30)
for server in servers:
    status = "✅ ДОСТУПЕН" if ping(server) else "❌ НЕ ДОСТУПЕН"
    print(f"{server:20} {status}")
