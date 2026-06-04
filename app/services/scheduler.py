"""
定时调度模块
每6小时自动执行一次岗位搜索和推荐流程
"""
import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.config import settings
from app.services.pipeline import run_pipeline


scheduler = AsyncIOScheduler()


def setup_scheduler():
    """配置定时任务"""
    hours = settings.SCHEDULE_HOURS  # [10, 16, 22, 4]
    hours_str = ",".join(str(h) for h in hours)

    # 每天在指定时间执行
    scheduler.add_job(
        _run_job,
        CronTrigger(hour=hours_str, minute=0),
        id="job_hunter_main",
        name="Job Hunter 自动搜索推荐",
        replace_existing=True,
    )

    scheduler.start()
    print(f"[调度] 定时任务已启动, 执行时间: 每天 {hours_str} 点整")


async def _run_job():
    """定时任务执行入口"""
    print("\n" + "=" * 50)
    print("[Job Hunter] 自动任务开始执行...")
    print("=" * 50)

    try:
        result = await run_pipeline()
        print(f"\n[完成] 任务完成: 推荐 {result.get('total', 0)} 个岗位")
    except Exception as e:
        print(f"\n[失败] 任务执行失败: {e}")


async def run_now():
    """立即执行一次（手动触发）"""
    await _run_job()
