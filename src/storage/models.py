# -*- coding: utf-8 -*-
"""
SQLAlchemy ORM模型

定义所有数据库表结构：
- Base: 声明基类
- PluginRecord: 插件记录
- SettingRecord: 设置记录
- PluginPermissionRecord: 插件权限授权记录
"""

from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """SQLAlchemy声明基类"""

    pass


class PluginRecord(Base):
    """
    插件记录表

    存储已安装插件的基本信息

    Attributes:
        id: 主键
        name: 插件名称（唯一）
        version: 插件版本
        enabled: 是否启用
        created_at: 创建时间
        updated_at: 更新时间
    """

    __tablename__ = "plugins"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    version: Mapped[str] = mapped_column(String(50), nullable=False, default="1.0.0")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.now,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.now,
        onupdate=datetime.now,
    )

    # 关联的权限记录
    permissions: Mapped[List["PluginPermissionRecord"]] = relationship(
        "PluginPermissionRecord",
        back_populates="plugin",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<PluginRecord {self.name} v{self.version}>"


class SettingRecord(Base):
    """
    设置记录表

    存储应用程序和插件的配置

    Attributes:
        key: 设置键（主键）
        value: 设置值（JSON字符串）
        plugin_name: 关联的插件名（null表示全局设置）
        created_at: 创建时间
        updated_at: 更新时间
    """

    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(255), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    plugin_name: Mapped[Optional[str]] = mapped_column(
        String(255),
        ForeignKey("plugins.name", ondelete="CASCADE"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.now,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.now,
        onupdate=datetime.now,
    )

    # 关联的插件
    plugin: Mapped[Optional["PluginRecord"]] = relationship(
        "PluginRecord",
        backref="settings",
    )

    def __repr__(self) -> str:
        return f"<SettingRecord {self.key}>"


class PluginPermissionRecord(Base):
    """
    插件权限授权记录表

    存储插件被授权的权限

    Attributes:
        id: 主键
        plugin_name: 插件名称
        permission: 权限标识
        granted_at: 授权时间
        granted_by_user: 授权用户（null表示系统自动授权）
    """

    __tablename__ = "plugin_permissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    plugin_name: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("plugins.name", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    permission: Mapped[str] = mapped_column(String(100), nullable=False)
    granted_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.now,
    )
    granted_by_user: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # 关联的插件
    plugin: Mapped["PluginRecord"] = relationship(
        "PluginRecord",
        back_populates="permissions",
    )

    def __repr__(self) -> str:
        return f"<PluginPermissionRecord {self.plugin_name}:{self.permission}>"


class WorkflowRecord(Base):
    """
    工作流记录表

    存储保存的工作流定义

    Attributes:
        id: 主键
        name: 工作流名称
        graph_json: 工作流图定义（JSON）
        created_at: 创建时间
        updated_at: 更新时间
    """

    __tablename__ = "workflows"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    graph_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.now,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.now,
        onupdate=datetime.now,
    )

    def __repr__(self) -> str:
        return f"<WorkflowRecord {self.name}>"


class ApiKeyRecord(Base):
    """
    API密钥记录表

    存储各服务商的API密钥（加密存储）

    Attributes:
        id: 主键
        provider: 服务商名称（如 openai, anthropic）
        encrypted_key: 加密后的密钥
        created_at: 创建时间
        updated_at: 更新时间
    """

    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    provider: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    encrypted_key: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.now,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.now,
        onupdate=datetime.now,
    )

    def __repr__(self) -> str:
        return f"<ApiKeyRecord {self.provider}>"


class NodePackageRecord(Base):
    """
    节点包记录表

    存储已安装的节点包信息

    Attributes:
        id: 包唯一标识
        name: 显示名称
        version: 版本号
        author: 作者
        description: 描述
        repository_url: Git仓库地址
        branch: 分支
        local_path: 本地安装路径
        enabled: 是否启用
        installed_at: 安装时间
        updated_at: 更新时间
    """

    __tablename__ = "node_packages"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    author: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    repository_url: Mapped[str] = mapped_column(String(500), nullable=False)
    branch: Mapped[str] = mapped_column(String(100), nullable=False, default="main")
    local_path: Mapped[str] = mapped_column(String(500), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    installed_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.now,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.now,
        onupdate=datetime.now,
    )

    def __repr__(self) -> str:
        return f"<NodePackageRecord {self.name} v{self.version}>"
