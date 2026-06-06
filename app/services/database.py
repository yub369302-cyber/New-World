"""
Supabase 数据库服务
管理用户认证和档案数据的云端存储
"""
from supabase import create_client, Client

from app.config import settings

_client: Client | None = None


def get_supabase() -> Client:
    """获取 Supabase 客户端单例"""
    global _client
    if _client is None:
        if not settings.SUPABASE_URL or not settings.SUPABASE_KEY:
            raise RuntimeError("Supabase 未配置，请在 .env 中设置 SUPABASE_URL 和 SUPABASE_KEY")
        _client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
    return _client


# ==================== 用户认证 ====================


def sign_up(email: str, password: str) -> dict:
    """用户注册"""
    try:
        client = get_supabase()
        result = client.auth.sign_up({"email": email, "password": password})
        if result.user:
            return {
                "ok": True,
                "user": {
                    "id": result.user.id,
                    "email": result.user.email,
                },
                "session": {
                    "access_token": result.session.access_token if result.session else None,
                    "refresh_token": result.session.refresh_token if result.session else None,
                },
            }
        return {"ok": False, "error": "注册失败，请稍后重试"}
    except Exception as e:
        error_msg = str(e)
        if "already registered" in error_msg.lower() or "already been registered" in error_msg.lower():
            return {"ok": False, "error": "该邮箱已注册，请直接登录"}
        return {"ok": False, "error": f"注册失败: {error_msg}"}


def sign_in(email: str, password: str) -> dict:
    """用户登录"""
    try:
        client = get_supabase()
        result = client.auth.sign_in_with_password({"email": email, "password": password})
        if result.user and result.session:
            return {
                "ok": True,
                "user": {
                    "id": result.user.id,
                    "email": result.user.email,
                },
                "session": {
                    "access_token": result.session.access_token,
                    "refresh_token": result.session.refresh_token,
                },
            }
        return {"ok": False, "error": "登录失败"}
    except Exception as e:
        error_msg = str(e)
        if "invalid" in error_msg.lower():
            return {"ok": False, "error": "邮箱或密码错误"}
        return {"ok": False, "error": f"登录失败: {error_msg}"}


def get_user_from_token(access_token: str) -> dict | None:
    """通过 access_token 获取当前用户信息"""
    try:
        client = get_supabase()
        result = client.auth.get_user(access_token)
        if result.user:
            return {
                "id": result.user.id,
                "email": result.user.email,
            }
        return None
    except Exception:
        return None


def refresh_session(refresh_token: str) -> dict:
    """刷新会话"""
    try:
        client = get_supabase()
        result = client.auth.refresh_session(refresh_token)
        if result.session:
            return {
                "ok": True,
                "session": {
                    "access_token": result.session.access_token,
                    "refresh_token": result.session.refresh_token,
                },
            }
        return {"ok": False, "error": "刷新失败"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ==================== 档案 CRUD ====================


def save_profile(user_id: str, profile_data: dict) -> dict:
    """保存用户档案（upsert）"""
    try:
        client = get_supabase()
        row = {
            "user_id": user_id,
            "profile_data": profile_data,
        }
        result = (
            client.table("profiles")
            .upsert(row, on_conflict="user_id")
            .execute()
        )
        if result.data:
            return {"ok": True, "message": "档案已保存到云端"}
        return {"ok": False, "error": "保存失败"}
    except Exception as e:
        return {"ok": False, "error": f"保存失败: {str(e)}"}


def load_profile(user_id: str) -> dict:
    """加载用户档案"""
    try:
        client = get_supabase()
        result = (
            client.table("profiles")
            .select("profile_data, updated_at")
            .eq("user_id", user_id)
            .maybe_single()
            .execute()
        )
        if result.data:
            return {
                "ok": True,
                "profile": result.data["profile_data"],
                "updated_at": result.data["updated_at"],
            }
        return {"ok": True, "profile": None, "updated_at": None}
    except Exception as e:
        return {"ok": False, "error": f"加载失败: {str(e)}"}
