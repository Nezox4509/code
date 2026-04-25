import os
import pwd
import grp
from pathlib import Path

def audit_sensitive_files(sensitive_paths):
    """Проверяет права доступа к критичным файлам."""
    violations = []
    
    for path in sensitive_paths:
        stat = os.stat(path)
        mode = stat.st_mode
        
        # Проверка на запись для группы и других
        if mode & 0o022:  # групповые или другие имеют право на запись
            violations.append({
                'file': path,
                'permissions': oct(mode)[-3:],
                'owner': pwd.getpwuid(stat.st_uid).pw_name,
                'problem': 'Write permissions for group/others'
            })
        
        # Проверка на SUID биты на неожиданных файлах
        if mode & 0o4000 and path not in ['/bin/su', '/usr/bin/sudo']:
            violations.append({
                'file': path,
                'permissions': oct(mode)[-3:],
                'problem': 'Unexpected SUID bit'
            })
    
    return violations