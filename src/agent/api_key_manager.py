# -*- coding: utf-8 -*-
"""
API密钥管理器

提供API密钥的加密存储和访问功能：
- 使用Fernet对称加密保护密钥
- 基于机器特征生成加密密钥
- 集成到SQLite数据库

使用方式:
    from src.agent.api_key_manager import ApiKeyManager

    manager = ApiKeyManager()
    manager.store_key("openai", "sk-xxxxx")
    key = manager.get_key("openai")
"""

import hashlib
import os
import platform
import uuid
from pathlib import Path
from typing import Optional, List

from cryptography.fernet import Fernet
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.storage.database import Database
from src.storage.models import ApiKeyRecord
from src.utils.logger import get_logger

_logger = get_logger(__name__)


class ApiKeyManager:
    """
    API密钥管理器

    管理各AI服务商的API密钥，提供加密存储和安全访问

    Example:
        >>> manager = ApiKeyManager()
        >>> manager.store_key("openai", "sk-xxxxx")
        >>> key = manager.get_key("openai")
        >>> print(key)
        sk-xxxxx
    """

    def __init__(self, db: Optional[Database] = None):
        if db is None:
            from pathlib import Path

            db_path = Path.home() / ".office_tools" / "data.db"
            db = Database(db_path)

        self._db = db
        self._db.create_tables()
        self._fernet = self._init_fernet()
        _logger.info("API密钥管理器初始化完成")

    def _init_fernet(self) -> Fernet:
        """
        初始化Fernet加密器

        基于机器特征生成稳定的加密密钥

        Returns:
            Fernet加密器实例
        """
        # 获取或生成加密密钥
        key = self._get_or_create_encryption_key()
        return Fernet(key)

    def _get_or_create_encryption_key(self) -> bytes:
        """
        获取或创建加密密钥

        策略：
        1. 尝试从配置文件读取
        2. 如果不存在，基于机器特征生成并保存

        Returns:
            Fernet格式的加密密钥
        """
        # 加密密钥文件路径
        config_dir = Path.home() / ".office_tools"
        config_dir.mkdir(exist_ok=True)
        key_file = config_dir / ".encryption_key"

        # 尝试读取现有密钥
        if key_file.exists():
            try:
                key = key_file.read_bytes()
                # 验证密钥格式
                Fernet(key)
                _logger.debug("从配置文件加载加密密钥")
                return key
            except Exception as e:
                _logger.warning(f"加密密钥文件损坏，将重新生成: {e}")

        # 生成新密钥
        key = self._generate_machine_key()
        key_file.write_bytes(key)
        key_file.chmod(0o600)  # 仅所有者可读写
        _logger.info("生成新的加密密钥并保存到配置文件")

        return key

    def _generate_machine_key(self) -> bytes:
        """
        基于机器特征生成加密密钥

        使用机器名、系统ID等生成稳定的密钥

        Returns:
            Fernet格式的加密密钥
        """
        # 收集机器特征
        machine_id = platform.node()  # 计算机名
        system_id = platform.system()  # 操作系统类型
        user_id = os.getenv("USER", "default")  # 用户名

        # 生成唯一标识
        unique_str = f"{machine_id}-{system_id}-{user_id}-office-tools"

        # 生成32字节密钥
        hash_bytes = hashlib.sha256(unique_str.encode()).digest()

        # 转换为Fernet格式（需要base64编码的32字节）
        import base64

        key = base64.urlsafe_b64encode(hash_bytes)

        return key

    def store_key(
        self,
        provider: str,
        api_key: str,
        base_url: Optional[str] = None,
        model_name: Optional[str] = None,
    ) -> None:
        """
        存储API密钥（加密）

        Args:
            provider: 服务商名称（如 "openai", "anthropic"）
            api_key: API密钥明文
            base_url: API基础URL（可选）
            model_name: 模型名称（可选）

        Example:
            >>> manager.store_key("openai", "sk-xxxxx")
        """
        # 加密密钥
        encrypted_key = self._fernet.encrypt(api_key.encode()).decode()

        # 保存到数据库
        with Session(self._db.engine) as session:
            # 检查是否已存在（provider + model_name 联合唯一）
            stmt = select(ApiKeyRecord).where(
                ApiKeyRecord.provider == provider,
                ApiKeyRecord.model_name == model_name,
            )
            existing = session.execute(stmt).scalar_one_or_none()

            if existing:
                existing.encrypted_key = encrypted_key
                existing.base_url = base_url
                existing.model_name = model_name
                _logger.info(f"更新API密钥: {provider}/{model_name or 'default'}")
            else:
                record = ApiKeyRecord(
                    provider=provider,
                    encrypted_key=encrypted_key,
                    base_url=base_url,
                    model_name=model_name,
                )
                session.add(record)
                _logger.info(f"存储新API密钥: {provider}/{model_name or 'default'}")

            session.commit()

    def get_key(self, provider: str, model_name: Optional[str] = None) -> Optional[str]:
        with Session(self._db.engine) as session:
            if model_name is not None:
                stmt = select(ApiKeyRecord).where(
                    ApiKeyRecord.provider == provider,
                    ApiKeyRecord.model_name == model_name,
                )
                record = session.execute(stmt).scalar_one_or_none()
            else:
                stmt = select(ApiKeyRecord).where(ApiKeyRecord.provider == provider).limit(1)
                record = session.execute(stmt).scalar_one_or_none()

            if not record:
                _logger.debug(f"未找到API密钥: {provider}/{model_name or 'default'}")
                return None

            try:
                decrypted = self._fernet.decrypt(record.encrypted_key.encode())
                return decrypted.decode()
            except Exception as e:
                _logger.error(f"解密API密钥失败: {provider}/{model_name or 'default'} - {e}")
                return None

    def delete_key(self, provider: str, model_name: Optional[str] = None) -> bool:
        with Session(self._db.engine) as session:
            stmt = select(ApiKeyRecord).where(
                ApiKeyRecord.provider == provider,
                ApiKeyRecord.model_name == model_name,
            )
            record = session.execute(stmt).scalar_one_or_none()

            if not record:
                _logger.warning(f"未找到要删除的API密钥: {provider}/{model_name or 'default'}")
                return False

            session.delete(record)
            session.commit()
            _logger.info(f"已删除API密钥: {provider}/{model_name or 'default'}")
            return True

    def list_providers(self) -> list[str]:
        """
        列出所有已存储的服务商

        Returns:
            服务商名称列表

        Example:
            >>> providers = manager.list_providers()
            >>> print(providers)
            ['openai', 'anthropic']
        """
        with Session(self._db.engine) as session:
            stmt = select(ApiKeyRecord.provider)
            result = session.execute(stmt)
            return [row[0] for row in result]

    def has_key(self, provider: str, model_name: Optional[str] = None) -> bool:
        return self.get_key(provider, model_name) is not None

    def set_enabled(self, provider: str, enabled: bool, model_name: Optional[str] = None) -> bool:
        with Session(self._db.engine) as session:
            stmt = select(ApiKeyRecord).where(
                ApiKeyRecord.provider == provider,
                ApiKeyRecord.model_name == model_name,
            )
            record = session.execute(stmt).scalar_one_or_none()

            if not record:
                _logger.warning(f"未找到API密钥: {provider}/{model_name or 'default'}")
                return False

            record.enabled = enabled
            session.commit()
            status = "启用" if enabled else "禁用"
            _logger.info(f"{status}API密钥: {provider}/{model_name or 'default'}")
            return True

    def list_all_configs(self) -> List[dict]:
        with Session(self._db.engine) as session:
            stmt = select(ApiKeyRecord)
            result = session.execute(stmt)
            records = result.scalars().all()
            return [
                {
                    "provider": r.provider,
                    "base_url": r.base_url,
                    "model_name": r.model_name,
                    "enabled": r.enabled,
                    "created_at": r.created_at,
                    "updated_at": r.updated_at,
                }
                for r in records
            ]

    def get_config(self, provider: str, model_name: Optional[str] = None) -> Optional[dict]:
        with Session(self._db.engine) as session:
            if model_name is not None:
                stmt = select(ApiKeyRecord).where(
                    ApiKeyRecord.provider == provider,
                    ApiKeyRecord.model_name == model_name,
                )
            else:
                stmt = select(ApiKeyRecord).where(ApiKeyRecord.provider == provider).limit(1)
            record = session.execute(stmt).scalar_one_or_none()

            if not record:
                return None

            return {
                "provider": record.provider,
                "api_key": self.get_key(provider, record.model_name),
                "base_url": record.base_url,
                "model_name": record.model_name,
                "enabled": record.enabled,
                "created_at": record.created_at,
                "updated_at": record.updated_at,
            }

    def update_config(self, provider: str, model_name: Optional[str] = None, **kwargs) -> bool:
        allowed_fields = {"base_url", "model_name"}
        update_fields = {k: v for k, v in kwargs.items() if k in allowed_fields}

        if not update_fields:
            return False

        with Session(self._db.engine) as session:
            stmt = select(ApiKeyRecord).where(
                ApiKeyRecord.provider == provider,
                ApiKeyRecord.model_name == model_name,
            )
            record = session.execute(stmt).scalar_one_or_none()

            if not record:
                _logger.warning(f"未找到API密钥: {provider}/{model_name or 'default'}")
                return False

            for field, value in update_fields.items():
                setattr(record, field, value)

            session.commit()
            _logger.info(f"更新API密钥配置: {provider}/{model_name or 'default'} - {update_fields}")
            return True
