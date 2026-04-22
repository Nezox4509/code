# process_monitor.py - следим за важными процессами
import subprocess
import psutil  # нужно установить: pip install psutil

def check_process(process_name):
    """Проверяет, запущен ли процесс"""
    for proc in psutil.process_iter(['name']):
        if proc.info['name'] == process_name:
            return True
    return False

def show_top_cpu():
    """Топ 5 процессов по CPU"""
    processes = []
    for proc in psutil.process_iter(['pid', 'name', 'cpu_percent']):
        try:
            cpu = proc.info['cpu_percent']
            if cpu > 0:
                processes.append((cpu, proc.info['pid'], proc.info['name']))
        except:
            pass
    
    processes.sort(reverse=True)
    print("🔥 ТОП ПРОЦЕССОВ ПО CPU")
    for cpu, pid, name in processes[:5]:
        print(f"   {cpu:5.1f}% - {name} (PID: {pid})")

# Важные процессы для проверки
critical_processes = ['nginx', 'mysql', 'sshd', 'cron']

print("🔍 ПРОВЕРКА КРИТИЧНЫХ ПРОЦЕССОВ")
for proc in critical_processes:
    if check_process(proc):
        print(f"✅ {proc} - РАБОТАЕТ")
    else:
        print(f"❌ {proc} - НЕ РАБОТАЕТ")

print()
show_top_cpu()