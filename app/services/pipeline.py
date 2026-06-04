"""
主流程管道
串联所有模块：抓取 → 过滤 → AI分析 → 邮件推送 → Excel记录
"""
from datetime import datetime

from app.scrapers.job_scraper import JobScraper
from app.services.job_filter import JobFilter
from app.services.ai_analyzer import AIAnalyzer
from app.services.email_sender import EmailSender
from app.services.excel_recorder import ExcelRecorder


async def run_pipeline() -> dict:
    """
    执行完整的求职推荐流程

    流程:
    1. 抓取岗位（SerpAPI）
    2. 规则过滤
    3. AI 匹配分析
    4. 邮件推送
    5. Excel 记录

    Returns:
        执行结果摘要
    """
    start_time = datetime.now()
    print(f"\n[开始] {start_time.strftime('%Y-%m-%d %H:%M:%S')}")

    # Step 1: 抓取岗位
    print("\n[Step 1] 搜索岗位...")
    scraper = JobScraper()
    raw_jobs = await scraper.search_all()

    if not raw_jobs:
        print("[结束] 未搜索到任何岗位")
        return {"total": 0, "status": "no_jobs_found"}

    # Step 2: 规则过滤
    print("\n[Step 2] 过滤岗位...")
    job_filter = JobFilter()
    filtered_jobs = job_filter.filter_jobs(raw_jobs)

    if not filtered_jobs:
        print("[结束] 过滤后无剩余岗位")
        return {"total": 0, "status": "all_filtered"}

    # Step 3: AI 分析
    print("\n[Step 3] AI 匹配分析...")
    analyzer = AIAnalyzer()
    analyzed_jobs = await analyzer.analyze_jobs(filtered_jobs, top_n=20)

    # 只保留50分以上的推荐
    recommended_jobs = [j for j in analyzed_jobs if j.get("match_score", 0) >= 50]

    if not recommended_jobs:
        print("[结束] 无匹配度足够的岗位")
        return {"total": 0, "status": "no_match"}

    # Step 4: 邮件推送
    print("\n[Step 4] 发送邮件推荐...")
    email_sender = EmailSender()
    email_sent = await email_sender.send_recommendations(recommended_jobs)

    # Step 5: Excel 记录
    print("\n[Step 5] 保存 Excel 记录...")
    recorder = ExcelRecorder()
    excel_path = recorder.save_jobs(recommended_jobs)

    # 总结
    elapsed = (datetime.now() - start_time).total_seconds()
    result = {
        "total": len(recommended_jobs),
        "high_match": len([j for j in recommended_jobs if j.get("match_score", 0) >= 70]),
        "email_sent": email_sent,
        "excel_path": excel_path,
        "elapsed_seconds": round(elapsed, 1),
        "status": "success",
        "jobs": recommended_jobs,  # 返回岗位详情供前端使用
    }

    print(f"\n{'=' * 50}")
    print(f"[完成] 流程完成! 耗时 {result['elapsed_seconds']}s")
    print(f"   推荐岗位: {result['total']} 个（其中高匹配 {result['high_match']} 个）")
    print(f"   邮件发送: {'成功' if email_sent else '失败'}")
    print(f"   Excel: {excel_path}")
    print(f"{'=' * 50}")

    return result
