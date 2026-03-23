"""Chrome profile decoration and cleanup.

参考 OpenClaw 的 chrome.profile-decoration.ts 实现：
- 配置文件装饰（标识 OpenClaw/Nanobot 管理的配置文件）
- 清理退出（确保浏览器进程正确关闭）
- 配置文件状态管理
"""

import asyncio
import json
import os
import shutil
import signal
import subprocess
import time
from pathlib import Path
from typing import Any

from loguru import logger

PROFILE_DECORATION_FILE = "nanobot_managed.json"
PROFILE_LOCK_FILE = "SingletonLock"
PROFILE_SNAPSHOT_FILE = "profile_snapshot.json"


def is_profile_decorated(user_data_dir: str) -> bool:
    """检查配置文件是否已被 Nanobot 装饰（管理）。"""
    decoration_path = os.path.join(user_data_dir, PROFILE_DECORATION_FILE)
    return os.path.exists(decoration_path)


def decorate_profile(user_data_dir: str, profile_name: str = "default") -> dict[str, Any]:
    """装饰配置文件，标记为 Nanobot 管理。

    这会创建一个装饰文件，包含：
    - 管理标识
    - 创建时间
    - 配置文件名称
    - 版本信息
    """
    decoration_path = os.path.join(user_data_dir, PROFILE_DECORATION_FILE)

    decoration_data = {
        "managed_by": "nanobot",
        "profile_name": profile_name,
        "created_at": time.time(),
        "version": "1.0",
        "decorated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }

    try:
        with open(decoration_path, "w", encoding="utf-8") as f:
            json.dump(decoration_data, f, indent=2)

        logger.info(f"Decorated profile: {user_data_dir} (name: {profile_name})")
        return decoration_data
    except Exception as e:
        logger.error(f"Failed to decorate profile: {e}")
        raise


def undecorate_profile(user_data_dir: str) -> bool:
    """移除配置文件装饰。"""
    decoration_path = os.path.join(user_data_dir, PROFILE_DECORATION_FILE)

    try:
        if os.path.exists(decoration_path):
            os.remove(decoration_path)
            logger.info(f"Removed decoration from profile: {user_data_dir}")
        return True
    except Exception as e:
        logger.error(f"Failed to undecorate profile: {e}")
        return False


def create_profile_snapshot(user_data_dir: str) -> dict[str, Any]:
    """创建配置文件快照（用于状态恢复）。"""
    snapshot = {
        "timestamp": time.time(),
        "files": [],
        "directories": [],
        "total_size": 0,
    }

    try:
        total_size = 0
        file_count = 0
        dir_count = 0

        for root, dirs, files in os.walk(user_data_dir):
            # Skip symlinks
            dirs[:] = [d for d in dirs if not os.path.islink(os.path.join(root, d))]

            for name in files:
                file_path = os.path.join(root, name)
                try:
                    size = os.path.getsize(file_path)
                    snapshot["files"].append(
                        {
                            "path": os.path.relpath(file_path, user_data_dir),
                            "size": size,
                            "mtime": os.path.getmtime(file_path),
                        }
                    )
                    total_size += size
                    file_count += 1
                except OSError:
                    pass

            dir_count += len(dirs)

        snapshot["total_size"] = total_size
        snapshot["file_count"] = file_count
        snapshot["directory_count"] = dir_count

        # Save snapshot
        snapshot_path = os.path.join(user_data_dir, PROFILE_SNAPSHOT_FILE)
        with open(snapshot_path, "w", encoding="utf-8") as f:
            json.dump(snapshot, f, indent=2)

        logger.info(f"Created profile snapshot: {file_count} files, {total_size / 1024:.1f} KB")
        return snapshot
    except Exception as e:
        logger.error(f"Failed to create profile snapshot: {e}")
        return snapshot


def get_profile_size(user_data_dir: str) -> int:
    """获取配置文件总大小（字节）。"""
    total_size = 0

    for root, dirs, files in os.walk(user_data_dir):
        dirs[:] = [d for d in dirs if not os.path.islink(os.path.join(root, d))]

        for name in files:
            try:
                total_size += os.path.getsize(os.path.join(root, name))
            except OSError:
                pass

    return total_size


async def ensure_profile_clean_exit(
    user_data_dir: str,
    pid: int | None = None,
    timeout: float = 5.0,
) -> bool:
    """确保浏览器配置文件正确退出（清理锁文件）。

    Chrome 会在用户数据目录创建 SingletonLock 文件。
    如果浏览器非正常退出，这个文件会残留，导致无法重新启动。

    此函数：
    1. 等待浏览器进程退出
    2. 清理锁文件
    3. 创建快照
    """
    logger.info(f"Ensuring clean exit for profile: {user_data_dir}")

    # 1. 等待进程退出
    if pid:
        try:
            # 检查进程是否存在
            os.kill(pid, 0)

            # 等待进程退出
            start_time = time.time()
            while time.time() - start_time < timeout:
                try:
                    os.kill(pid, 0)
                    await asyncio.sleep(0.1)
                except OSError:
                    # 进程已退出
                    logger.info(f"Browser process {pid} exited")
                    break
            else:
                # 超时，强制终止
                logger.warning(f"Browser process {pid} did not exit gracefully, forcing...")
                try:
                    os.kill(pid, signal.SIGKILL)
                except OSError:
                    pass
        except OSError:
            # 进程已不存在
            pass

    # 2. 清理锁文件
    lock_file = os.path.join(user_data_dir, PROFILE_LOCK_FILE)
    if os.path.exists(lock_file):
        try:
            os.remove(lock_file)
            logger.info(f"Removed lock file: {lock_file}")
        except Exception as e:
            logger.warning(f"Failed to remove lock file: {e}")

    # 3. 清理其他临时文件
    temp_files = [
        "SingletonCookie",
        "chrome_shutdown_ms.txt",
        "Last Browser",
        "Last Session",
        "Last Tabs",
    ]

    for temp_file in temp_files:
        temp_path = os.path.join(user_data_dir, temp_file)
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception as e:
                logger.debug(f"Failed to remove temp file {temp_file}: {e}")

    # 4. 创建快照
    create_profile_snapshot(user_data_dir)

    logger.info(f"Profile clean exit completed: {user_data_dir}")
    return True


def cleanup_profile(user_data_dir: str, keep_managed: bool = True) -> bool:
    """清理配置文件目录。

    Args:
        user_data_dir: 配置文件目录路径
        keep_managed: 如果为 True，保留 nanobot_managed.json 文件

    Returns:
        清理是否成功
    """
    logger.info(f"Cleaning up profile: {user_data_dir}")

    try:
        if not os.path.exists(user_data_dir):
            return True

        # 保存装饰文件（如果需要保留）
        decoration_data = None
        if keep_managed:
            decoration_path = os.path.join(user_data_dir, PROFILE_DECORATION_FILE)
            if os.path.exists(decoration_path):
                with open(decoration_path, "r", encoding="utf-8") as f:
                    decoration_data = json.load(f)

        # 删除目录
        shutil.rmtree(user_data_dir)

        # 重新创建目录
        os.makedirs(user_data_dir, exist_ok=True)

        # 恢复装饰文件
        if decoration_data:
            decoration_path = os.path.join(user_data_dir, PROFILE_DECORATION_FILE)
            with open(decoration_path, "w", encoding="utf-8") as f:
                json.dump(decoration_data, f, indent=2)

        logger.info(f"Profile cleaned up: {user_data_dir}")
        return True
    except Exception as e:
        logger.error(f"Failed to cleanup profile: {e}")
        return False


def backup_profile(user_data_dir: str, backup_dir: str | None = None) -> str | None:
    """备份配置文件。

    Args:
        user_data_dir: 配置文件目录
        backup_dir: 备份目录（默认在配置文件目录旁创建 .backup）

    Returns:
        备份目录路径，如果失败则返回 None
    """
    if not backup_dir:
        backup_dir = user_data_dir + ".backup"

    logger.info(f"Backing up profile to: {backup_dir}")

    try:
        # 如果备份目录已存在，添加时间戳
        if os.path.exists(backup_dir):
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            backup_dir = f"{backup_dir}_{timestamp}"

        shutil.copytree(
            user_data_dir,
            backup_dir,
            ignore=shutil.ignore_patterns(
                "*.log",
                "*.lock",
                "Singleton*",
                "chrome_*.pak",
            ),
        )

        logger.info(f"Profile backed up to: {backup_dir}")
        return backup_dir
    except Exception as e:
        logger.error(f"Failed to backup profile: {e}")
        return None


def restore_profile(backup_dir: str, user_data_dir: str) -> bool:
    """恢复配置文件。

    Args:
        backup_dir: 备份目录
        user_data_dir: 目标配置文件目录

    Returns:
        恢复是否成功
    """
    logger.info(f"Restoring profile from {backup_dir} to {user_data_dir}")

    try:
        if not os.path.exists(backup_dir):
            logger.error(f"Backup directory not found: {backup_dir}")
            return False

        # 删除现有配置文件
        if os.path.exists(user_data_dir):
            shutil.rmtree(user_data_dir)

        # 恢复备份
        shutil.copytree(backup_dir, user_data_dir)

        logger.info(f"Profile restored successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to restore profile: {e}")
        return False


def get_profile_info(user_data_dir: str) -> dict[str, Any]:
    """获取配置文件信息。"""
    info = {
        "path": user_data_dir,
        "exists": os.path.exists(user_data_dir),
        "managed": False,
        "size": 0,
        "files": 0,
        "directories": 0,
        "decoration": None,
    }

    if not info["exists"]:
        return info

    # 检查是否被管理
    info["managed"] = is_profile_decorated(user_data_dir)

    # 获取装饰信息
    if info["managed"]:
        decoration_path = os.path.join(user_data_dir, PROFILE_DECORATION_FILE)
        try:
            with open(decoration_path, "r", encoding="utf-8") as f:
                info["decoration"] = json.load(f)
        except Exception:
            pass

    # 统计大小和文件数
    info["size"] = get_profile_size(user_data_dir)

    try:
        for root, dirs, files in os.walk(user_data_dir):
            dirs[:] = [d for d in dirs if not os.path.islink(os.path.join(root, d))]
            info["directories"] += len(dirs)
            info["files"] += len(files)
    except Exception:
        pass

    return info


class ProfileManager:
    """配置文件管理器。"""

    def __init__(self, base_dir: str):
        self.base_dir = base_dir
        self.profiles: dict[str, str] = {}  # profile_name -> user_data_dir

    def get_profile_dir(self, profile_name: str) -> str:
        """获取配置文件目录。"""
        from nanobot.config.paths import get_data_dir

        base = get_data_dir()
        return os.path.join(base, "browser", profile_name, "user-data")

    def create_profile(self, profile_name: str) -> str:
        """创建新的配置文件。"""
        user_data_dir = self.get_profile_dir(profile_name)
        os.makedirs(user_data_dir, exist_ok=True)
        decorate_profile(user_data_dir, profile_name)
        self.profiles[profile_name] = user_data_dir
        logger.info(f"Created profile: {profile_name}")
        return user_data_dir

    async def cleanup(self, profile_name: str, pid: int | None = None) -> bool:
        """清理配置文件。"""
        if profile_name not in self.profiles:
            return True

        user_data_dir = self.profiles[profile_name]
        return await ensure_profile_clean_exit(user_data_dir, pid)

    def list_profiles(self) -> list[dict[str, Any]]:
        """列出所有配置文件。"""
        from nanobot.config.paths import get_data_dir

        base = os.path.join(get_data_dir(), "browser")

        profiles = []
        if os.path.exists(base):
            for name in os.listdir(base):
                profile_dir = os.path.join(base, name, "user-data")
                if os.path.exists(profile_dir):
                    info = get_profile_info(profile_dir)
                    info["name"] = name
                    profiles.append(info)

        return profiles

    def delete_profile(self, profile_name: str) -> bool:
        """删除配置文件。"""
        if profile_name not in self.profiles:
            return False

        user_data_dir = self.profiles[profile_name]

        try:
            shutil.rmtree(user_data_dir)
            del self.profiles[profile_name]
            logger.info(f"Deleted profile: {profile_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete profile: {e}")
            return False


__all__ = [
    "ProfileManager",
    "backup_profile",
    "cleanup_profile",
    "create_profile_snapshot",
    "decorate_profile",
    "ensure_profile_clean_exit",
    "get_profile_info",
    "get_profile_size",
    "is_profile_decorated",
    "restore_profile",
    "undecorate_profile",
]
