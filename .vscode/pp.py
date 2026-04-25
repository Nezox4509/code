# modules/backup.py

#!/usr/bin/env python3
"""
Модуль автоматического резервного копирования
Поддерживает: полные, инкрементальные, дифференциальные бэкапы
"""

import os
import shutil
import tarfile
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional
import json
import hashlib

class BackupManager:
    """Класс для управления резервным копированием"""
    
    def __init__(self, config: Dict):
        """
        Инициализация менеджера бэкапов
        :param config: конфигурация бэкапов
        """
        self.config = config
        self.backup_root = Path(config.get('backup_root', '/opt/automation/backups'))
        self.backup_root.mkdir(parents=True, exist_ok=True)
        
        self.retention = config.get('retention', {
            'daily': 7,
            'weekly': 4,
            'monthly': 6
        })
    
    def create_backup(self, source: str, backup_type: str = 'full', 
                      name: str = None) -> Dict:
        """
        Создание резервной копии
        :param source: источник для бэкапа
        :param backup_type: full, incremental, differential
        :param name: имя бэкапа (опционально)
        :return: информация о бэкапе
        """
        if not name:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            name = f"{Path(source).name}_{timestamp}"
        
        # Создание директории для бэкапа
        backup_dir = self.backup_root / name
        backup_dir.mkdir(exist_ok=True)
        
        # Создание архива в зависимости от типа
        if backup_type == 'full':
            result = self._create_full_backup(source, backup_dir)
        elif backup_type == 'incremental':
            result = self._create_incremental_backup(source, backup_dir)
        elif backup_type == 'differential':
            result = self._create_differential_backup(source, backup_dir)
        else:
            raise ValueError(f"Неизвестный тип бэкапа: {backup_type}")
        
        # Сохранение метаданных
        metadata = {
            'name': name,
            'source': source,
            'type': backup_type,
            'created_at': datetime.now().isoformat(),
            'size_bytes': result['size'],
            'files_count': result['files_count'],
            'checksum': self._calculate_checksum(result['archive_path'])
        }
        
        with open(backup_dir / 'metadata.json', 'w') as f:
            json.dump(metadata, f, indent=2)
        
        return metadata
    
    def _create_full_backup(self, source: str, backup_dir: Path) -> Dict:
        """Создание полного бэкапа"""
        source_path = Path(source)
        archive_path = backup_dir / f"{backup_dir.name}.tar.gz"
        
        # Создание tar.gz архива
        with tarfile.open(archive_path, 'w:gz') as tar:
            tar.add(source_path, arcname=source_path.name)
        
        # Подсчет файлов
        files_count = sum(1 for _ in source_path.rglob('*') if _.is_file())
        size = archive_path.stat().st_size
        
        # Сохранение списка файлов
        file_list = backup_dir / 'file_list.txt'
        with open(file_list, 'w') as f:
            for file in source_path.rglob('*'):
                if file.is_file():
                    rel_path = file.relative_to(source_path)
                    f.write(f"{rel_path}\n")
        
        return {
            'archive_path': str(archive_path),
            'size': size,
            'files_count': files_count
        }
    
    def _create_incremental_backup(self, source: str, backup_dir: Path) -> Dict:
        """Создание инкрементального бэкапа"""
        source_path = Path(source)
        last_backup = self._get_last_backup(source)
        
        if not last_backup:
            # Если нет предыдущего бэкапа, создаем полный
            return self._create_full_backup(source, backup_dir)
        
        # Использование rsync для инкрементального копирования
        archive_path = backup_dir / f"{backup_dir.name}_incremental.tar.gz"
        
        # Создание временной директории для измененных файлов
        temp_dir = backup_dir / 'temp'
        temp_dir.mkdir(exist_ok=True)
        
        # Rsync для копирования только измененных файлов
        cmd = [
            'rsync', '-av', '--compare-dest', last_backup['archive_path'],
            '--link-dest', last_backup['archive_path'],
            str(source_path) + '/', str(temp_dir) + '/'
        ]
        subprocess.run(cmd, capture_output=True)
        
        # Архивация измененных файлов
        with tarfile.open(archive_path, 'w:gz') as tar:
            tar.add(temp_dir, arcname='')
        
        # Подсчет файлов
        files_count = sum(1 for _ in temp_dir.rglob('*') if _.is_file())
        size = archive_path.stat().st_size
        
        # Очистка временной директории
        shutil.rmtree(temp_dir)
        
        return {
            'archive_path': str(archive_path),
            'size': size,
            'files_count': files_count,
            'based_on': last_backup['name']
        }
    
    def _create_differential_backup(self, source: str, backup_dir: Path) -> Dict:
        """Создание дифференциального бэкапа"""
        source_path = Path(source)
        last_full_backup = self._get_last_full_backup(source)
        
        if not last_full_backup:
            return self._create_full_backup(source, backup_dir)
        
        archive_path = backup_dir / f"{backup_dir.name}_differential.tar.gz"
        
        # Использование rsync для копирования изменений относительно полного бэкапа
        temp_dir = backup_dir / 'temp'
        temp_dir.mkdir(exist_ok=True)
        
        cmd = [
            'rsync', '-av', '--compare-dest', last_full_backup['archive_path'],
            str(source_path) + '/', str(temp_dir) + '/'
        ]
        subprocess.run(cmd, capture_output=True)
        
        with tarfile.open(archive_path, 'w:gz') as tar:
            tar.add(temp_dir, arcname='')
        
        files_count = sum(1 for _ in temp_dir.rglob('*') if _.is_file())
        size = archive_path.stat().st_size
        
        shutil.rmtree(temp_dir)
        
        return {
            'archive_path': str(archive_path),
            'size': size,
            'files_count': files_count,
            'based_on': last_full_backup['name']
        }
    
    def _get_last_backup(self, source: str) -> Optional[Dict]:
        """Получение последнего бэкапа для источника"""
        backups = []
        for backup_dir in self.backup_root.iterdir():
            if backup_dir.is_dir():
                metadata_file = backup_dir / 'metadata.json'
                if metadata_file.exists():
                    with open(metadata_file, 'r') as f:
                        metadata = json.load(f)
                        if metadata.get('source') == source:
                            backups.append(metadata)
        
        if backups:
            backups.sort(key=lambda x: x['created_at'], reverse=True)
            return backups[0]
        
        return None
    
    def _get_last_full_backup(self, source: str) -> Optional[Dict]:
        """Получение последнего полного бэкапа"""
        backups = []
        for backup_dir in self.backup_root.iterdir():
            if backup_dir.is_dir():
                metadata_file = backup_dir / 'metadata.json'
                if metadata_file.exists():
                    with open(metadata_file, 'r') as f:
                        metadata = json.load(f)
                        if metadata.get('source') == source and metadata.get('type') == 'full':
                            backups.append(metadata)
        
        if backups:
            backups.sort(key=lambda x: x['created_at'], reverse=True)
            return backups[0]
        
        return None
    
    def _calculate_checksum(self, file_path: str) -> str:
        """Вычисление MD5 суммы файла"""
        hash_md5 = hashlib.md5()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    
    def restore_backup(self, backup_name: str, destination: str) -> bool:
        """Восстановление из бэкапа"""
        backup_dir = self.backup_root / backup_name
        
        if not backup_dir.exists():
            print(f"Бэкап {backup_name} не найден")
            return False
        
        metadata_file = backup_dir / 'metadata.json'
        if not metadata_file.exists():
            print(f"Метаданные для {backup_name} не найдены")
            return False
        
        with open(metadata_file, 'r') as f:
            metadata = json.load(f)
        
        archive_path = Path(metadata.get('archive_path'))
        if not archive_path.exists():
            print(f"Архив {archive_path} не найден")
            return False
        
        # Распаковка архива
        destination_path = Path(destination)
        destination_path.mkdir(parents=True, exist_ok=True)
        
        with tarfile.open(archive_path, 'r:gz') as tar:
            tar.extractall(destination_path)
        
        print(f"Бэкап {backup_name} восстановлен в {destination}")
        return True
    
    def rotate_backups(self):
        """Ротация старых бэкапов согласно политике хранения"""
        now = datetime.now()
        
        for backup_dir in self.backup_root.iterdir():
            if not backup_dir.is_dir():
                continue
            
            metadata_file = backup_dir / 'metadata.json'
            if not metadata_file.exists():
                continue
            
            with open(metadata_file, 'r') as f:
                metadata = json.load(f)
            
            created_at = datetime.fromisoformat(metadata['created_at'])
            age_days = (now - created_at).days
            
            # Для daily бэкапов
            if age_days > self.retention.get('daily', 7):
                # Проверяем, не является ли бэкап weekly или monthly
                if created_at.weekday() != 0:  # Не понедельник
                    if age_days > self.retention.get('weekly', 4) * 7:
                        if created_at.day != 1:  # Не первое число
                            # Удаляем старый бэкап
                            shutil.rmtree(backup_dir)
                            print(f"Удален старый бэкап: {backup_dir.name}")
    
    def list_backups(self) -> List[Dict]:
        """Список всех бэкапов"""
        backups = []
        for backup_dir in self.backup_root.iterdir():
            if backup_dir.is_dir():
                metadata_file = backup_dir / 'metadata.json'
                if metadata_file.exists():
                    with open(metadata_file, 'r') as f:
                        metadata = json.load(f)
                        backups.append(metadata)
        
        backups.sort(key=lambda x: x['created_at'], reverse=True)
        return backups
    
    def verify_backup(self, backup_name: str) -> bool:
        """Проверка целостности бэкапа"""
        backup_dir = self.backup_root / backup_name
        
        if not backup_dir.exists():
            return False
        
        metadata_file = backup_dir / 'metadata.json'
        if not metadata_file.exists():
            return False
        
        with open(metadata_file, 'r') as f:
            metadata = json.load(f)
        
        archive_path = Path(metadata['archive_path'])
        
        # Проверка существования архива
        if not archive_path.exists():
            return False
        
        # Проверка контрольной суммы
        current_checksum = self._calculate_checksum(str(archive_path))
        if current_checksum != metadata['checksum']:
            print(f"Контрольная сумма не совпадает для {backup_name}")
            return False
        
        # Проверка целостности tar архива
        try:
            with tarfile.open(archive_path, 'r:gz') as tar:
                # Просто открываем и проверяем
                tar.getmembers()
        except tarfile.TarError as e:
            print(f"Ошибка целостности архива: {e}")
            return False
        
        return True


# Скрипт для автоматического бэкапа
def auto_backup():
    """Автоматическое создание бэкапов по расписанию"""
    import yaml
    
    with open('/opt/automation/config/config.yaml', 'r') as f:
        config = yaml.safe_load(f)
    
    backup_config