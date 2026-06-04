"""
Job Hunter - 智能求职推荐系统
主入口文件：FastAPI 应用 + API 路由
"""
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

from app.config import settings
from app.services.scheduler import setup_scheduler, run_now, scheduler
from app.services.pipeline import run_pipeline

# 运行状态跟踪
run_history: list = []
is_running: bool = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时初始化调度器
    setup_scheduler()
    print("\n🎯 Job Hunter 已启动！")
    print(f"   调度时间: 每天 {settings.SCHEDULE_HOURS} 点")
    print(f"   搜索关键词: {settings.JOB_KEYWORDS}")
    print(f"   目标城市: {settings.JOB_CITIES}")
    print(f"   邮箱推送: {settings.RECIPIENT_EMAIL}")
    print(f"\n🌐 访问管理面板: http://localhost:8000")
    yield
    # 关闭时停止调度器
    scheduler.shutdown(wait=False)
    print("\n👋 Job Hunter 已停止")


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
    return templates.TemplateResponse("index.html", {"request": request})


# ==================== API 路由 ====================


@app.post("/api/run")
async def api_run(background_tasks: BackgroundTasks):
    """手动触发一次完整流程"""
    global is_running

    if is_running:
        return JSONResponse(
            status_code=429,
            content={"status": "busy", "message": "已有任务正在执行中，请稍后再试"},
        )

    background_tasks.add_task(_execute_pipeline)
    return {"status": "started", "message": "任务已启动，请稍后查看结果"}


async def _execute_pipeline():
    """后台执行流程并记录结果"""
    global is_running
    is_running = True

    try:
        result = await run_pipeline()
        result["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        run_history.insert(0, result)
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
    jobs = scheduler.get_jobs()
    if jobs:
        next_run_time = jobs[0].next_run_time
        if next_run_time:
            next_run = next_run_time.strftime("%Y-%m-%d %H:%M:%S")

    return {
        "is_running": is_running,
        "scheduler_running": scheduler.running,
        "next_run": next_run,
        "total_runs": len(run_history),
        "last_run": run_history[0] if run_history else None,
    }


@app.get("/api/health")
async def api_health():
    """健康检查"""
    return {"status": "ok", "timestamp": datetime.now().isoformat()}


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
