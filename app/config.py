"""应用配置"""
import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    """全局配置类"""

    # OpenAI
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_BASE_URL: str = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    # SerpAPI
    SERPAPI_KEY: str = os.getenv("SERPAPI_KEY", "")

    # 邮箱
    SMTP_HOST: str = os.getenv("SMTP_HOST", "smtp.153.com")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "465"))
    SMTP_USER: str = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
    RECIPIENT_EMAIL: str = os.getenv("RECIPIENT_EMAIL", "")

    # 求职配置
    JOB_KEYWORDS: list = os.getenv("JOB_KEYWORDS", "数据分析实习,审计实习").split(",")
    JOB_CITIES: list = os.getenv("JOB_CITIES", "北京,南京").split(",")
    JOB_TYPE: str = os.getenv("JOB_TYPE", "实习")
    JOB_EXCLUDE_KEYWORDS: list = os.getenv(
        "JOB_EXCLUDE_KEYWORDS", "Senior,Lead,高级,资深"
    ).split(",")

    # 简历摘要
    RESUME_SUMMARY: str = os.getenv(
        "RESUME_SUMMARY",
        "审计专业在校大学生，具备数据分析能力，熟练使用SQL、Excel、Tableau等工具，有券商投行部实习经历。",
    )

    # 调度配置
    SCHEDULE_HOURS: list = [
        int(h) for h in os.getenv("SCHEDULE_HOURS", "10,16,22,4").split(",")
    ]

    # 数据存储路径
    DATA_DIR: str = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
    EXCEL_PATH: str = os.path.join(DATA_DIR, "job_recommendations.xlsx")


settings = Settings()

# 确保数据目录存在
os.makedirs(settings.DATA_DIR, exist_ok=True)
