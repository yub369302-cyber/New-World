"""
Supabase 数据库服务
管理用户认证和档案数据的云端存储
使用 REST API 直接调用，兼容新版 sb_publishable_ 格式的 API key
"""
import httpx

from app.config import settings

# Supabase REST API 基础配置
_base_url = settings.SUPABASE_URL
_api_key = settings.SUPABASE_KEY
_headers = {
    "apikey": _api_key,
    "Content-Type": "application/json",
}


def _auth_headers(access_token: str = None) -> dict:
    """生成请求头"""
    h = {**_headers}
    if access_token:
        h["Authorization"] = f"Bearer {access_token}"
    else:
        h["Authorization"] = f"Bearer {_api_key}"
    return h


# ==================== 用户认证 ====================


def sign_up(email: str, password: str) -> dict:
    """用户注册"""
    try:
        url = f"{_base_url}/auth/v1/signup"
        payload = {"email": email, "password": password}
        with httpx.Client(timeout=15) as client:
            resp = client.post(url, json=payload, headers=_headers)

        if resp.status_code == 200:
            data = resp.json()
            user = data.get("user") or data
            session = data.get("session") or {}
            return {
                "ok": True,
                "user": {
                    "id": user.get("id", ""),
                    "email": user.get("email", email),
                },
                "session": {
                    "access_token": session.get("access_token") or data.get("access_token"),
                    "refresh_token": session.get("refresh_token") or data.get("refresh_token"),
                },
            }
        else:
            error_data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
            error_msg = error_data.get("error_description") or error_data.get("msg") or error_data.get("message") or resp.text
            if "already registered" in str(error_msg).lower():
                return {"ok": False, "error": "该邮箱已注册，请直接登录"}
            return {"ok": False, "error": f"注册失败: {error_msg}"}
    except Exception as e:
        return {"ok": False, "error": f"注册失败: {str(e)}"}


def sign_in(email: str, password: str) -> dict:
    """用户登录"""
    try:
        url = f"{_base_url}/auth/v1/token?grant_type=password"
        payload = {"email": email, "password": password}
        with httpx.Client(timeout=15) as client:
            resp = client.post(url, json=payload, headers=_headers)

        if resp.status_code == 200:
            data = resp.json()
            user = data.get("user", {})
            return {
                "ok": True,
                "user": {
                    "id": user.get("id", ""),
                    "email": user.get("email", email),
                },
                "session": {
                    "access_token": data.get("access_token", ""),
                    "refresh_token": data.get("refresh_token", ""),
                },
            }
        else:
            error_data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
            error_msg = error_data.get("error_description") or error_data.get("msg") or error_data.get("message") or "邮箱或密码错误"
            return {"ok": False, "error": error_msg}
    except Exception as e:
        return {"ok": False, "error": f"登录失败: {str(e)}"}


def get_user_from_token(access_token: str) -> dict | None:
    """通过 access_token 获取当前用户信息"""
    try:
        url = f"{_base_url}/auth/v1/user"
        headers = _auth_headers(access_token)
        with httpx.Client(timeout=10) as client:
            resp = client.get(url, headers=headers)

        if resp.status_code == 200:
            user = resp.json()
            return {
                "id": user.get("id", ""),
                "email": user.get("email", ""),
            }
        return None
    except Exception:
        return None


def refresh_session(refresh_token: str) -> dict:
    """刷新会话"""
    try:
        url = f"{_base_url}/auth/v1/token?grant_type=refresh_token"
        payload = {"refresh_token": refresh_token}
        with httpx.Client(timeout=10) as client:
            resp = client.post(url, json=payload, headers=_headers)

        if resp.status_code == 200:
            data = resp.json()
            return {
                "ok": True,
                "session": {
                    "access_token": data.get("access_token", ""),
                    "refresh_token": data.get("refresh_token", ""),
                },
            }
        return {"ok": False, "error": "刷新失败"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ==================== 档案 CRUD ====================


def save_profile(user_id: str, profile_data: dict) -> dict:
    """保存用户档案（upsert）"""
    try:
        url = f"{_base_url}/rest/v1/profiles"
        headers = _auth_headers(_api_key)
        headers["Prefer"] = "resolution=merge-duplicates"

        row = {
            "user_id": user_id,
            "profile_data": profile_data,
        }
        with httpx.Client(timeout=10) as client:
            resp = client.post(url, json=row, headers=headers)

        if resp.status_code in (200, 201, 204):
            return {"ok": True, "message": "档案已保存到云端"}
        else:
            error_msg = resp.text
            return {"ok": False, "error": f"保存失败: {error_msg}"}
    except Exception as e:
        return {"ok": False, "error": f"保存失败: {str(e)}"}


def load_profile(user_id: str) -> dict:
    """加载用户档案"""
    try:
        url = f"{_base_url}/rest/v1/profiles?user_id=eq.{user_id}&select=profile_data,updated_at"
        headers = _auth_headers(_api_key)
        with httpx.Client(timeout=10) as client:
            resp = client.get(url, headers=headers)

        if resp.status_code == 200:
            data = resp.json()
            if data and len(data) > 0:
                return {
                    "ok": True,
                    "profile": data[0].get("profile_data"),
                    "updated_at": data[0].get("updated_at"),
                }
            return {"ok": True, "profile": None, "updated_at": None}
        return {"ok": False, "error": f"加载失败: {resp.text}"}
    except Exception as e:
        return {"ok": False, "error": f"加载失败: {str(e)}"}
