"""
岗位过滤模块
根据规则对抓取的岗位进行智能过滤，排除不相关的岗位
"""
from app.config import settings


class JobFilter:
    """岗位过滤器 - 基于规则筛选合适的岗位"""

    def __init__(self):
        self.exclude_keywords = [kw.strip().lower() for kw in settings.JOB_EXCLUDE_KEYWORDS]

    def filter_jobs(self, jobs: list[dict]) -> list[dict]:
        """
        过滤岗位列表

        规则:
        1. 排除包含排除关键词的岗位（如 Senior、高级、资深）
        2. 排除描述中要求多年经验的岗位
        3. 保留与实习相关的岗位

        Args:
            jobs: 原始岗位列表

        Returns:
            过滤后的岗位列表
        """
        filtered = []
        for job in jobs:
            if self._should_keep(job):
                filtered.append(job)

        print(f"[信息] 过滤后剩余 {len(filtered)} 个岗位（过滤掉 {len(jobs) - len(filtered)} 个）")
        return filtered

    def _should_keep(self, job: dict) -> bool:
        """判断一个岗位是否应该保留"""
        title = job.get("title", "").lower()
        description = job.get("description", "").lower()
        combined = f"{title} {description}"

        # 规则1: 排除包含排除关键词的岗位
        for keyword in self.exclude_keywords:
            if keyword in combined:
                return False

        # 规则2: 排除明确要求多年经验的岗位
        experience_patterns = [
            "3年以上", "5年以上", "7年以上", "10年以上",
            "3-5年", "5-10年", "3年及以上", "5年及以上",
            "three years", "five years", "3+ years", "5+ years",
        ]
        for pattern in experience_patterns:
            if pattern in combined:
                return False

        # 规则3: 排除明确的全职高级岗位类型
        senior_titles = [
            "总监", "经理", "主管", "总裁", "副总",
            "director", "manager", "principal", "staff",
        ]
        for st in senior_titles:
            if st in title:
                return False

        return True
