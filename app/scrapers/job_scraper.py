"""
岗位抓取模块
使用 SerpAPI 对接 Google Jobs 进行聚合搜索
支持智联招聘、BOSS直聘、各公司官网等多平台数据
"""
import httpx
from typing import Optional
from datetime import datetime

from app.config import settings


class JobScraper:
    """岗位抓取器 - 通过 SerpAPI 搜索 Google Jobs"""

    SERPAPI_URL = "https://serpapi.com/search.json"

    def __init__(self):
        self.api_key = settings.SERPAPI_KEY

    async def search_jobs(
        self,
        keyword: str,
        city: str,
        job_type: Optional[str] = None,
    ) -> list[dict]:
        """
        搜索岗位

        Args:
            keyword: 搜索关键词，如 "数据分析实习"
            city: 城市，如 "北京"
            job_type: 岗位类型，如 "实习"

        Returns:
            岗位列表
        """
        query = f"{keyword} {city}"
        if job_type:
            query += f" {job_type}"

        params = {
            "engine": "google_jobs",
            "q": query,
            "hl": "zh-cn",
            "gl": "cn",
            "api_key": self.api_key,
        }

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(self.SERPAPI_URL, params=params)
                response.raise_for_status()
                data = response.json()

            jobs = data.get("jobs_results", [])
            return [self._parse_job(job, city, keyword) for job in jobs]

        except Exception as e:
            print(f"[错误] 搜索 '{query}' 失败: {e}")
            return []

    def _parse_job(self, raw_job: dict, city: str, keyword: str) -> dict:
        """解析单个岗位数据"""
        # 提取薪资信息
        salary = ""
        highlights = raw_job.get("detected_extensions", {})
        if "salary" in highlights:
            salary = highlights["salary"]

        # 提取岗位详情
        description = raw_job.get("description", "")

        return {
            "title": raw_job.get("title", ""),
            "company": raw_job.get("company_name", ""),
            "location": raw_job.get("location", city),
            "description": description[:2000],  # 限制描述长度
            "salary": salary,
            "source": raw_job.get("via", ""),
            "posted_at": raw_job.get("detected_extensions", {}).get("posted_at", ""),
            "schedule_type": raw_job.get("detected_extensions", {}).get(
                "schedule_type", ""
            ),
            "job_id": raw_job.get("job_id", ""),
            "link": raw_job.get("share_link", raw_job.get("related_links", [{}])[0].get("link", "") if raw_job.get("related_links") else ""),
            "search_keyword": keyword,
            "search_city": city,
            "fetched_at": datetime.now().isoformat(),
        }

    async def search_all(self) -> list[dict]:
        """
        根据配置的关键词和城市，批量搜索所有岗位

        Returns:
            去重后的所有岗位列表
        """
        all_jobs = []
        seen_ids = set()

        for keyword in settings.JOB_KEYWORDS:
            for city in settings.JOB_CITIES:
                jobs = await self.search_jobs(
                    keyword=keyword.strip(),
                    city=city.strip(),
                    job_type=settings.JOB_TYPE,
                )

                for job in jobs:
                    # 基于公司+职位名去重
                    job_key = f"{job['company']}_{job['title']}"
                    if job_key not in seen_ids:
                        seen_ids.add(job_key)
                        all_jobs.append(job)

        print(f"[信息] 共搜索到 {len(all_jobs)} 个不重复岗位")
        return all_jobs
