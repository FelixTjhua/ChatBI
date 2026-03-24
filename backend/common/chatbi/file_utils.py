"""ChatBI 文件工具模块"""

import os
import uuid
import shutil
from typing import Tuple, List, Optional
from datetime import datetime

from fastapi import UploadFile, HTTPException

from common.core.config import settings
from common.utils.locale import I18n

_i18n = I18n("locales")


def _file_trans(lang: str = "zh-CN") -> callable:
    """获取基于语言的翻译函数"""
    _lang = (lang or 'zh-CN').lower().replace('_', '-')
    translations = _i18n.translations.get(_lang, _i18n.translations.get('zh-cn', {}))
    def _t(key: str, **kwargs) -> str:
        keys = key.split('.')
        current = translations
        for k in keys:
            if isinstance(current, dict) and k in current:
                current = current[k]
            else:
                return key
        if isinstance(current, str) and kwargs:
            try:
                return current.format(**kwargs)
            except (KeyError, ValueError):
                return current
        return current if isinstance(current, str) else key
    return _t


class ChatBIFileUtils:
    """ChatBI 文件工具类"""
    
    # 文件存储根目录
    UPLOAD_DIR = getattr(settings, 'UPLOAD_DIR', 'uploads')
    
    @classmethod
    def _ensure_upload_dir(cls) -> str:
        """确保上传目录存在"""
        upload_path = os.path.join(os.getcwd(), cls.UPLOAD_DIR)
        os.makedirs(upload_path, exist_ok=True)
        return upload_path
    
    @classmethod
    def _generate_file_id(cls, filename: str) -> str:
        """生成唯一文件ID"""
        ext = os.path.splitext(filename)[1] if filename else ''
        unique_id = uuid.uuid4().hex[:16]
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        return f"{timestamp}_{unique_id}{ext}"
    
    @staticmethod
    def get_file_path(file_id: str) -> str:
        """获取文件路径"""
        upload_dir = getattr(settings, 'UPLOAD_DIR', 'uploads')
        return os.path.join(os.getcwd(), upload_dir, file_id)
    
    @staticmethod
    def split_filename_and_flag(filename: str) -> Tuple[str, str]:
        """分割文件名和标志"""
        if '__' in filename:
            parts = filename.split('__', 1)
            return parts[1], parts[0]
        return filename, ''
    
    @staticmethod
    def check_file(
        file: UploadFile, 
        file_types: List[str], 
        limit_file_size: int
    ) -> bool:
        """检查文件是否符合要求"""
        if not file or not file.filename:
            raise HTTPException(status_code=400, detail=_file_trans()('i18n_file.file_empty'))
        
        # 检查文件类型
        ext = os.path.splitext(file.filename)[1].lower()
        if file_types and ext not in [t.lower() for t in file_types]:
            raise HTTPException(
                status_code=400, 
                detail=_file_trans()('i18n_file.unsupported_type', ext=ext, types=', '.join(file_types))
            )
        
        # 检查文件大小
        if hasattr(file, 'size') and file.size:
            if file.size > limit_file_size:
                raise HTTPException(
                    status_code=400,
                    detail=_file_trans()('i18n_file.size_exceeded', size=f"{limit_file_size / 1024 / 1024:.1f}")
                )
        
        return True
    
    @classmethod
    def delete_file(cls, file_id: str) -> bool:
        """删除文件"""
        if not file_id:
            return False
            
        try:
            file_path = cls.get_file_path(file_id)
            if os.path.exists(file_path):
                os.remove(file_path)
                return True
            return False
        except Exception:
            return False
    
    @classmethod
    async def upload(cls, file: UploadFile) -> str:
        """上传文件"""
        if not file or not file.filename:
            raise HTTPException(status_code=400, detail=_file_trans()('i18n_file.file_empty'))
        
        # 确保上传目录存在
        upload_path = cls._ensure_upload_dir()
        
        # 生成文件ID
        file_id = cls._generate_file_id(file.filename)
        file_path = os.path.join(upload_path, file_id)
        
        try:
            # 保存文件
            content = await file.read()
            with open(file_path, 'wb') as f:
                f.write(content)
            
            return file_id
            
        except Exception as e:
            # 清理可能创建的文件
            if os.path.exists(file_path):
                os.remove(file_path)
            raise HTTPException(status_code=500, detail=_file_trans()('i18n_file.upload_failed', msg=str(e)))
    
    @classmethod
    def save_file_sync(cls, content: bytes, filename: str) -> str:
        """同步保存文件"""
        upload_path = cls._ensure_upload_dir()
        file_id = cls._generate_file_id(filename)
        file_path = os.path.join(upload_path, file_id)
        
        with open(file_path, 'wb') as f:
            f.write(content)
        
        return file_id


# 导出
__all__ = ['ChatBIFileUtils']
