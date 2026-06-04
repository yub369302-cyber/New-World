"""
邮件推送模块
将分析结果格式化为美观的 HTML 邮件发送
"""
import ssl
import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

from app.config import settings


class EmailSender:
    """邮件发送器"""

    async def send_recommendations(self, jobs: list[dict]) -> bool:
        """
        发送岗位推荐邮件

        Args:
            jobs: 分析后的岗位列表

        Returns:
            是否发送成功
        """
        if not jobs:
            print("[信息] 无推荐岗位，跳过邮件发送")
            return False

        subject = f"🎯 Job Hunter AI 推荐 | {datetime.now().strftime('%m/%d %H:%M')} | {len(jobs)}个匹配岗位"
        html_content = self._build_html(jobs)

        msg = MIMEMultipart("alternative")
        msg["From"] = settings.SMTP_USER
        msg["To"] = settings.RECIPIENT_EMAIL
        msg["Subject"] = subject
        msg.attach(MIMEText(html_content, "html", "utf-8"))

        try:
            context = ssl.create_default_context()
            smtp = aiosmtplib.SMTP(
                hostname=settings.SMTP_HOST,
                port=settings.SMTP_PORT,
                use_tls=True,
                tls_context=context,
            )
            await smtp.connect()
            await smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            await smtp.send_message(msg)
            await smtp.quit()
            print(f"[成功] 邮件已发送至 {settings.RECIPIENT_EMAIL}")
            return True

        except Exception as e:
            print(f"[错误] 邮件发送失败: {e}")
            return False

    def _build_html(self, jobs: list[dict]) -> str:
        """构建 HTML 邮件内容"""
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        high_match = [j for j in jobs if j.get("match_score", 0) >= 70]
        medium_match = [j for j in jobs if 50 <= j.get("match_score", 0) < 70]

        html = f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f5f5f5; padding: 20px; }}
.container {{ max-width: 700px; margin: 0 auto; background: #fff; border-radius: 12px; box-shadow: 0 2px 12px rgba(0,0,0,0.1); overflow: hidden; }}
.header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: #fff; padding: 30px; text-align: center; }}
.header h1 {{ margin: 0; font-size: 24px; }}
.header p {{ margin: 8px 0 0; opacity: 0.9; }}
.stats {{ display: flex; justify-content: center; gap: 30px; margin-top: 15px; }}
.stat {{ text-align: center; }}
.stat-num {{ font-size: 28px; font-weight: bold; }}
.stat-label {{ font-size: 12px; opacity: 0.8; }}
.section {{ padding: 20px 30px; }}
.section-title {{ font-size: 18px; font-weight: 600; color: #333; border-bottom: 2px solid #667eea; padding-bottom: 8px; margin-bottom: 15px; }}
.job-card {{ background: #f8f9fa; border-radius: 8px; padding: 16px; margin-bottom: 12px; border-left: 4px solid #667eea; }}
.job-card.medium {{ border-left-color: #ffa726; }}
.job-title {{ font-size: 16px; font-weight: 600; color: #333; margin-bottom: 4px; }}
.job-company {{ color: #666; font-size: 14px; margin-bottom: 8px; }}
.job-meta {{ display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 10px; }}
.tag {{ background: #e3f2fd; color: #1976d2; padding: 2px 8px; border-radius: 4px; font-size: 12px; }}
.tag.score {{ background: #e8f5e9; color: #2e7d32; }}
.tag.score.medium {{ background: #fff3e0; color: #e65100; }}
.advice {{ background: #fff; border-radius: 6px; padding: 12px; margin-top: 10px; font-size: 13px; color: #555; }}
.advice-title {{ font-weight: 600; color: #333; margin-bottom: 4px; }}
.greeting {{ background: #e8f5e9; border-radius: 6px; padding: 10px 12px; margin-top: 8px; font-size: 13px; color: #2e7d32; font-style: italic; }}
.footer {{ text-align: center; padding: 20px; color: #999; font-size: 12px; border-top: 1px solid #eee; }}
</style>
</head>
<body>
<div class="container">
    <div class="header">
        <h1>🎯 Job Hunter AI</h1>
        <p>智能求职推荐 · {now}</p>
        <div class="stats">
            <div class="stat">
                <div class="stat-num">{len(jobs)}</div>
                <div class="stat-label">推荐岗位</div>
            </div>
            <div class="stat">
                <div class="stat-num">{len(high_match)}</div>
                <div class="stat-label">高度匹配</div>
            </div>
            <div class="stat">
                <div class="stat-num">{len(medium_match)}</div>
                <div class="stat-label">中度匹配</div>
            </div>
        </div>
    </div>
"""

        # 高匹配度岗位
        if high_match:
            html += '<div class="section"><div class="section-title">⭐ 高度匹配（70分以上）</div>'
            for job in high_match:
                html += self._job_card_html(job, "high")
            html += "</div>"

        # 中等匹配度岗位
        if medium_match:
            html += '<div class="section"><div class="section-title">💡 值得关注（50-69分）</div>'
            for job in medium_match:
                html += self._job_card_html(job, "medium")
            html += "</div>"

        html += f"""
    <div class="footer">
        <p>由 Job Hunter AI 自动生成 | 下次更新时间：每6小时</p>
        <p>如需调整搜索条件，请访问管理页面</p>
    </div>
</div>
</body>
</html>
"""
        return html

    def _job_card_html(self, job: dict, level: str) -> str:
        """生成单个岗位卡片的 HTML"""
        score = job.get("match_score", 0)
        score_class = "score" if level == "high" else "score medium"
        card_class = "" if level == "high" else " medium"

        card = f"""
<div class="job-card{card_class}">
    <div class="job-title">{job.get('title', '')}</div>
    <div class="job-company">{job.get('company', '')} · {job.get('location', '')}</div>
    <div class="job-meta">
        <span class="tag {score_class}">匹配度 {score}分</span>
        <span class="tag">{job.get('source', '')}</span>
        {"<span class='tag'>" + job.get('salary', '') + "</span>" if job.get('salary') else ""}
        {"<span class='tag'>" + job.get('posted_at', '') + "</span>" if job.get('posted_at') else ""}
    </div>
    <div class="advice">
        <div class="advice-title">📝 简历优化建议:</div>
        {job.get('resume_advice', '')}
    </div>
    {"<div class='greeting'>💬 推荐招呼语: " + job.get('greeting', '') + "</div>" if job.get('greeting') else ""}
</div>
"""
        return card
