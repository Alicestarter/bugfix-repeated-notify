"""GitHub REST API client."""

from __future__ import annotations

import aiohttp
from astrbot.api import logger

API_BASE = "https://api.github.com"


class GitHubAPI:
    """极简 GitHub REST API 客户端，支持可选 Token 认证。"""

    def __init__(self, token: str = ""):
        self._token = (token or "").strip()
        self._session: aiohttp.ClientSession | None = None

    async def _ensure_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            headers = {"Accept": "application/vnd.github+json"}
            if self._token:
                headers["Authorization"] = f"Bearer {self._token}"
            self._session = aiohttp.ClientSession(headers=headers)
        return self._session

    async def _get(self, path: str, params: dict | None = None):
        """GET 请求。返回 (status, data)；网络失败返回 (-1, None)。"""
        session = await self._ensure_session()
        url = f"{API_BASE}{path}"
        try:
            async with session.get(url, params=params) as resp:
                if resp.status in (204, 404):
                    return resp.status, None
                try:
                    data = await resp.json()
                except Exception:
                    data = None
                return resp.status, data
        except Exception as e:
            logger.warning(f"GitHub Webhook: GitHub API request failed ({path}): {e}")
            return -1, None

    async def get_user(self, login: str) -> dict | None:
        """获取用户信息（followers 等）。"""
        status, data = await self._get(f"/users/{login}")
        return data if status == 200 and isinstance(data, dict) else None

    async def get_repo(self, full_name: str) -> dict | None:
        """获取仓库信息（license、stargazers_count、forks_count 等）。"""
        status, data = await self._get(f"/repos/{full_name}")
        return data if status == 200 and isinstance(data, dict) else None

    async def get_readme_sha(self, full_name: str) -> str | None:
        """返回 README 的 sha；不存在返回 ""；请求失败返回 None。"""
        status, data = await self._get(f"/repos/{full_name}/readme")
        if status == 200 and isinstance(data, dict):
            return data.get("sha", "")
        if status == 404:
            return ""
        return None

    async def list_files(self, full_name: str, branch: str) -> list[str] | None:
        """列出仓库文件路径（用于敏感文件扫描）。"""
        status, data = await self._get(
            f"/repos/{full_name}/git/trees/{branch}", {"recursive": "1"}
        )
        if status != 200 or not isinstance(data, dict):
            return None
        tree = data.get("tree", [])
        return [item.get("path", "") for item in tree if item.get("type") == "blob"]

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()
