"""
Job Hunter - 智能求职推荐系统
主入口文件：FastAPI 应用 + API 路由
"""
import os
import json
import asyncio
from datetime import datetime
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.requests import Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional

from app.config import settings
from app.services import database as db

# 检测是否在 Vercel 无服务器环境中运行
IS_VERCEL = bool(os.environ.get("VERCEL") or os.environ.get("VERCEL_ENV"))

# 仅在非 Vercel 环境下导入需要长驻进程的模块
if not IS_VERCEL:
    from app.services.scheduler import setup_scheduler, run_now, scheduler
    from app.services.pipeline import run_pipeline
    from app.services.ai_analyzer import AIAnalyzer
    from app.scrapers.boss_scraper import BossScraper

# 运行状态跟踪
run_history: list = []
is_running: bool = False
latest_jobs: list = []  # 最新推荐的岗位列表


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    if not IS_VERCEL:
        # 仅在本地运行时启动调度器
        setup_scheduler()
        print("\n[Job Hunter] 已启动!")
        print(f"   调度时间: 每天 {settings.SCHEDULE_HOURS} 点")
        print(f"   搜索关键词: {settings.JOB_KEYWORDS}")
        print(f"   目标城市: {settings.JOB_CITIES}")
        print(f"   邮箱推送: {settings.RECIPIENT_EMAIL}")
        print("\n[Web] 访问管理面板: http://localhost:8000")
    yield
    if not IS_VERCEL:
        # 关闭时停止调度器
        scheduler.shutdown(wait=False)
        print("\n[Job Hunter] 已停止")


# 创建 FastAPI 应用
app = FastAPI(
    title="Job Hunter - 智能求职推荐系统",
    description="自动抓取岗位、AI匹配分析、邮件推送",
    version="1.0.0",
    lifespan=lifespan,
)

# 挂载静态文件和模板
BASE_DIR = Path(__file__).resolve().parent
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "app" / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "app" / "templates"))


# ==================== 页面路由 ====================


@app.get("/")
async def index(request: Request):
    """管理面板首页"""
    return templates.TemplateResponse("index.html", {"request": request, "config": settings})


# ==================== API 路由 ====================


@app.post("/api/run")
async def api_run(background_tasks: BackgroundTasks):
    """手动触发一次完整流程"""
    global is_running

    if IS_VERCEL:
        return JSONResponse(
            status_code=503,
            content={"status": "unavailable", "message": "云端部署不支持后台任务，请在本地运行此功能"},
        )

    if is_running:
        return JSONResponse(
            status_code=429,
            content={"status": "busy", "message": "已有任务正在执行中，请稍后再试"},
        )

    background_tasks.add_task(_execute_pipeline)
    return {"status": "started", "message": "任务已启动，请稍后查看结果"}


async def _execute_pipeline():
    """后台执行流程并记录结果"""
    global is_running, latest_jobs
    is_running = True

    try:
        result = await run_pipeline()
        result["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        run_history.insert(0, result)
        # 保存岗位详情供前端使用
        if "jobs" in result:
            latest_jobs = result["jobs"]
        # 只保留最近 50 条记录
        if len(run_history) > 50:
            run_history.pop()
    except Exception as e:
        run_history.insert(0, {
            "status": "error",
            "message": str(e),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        })
    finally:
        is_running = False


@app.get("/api/history")
async def api_history():
    """获取运行历史"""
    return {
        "history": run_history,
        "is_running": is_running,
    }


@app.get("/api/config")
async def api_config():
    """获取当前配置（脱敏）"""
    return {
        "keywords": settings.JOB_KEYWORDS,
        "cities": settings.JOB_CITIES,
        "job_type": settings.JOB_TYPE,
        "exclude_keywords": settings.JOB_EXCLUDE_KEYWORDS,
        "schedule_hours": settings.SCHEDULE_HOURS,
        "recipient_email": _mask_email(settings.RECIPIENT_EMAIL),
        "openai_model": settings.OPENAI_MODEL,
        "resume_summary": settings.RESUME_SUMMARY[:50] + "...",
        "has_serpapi_key": bool(settings.SERPAPI_KEY),
        "has_openai_key": bool(settings.OPENAI_API_KEY),
        "has_smtp_config": bool(settings.SMTP_USER and settings.SMTP_PASSWORD),
    }


@app.get("/api/status")
async def api_status():
    """系统状态"""
    next_run = None
    scheduler_running = False

    if not IS_VERCEL:
        jobs = scheduler.get_jobs()
        if jobs:
            next_run_time = jobs[0].next_run_time
            if next_run_time:
                next_run = next_run_time.strftime("%Y-%m-%d %H:%M:%S")
        scheduler_running = scheduler.running

    return {
        "is_running": is_running,
        "scheduler_running": scheduler_running,
        "next_run": next_run,
        "total_runs": len(run_history),
        "last_run": run_history[0] if run_history else None,
    }


@app.get("/api/health")
async def api_health():
    """健康检查"""
    return {"status": "ok", "timestamp": datetime.now().isoformat()}


@app.get("/api/debug/supabase")
async def api_debug_supabase():
    """调试：检查 Supabase 配置是否加载（不暴露完整密钥）"""
    url = settings.SUPABASE_URL
    key = settings.SUPABASE_KEY
    return {
        "supabase_url_set": bool(url),
        "supabase_url_prefix": url[:30] + "..." if url else "",
        "supabase_key_set": bool(key),
        "supabase_key_prefix": key[:20] + "..." if key else "",
        "supabase_key_length": len(key) if key else 0,
    }


# ==================== 用户认证 API ====================


def _get_token(request: Request) -> str | None:
    """从请求头提取 access_token"""
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:]
    return None


def _require_user(request: Request) -> dict | None:
    """校验用户身份，返回 user dict 或 None"""
    token = _get_token(request)
    if not token:
        return None
    return db.get_user_from_token(token)


@app.post("/api/auth/register")
async def api_register(request: Request):
    """用户注册"""
    data = await request.json()
    email = data.get("email", "").strip()
    password = data.get("password", "")
    if not email or not password:
        return JSONResponse(status_code=400, content={"ok": False, "error": "请输入邮箱和密码"})
    if len(password) < 6:
        return JSONResponse(status_code=400, content={"ok": False, "error": "密码至少 6 位"})
    result = db.sign_up(email, password)
    if not result["ok"]:
        return JSONResponse(status_code=400, content=result)
    return result


@app.post("/api/auth/login")
async def api_login(request: Request):
    """用户登录"""
    data = await request.json()
    email = data.get("email", "").strip()
    password = data.get("password", "")
    if not email or not password:
        return JSONResponse(status_code=400, content={"ok": False, "error": "请输入邮箱和密码"})
    result = db.sign_in(email, password)
    if not result["ok"]:
        return JSONResponse(status_code=401, content=result)
    return result


@app.get("/api/auth/me")
async def api_me(request: Request):
    """获取当前登录用户信息"""
    user = _require_user(request)
    if not user:
        return JSONResponse(status_code=401, content={"ok": False, "error": "未登录或会话已过期"})
    return {"ok": True, "user": user}


@app.post("/api/auth/refresh")
async def api_refresh(request: Request):
    """刷新会话 token"""
    data = await request.json()
    refresh_token = data.get("refresh_token", "")
    if not refresh_token:
        return JSONResponse(status_code=400, content={"ok": False, "error": "缺少 refresh_token"})
    return db.refresh_session(refresh_token)


# ==================== 档案 API（需登录） ====================


@app.post("/api/profile")
async def api_save_profile(request: Request):
    """保存用户档案到云端"""
    user = _require_user(request)
    if not user:
        return JSONResponse(status_code=401, content={"ok": False, "error": "请先登录"})
    data = await request.json()
    result = db.save_profile(user["id"], data)
    return result


@app.get("/api/profile")
async def api_get_profile(request: Request):
    """获取当前用户的云端档案"""
    user = _require_user(request)
    if not user:
        return JSONResponse(status_code=401, content={"ok": False, "error": "请先登录"})
    result = db.load_profile(user["id"])
    return result


@app.get("/api/jobs")
async def api_get_jobs():
    """获取最新推荐的岗位详情列表"""
    return latest_jobs


@app.post("/api/generate-resume")
async def api_generate_resume(request: Request):
    """根据用户档案 + JD 生成定制简历"""
    data = await request.json()
    profile = data.get("profile", {})
    jd = data.get("jd", "")

    if not profile.get("name"):
        return JSONResponse(status_code=400, content={"error": "请先填写个人档案"})
    if not jd:
        return JSONResponse(status_code=400, content={"error": "请提供岗位描述(JD)"})

    # 构造 prompt
    profile_text = _format_profile_for_ai(profile)
    prompt = f"""你是一位专业的求职顾问和简历优化专家。请根据以下个人信息和目标岗位JD，生成一份量身定制的简历内容。

要求：
1. 根据JD中的关键要求，重新组织和优化个人经历的描述
2. 突出与岗位最相关的技能和经验
3. 使用STAR法则描述经历（情景-任务-行动-结果）
4. 适当添加量化成果（如处理了多少数据、提升了多少效率）
5. 语言专业精练，符合求职简历的规范
6. 输出格式为结构化的简历文本

===== 个人信息 =====
{profile_text}

===== 目标岗位JD =====
{jd}

请生成定制简历内容："""

    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.OPENAI_BASE_URL,
        )
        response = await client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=2000,
        )
        resume_text = response.choices[0].message.content
        return {"resume": resume_text}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": f"AI生成失败: {str(e)}"})


def _format_profile_for_ai(profile: dict) -> str:
    """将用户档案格式化为AI可读的文本"""
    lines = []
    if profile.get("name"):
        lines.append(f"姓名: {profile['name']}")
    if profile.get("education"):
        lines.append(f"学历: {profile['education']}")
    if profile.get("school"):
        lines.append(f"院校: {profile['school']}")
    if profile.get("major"):
        lines.append(f"专业: {profile['major']}")
    if profile.get("gradTime"):
        lines.append(f"毕业时间: {profile['gradTime']}")
    if profile.get("gpa"):
        lines.append(f"GPA/排名: {profile['gpa']}")

    if profile.get("skillsData"):
        lines.append(f"专业技能: {', '.join(profile['skillsData'])}")
    if profile.get("skillsOther"):
        lines.append(f"工具/证书: {', '.join(profile['skillsOther'])}")

    if profile.get("skillsLang"):
        lines.append(f"语言能力: {', '.join(profile['skillsLang'])}")

    if profile.get("experiences"):
        lines.append("\n实习/项目经历:")
        for i, exp in enumerate(profile["experiences"], 1):
            lines.append(f"  {i}. {exp.get('company','')} - {exp.get('role','')}")
            if exp.get("time"):
                lines.append(f"     时间: {exp['time']}")
            if exp.get("desc"):
                lines.append(f"     内容: {exp['desc']}")

    if profile.get("industries"):
        lines.append(f"目标行业: {', '.join(profile['industries'])}")
    if profile.get("positions"):
        lines.append(f"目标岗位: {', '.join(profile['positions'])}")
    if profile.get("intro"):
        lines.append(f"自我介绍: {profile['intro']}")

    return "\n".join(lines)


# ==================== BOSS 直聘 API ====================

def _boss_unavailable():
    """Vercel 环境下 BOSS 功能不可用"""
    return JSONResponse(status_code=503, content={"ok": False, "error": "BOSS 直聘功能需要在本地运行"})


@app.get("/api/boss/status")
async def api_boss_status():
    """检查 BOSS 直聘登录状态"""
    if IS_VERCEL:
        return {"logged_in": False, "message": "云端部署暂不支持 BOSS 直聘功能"}
    boss = BossScraper()
    result = await boss.check_status()
    return result


@app.post("/api/boss/login")
async def api_boss_login():
    """触发 BOSS 直聘登录"""
    if IS_VERCEL:
        return _boss_unavailable()
    boss = BossScraper()
    result = await boss.login(timeout=120)
    return result


@app.post("/api/boss/search")
async def api_boss_search(request: Request):
    """BOSS 直聘搜索职位"""
    if IS_VERCEL:
        return _boss_unavailable()
    data = await request.json()
    boss = BossScraper()
    jobs = await boss.search_jobs(
        query=data.get("query", ""),
        city=data.get("city"),
        salary=data.get("salary"),
        experience=data.get("experience"),
        education=data.get("education"),
        industry=data.get("industry"),
        scale=data.get("scale"),
        stage=data.get("stage"),
        job_type=data.get("job_type"),
        page=data.get("page", 1),
    )
    return {"jobs": jobs, "total": len(jobs)}


@app.get("/api/boss/recommend")
async def api_boss_recommend(page: int = 1):
    """BOSS 直聘个性化推荐"""
    if IS_VERCEL:
        return _boss_unavailable()
    boss = BossScraper()
    jobs = await boss.get_recommend(page=page, with_score=True)
    return {"jobs": jobs, "total": len(jobs)}


@app.post("/api/boss/greet")
async def api_boss_greet(request: Request):
    """向招聘者打招呼"""
    if IS_VERCEL:
        return _boss_unavailable()
    data = await request.json()
    security_id = data.get("security_id", "")
    job_id = data.get("job_id", "")
    message = data.get("message", "")

    if not security_id or not job_id:
        return JSONResponse(status_code=400, content={"error": "缺少 security_id 或 job_id"})

    boss = BossScraper()
    result = await boss.greet(security_id, job_id, message)
    return result


@app.post("/api/boss/batch-greet")
async def api_boss_batch_greet(request: Request):
    """批量打招呼"""
    if IS_VERCEL:
        return _boss_unavailable()
    data = await request.json()
    query = data.get("query", "")
    if not query:
        return JSONResponse(status_code=400, content={"error": "请提供搜索关键词"})

    boss = BossScraper()
    result = await boss.batch_greet(
        query=query,
        city=data.get("city"),
        salary=data.get("salary"),
        experience=data.get("experience"),
        education=data.get("education"),
        count=data.get("count", 10),
        dry_run=data.get("dry_run", False),
    )
    return result


@app.get("/api/boss/chat")
async def api_boss_chat(from_who: Optional[str] = None, days: Optional[int] = None, page: int = 1):
    """获取沟通列表"""
    if IS_VERCEL:
        return _boss_unavailable()
    boss = BossScraper()
    chats = await boss.get_chat_list(from_who=from_who, days=days, page=page)
    return {"chats": chats, "total": len(chats)}


@app.get("/api/boss/interviews")
async def api_boss_interviews():
    """获取面试邀请"""
    if IS_VERCEL:
        return _boss_unavailable()
    boss = BossScraper()
    interviews = await boss.get_interviews()
    return {"interviews": interviews, "total": len(interviews)}


@app.get("/api/boss/digest")
async def api_boss_digest():
    """获取日报汇总"""
    if IS_VERCEL:
        return _boss_unavailable()
    boss = BossScraper()
    digest = await boss.get_digest()
    return digest or {"error": "获取日报失败"}


@app.get("/api/boss/stats")
async def api_boss_stats(days: int = 30):
    """获取投递统计"""
    if IS_VERCEL:
        return _boss_unavailable()
    boss = BossScraper()
    stats = await boss.get_stats(days=days)
    return stats or {"error": "获取统计失败"}


@app.get("/api/boss/me")
async def api_boss_me(section: Optional[str] = None):
    """获取 BOSS 个人信息"""
    if IS_VERCEL:
        return _boss_unavailable()
    boss = BossScraper()
    info = await boss.get_my_info(section=section)
    return info or {"error": "获取个人信息失败"}


# ==================== 辅助函数 ====================


def _mask_email(email: str) -> str:
    """邮箱脱敏"""
    if not email or "@" not in email:
        return "未配置"
    parts = email.split("@")
    name = parts[0]
    if len(name) > 3:
        masked = name[:3] + "*" * (len(name) - 3)
    else:
        masked = name[0] + "**"
    return f"{masked}@{parts[1]}"


# ==================== 主入口 ====================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
