"""
BOSS 直聘抓取模块
通过封装 boss-agent-cli 命令行工具，实现职位搜索、详情查看、打招呼等功能
所有 CLI 输出均为 JSON 信封格式: {"ok": bool, "data": ..., "error": ...}
"""
import asyncio
import json
import sys
from typing import Optional
from datetime import datetime


class BossScraper:
    """BOSS 直聘抓取器 - 封装 boss-agent-cli"""

    def __init__(self):
        self.base_cmd = [sys.executable, "-m", "boss_agent"]

    async def _run_cmd(self, args: list[str], timeout: int = 60) -> dict:
        """
        执行 boss CLI 命令并解析 JSON 输出

        Args:
            args: 命令参数列表
            timeout: 超时时间（秒）

        Returns:
            解析后的 JSON 信封数据
        """
        cmd = self.base_cmd + args + ["--json"]
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=timeout
            )

            output = stdout.decode("utf-8", errors="replace").strip()
            if not output:
                return {"ok": False, "data": None, "error": "命令无输出"}

            # 解析 JSON 信封
            result = json.loads(output)
            return result

        except asyncio.TimeoutError:
            return {"ok": False, "data": None, "error": f"命令超时 ({timeout}s)"}
        except json.JSONDecodeError as e:
            return {"ok": False, "data": None, "error": f"JSON 解析失败: {e}"}
        except Exception as e:
            return {"ok": False, "data": None, "error": f"执行失败: {e}"}

    # ========== 认证相关 ==========

    async def check_status(self) -> dict:
        """检查登录状态"""
        return await self._run_cmd(["status"])

    async def login(self, timeout: int = 120) -> dict:
        """登录 BOSS 直聘"""
        return await self._run_cmd(["login", "--timeout", str(timeout)], timeout=timeout + 10)

    # ========== 搜索相关 ==========

    async def search_jobs(
        self,
        query: str,
        city: Optional[str] = None,
        salary: Optional[str] = None,
        experience: Optional[str] = None,
        education: Optional[str] = None,
        industry: Optional[str] = None,
        scale: Optional[str] = None,
        stage: Optional[str] = None,
        job_type: Optional[str] = None,
        page: int = 1,
        with_score: bool = False,
    ) -> list[dict]:
        """
        搜索职位列表

        Args:
            query: 搜索关键词
            city: 城市名称
            salary: 薪资范围（如 10-20K）
            experience: 经验要求（如 3-5年）
            education: 学历要求（如 本科）
            industry: 行业类型
            scale: 公司规模
            stage: 融资阶段
            job_type: 职位类型（全职/兼职/实习）
            page: 页码
            with_score: 是否附加匹配分

        Returns:
            职位列表
        """
        args = ["search", query]

        if city:
            args.extend(["--city", city])
        if salary:
            args.extend(["--salary", salary])
        if experience:
            args.extend(["--experience", experience])
        if education:
            args.extend(["--education", education])
        if industry:
            args.extend(["--industry", industry])
        if scale:
            args.extend(["--scale", scale])
        if stage:
            args.extend(["--stage", stage])
        if job_type:
            args.extend(["--job-type", job_type])
        if page > 1:
            args.extend(["--page", str(page)])
        if with_score:
            args.append("--with-score")

        result = await self._run_cmd(args, timeout=30)

        if result.get("ok") and result.get("data"):
            jobs = result["data"] if isinstance(result["data"], list) else result["data"].get("jobs", [])
            return [self._normalize_job(job, query, city) for job in jobs]

        error_msg = result.get("error", "未知错误")
        print(f"[BOSS] 搜索 '{query}' 失败: {error_msg}")
        return []

    async def get_detail(
        self, security_id: str, job_id: str = "", lid: str = ""
    ) -> Optional[dict]:
        """
        查看职位详情

        Args:
            security_id: 安全 ID
            job_id: 加密职位 ID（传入则走快速通道）
            lid: 列表项 ID

        Returns:
            职位详情字典
        """
        args = ["detail", security_id]
        if job_id:
            args.extend(["--job-id", job_id])
        if lid:
            args.extend(["--lid", lid])

        result = await self._run_cmd(args, timeout=20)

        if result.get("ok") and result.get("data"):
            return result["data"]
        return None

    async def get_recommend(self, page: int = 1, with_score: bool = False) -> list[dict]:
        """
        获取基于简历的个性化推荐

        Args:
            page: 页码
            with_score: 是否附加匹配分

        Returns:
            推荐职位列表
        """
        args = ["recommend"]
        if page > 1:
            args.extend(["--page", str(page)])
        if with_score:
            args.append("--with-score")

        result = await self._run_cmd(args, timeout=30)

        if result.get("ok") and result.get("data"):
            jobs = result["data"] if isinstance(result["data"], list) else result["data"].get("jobs", [])
            return [self._normalize_job(job, "推荐", None) for job in jobs]
        return []

    # ========== 打招呼 / 投递 ==========

    async def greet(
        self, security_id: str, job_id: str, message: str = ""
    ) -> dict:
        """
        向招聘者打招呼

        Args:
            security_id: 安全 ID
            job_id: 加密职位 ID
            message: 自定义消息

        Returns:
            操作结果
        """
        args = ["greet", security_id, job_id]
        if message:
            args.extend(["--message", message])
        return await self._run_cmd(args, timeout=15)

    async def batch_greet(
        self,
        query: str,
        city: Optional[str] = None,
        salary: Optional[str] = None,
        experience: Optional[str] = None,
        education: Optional[str] = None,
        count: int = 10,
        dry_run: bool = False,
    ) -> dict:
        """
        批量打招呼

        Args:
            query: 搜索关键词
            city: 城市名称
            salary: 薪资范围
            experience: 经验要求
            education: 学历要求
            count: 数量上限（最大10）
            dry_run: 仅模拟

        Returns:
            批量操作结果
        """
        args = ["batch-greet", query]
        if city:
            args.extend(["--city", city])
        if salary:
            args.extend(["--salary", salary])
        if experience:
            args.extend(["--experience", experience])
        if education:
            args.extend(["--education", education])
        args.extend(["--count", str(min(count, 10))])
        if dry_run:
            args.append("--dry-run")

        return await self._run_cmd(args, timeout=60)

    async def apply(self, security_id: str, job_id: str, lid: str = "") -> dict:
        """
        投递/立即沟通

        Args:
            security_id: 安全 ID
            job_id: 加密职位 ID
            lid: 列表项 ID

        Returns:
            操作结果
        """
        args = ["apply", security_id, job_id]
        if lid:
            args.extend(["--lid", lid])
        return await self._run_cmd(args, timeout=15)

    # ========== 沟通管理 ==========

    async def get_chat_list(
        self, from_who: Optional[str] = None, days: Optional[int] = None, page: int = 1
    ) -> list[dict]:
        """
        获取沟通列表

        Args:
            from_who: 筛选 boss/me
            days: 最近 N 天
            page: 页码

        Returns:
            沟通记录列表
        """
        args = ["chat"]
        if from_who:
            args.extend(["--from", from_who])
        if days:
            args.extend(["--days", str(days)])
        if page > 1:
            args.extend(["--page", str(page)])

        result = await self._run_cmd(args, timeout=20)

        if result.get("ok") and result.get("data"):
            return result["data"] if isinstance(result["data"], list) else []
        return []

    async def get_chat_messages(
        self, security_id: str, page: int = 1, count: int = 20
    ) -> list[dict]:
        """获取与指定好友的聊天记录"""
        args = ["chatmsg", security_id, "--page", str(page), "--count", str(count)]
        result = await self._run_cmd(args, timeout=15)
        if result.get("ok") and result.get("data"):
            return result["data"] if isinstance(result["data"], list) else []
        return []

    # ========== 个人信息 ==========

    async def get_my_info(self, section: Optional[str] = None) -> Optional[dict]:
        """
        获取个人信息

        Args:
            section: user/resume/expect/deliver，不指定则获取全部
        """
        args = ["me"]
        if section:
            args.extend(["--section", section])
        result = await self._run_cmd(args, timeout=15)
        if result.get("ok") and result.get("data"):
            return result["data"]
        return None

    # ========== 面试 ==========

    async def get_interviews(self) -> list[dict]:
        """获取面试邀请列表"""
        result = await self._run_cmd(["interviews"], timeout=15)
        if result.get("ok") and result.get("data"):
            return result["data"] if isinstance(result["data"], list) else []
        return []

    # ========== 统计与跟进 ==========

    async def get_follow_up(self, days_stale: int = 3) -> list[dict]:
        """获取需要跟进的项目"""
        result = await self._run_cmd(
            ["follow-up", "--days-stale", str(days_stale)], timeout=15
        )
        if result.get("ok") and result.get("data"):
            return result["data"] if isinstance(result["data"], list) else []
        return []

    async def get_digest(self, days_stale: int = 3) -> Optional[dict]:
        """获取日报汇总"""
        result = await self._run_cmd(
            ["digest", "--days-stale", str(days_stale)], timeout=20
        )
        if result.get("ok") and result.get("data"):
            return result["data"]
        return None

    async def get_stats(self, days: int = 30) -> Optional[dict]:
        """获取投递转化漏斗统计"""
        result = await self._run_cmd(["stats", "--days", str(days)], timeout=15)
        if result.get("ok") and result.get("data"):
            return result["data"]
        return None

    # ========== 搜索全部（对接 pipeline 的入口） ==========

    async def search_all(
        self,
        keywords: list[str],
        cities: list[str],
        salary: Optional[str] = None,
        experience: Optional[str] = None,
        education: Optional[str] = None,
        job_type: Optional[str] = None,
    ) -> list[dict]:
        """
        根据关键词和城市批量搜索，去重后返回

        Args:
            keywords: 搜索关键词列表
            cities: 城市列表
            salary: 薪资范围
            experience: 经验要求
            education: 学历要求
            job_type: 职位类型

        Returns:
            去重后的职位列表
        """
        all_jobs = []
        seen_keys = set()

        for keyword in keywords:
            for city in cities:
                jobs = await self.search_jobs(
                    query=keyword.strip(),
                    city=city.strip(),
                    salary=salary,
                    experience=experience,
                    education=education,
                    job_type=job_type,
                )

                for job in jobs:
                    key = f"{job.get('company', '')}_{job.get('title', '')}"
                    if key not in seen_keys:
                        seen_keys.add(key)
                        all_jobs.append(job)

                # 防止请求过快触发风控
                await asyncio.sleep(1.5)

        print(f"[BOSS] 共搜索到 {len(all_jobs)} 个不重复岗位")
        return all_jobs

    # ========== 内部工具 ==========

    def _normalize_job(self, raw: dict, keyword: str, city: Optional[str]) -> dict:
        """
        将 boss-agent-cli 返回的职位数据标准化为统一格式
        与 SerpAPI 抓取器输出结构保持一致
        """
        return {
            "title": raw.get("job_name") or raw.get("title", ""),
            "company": raw.get("brand_name") or raw.get("company", ""),
            "location": raw.get("area_district") or raw.get("city_name") or city or "",
            "description": raw.get("job_desc") or raw.get("description", ""),
            "salary": raw.get("salary_desc") or raw.get("salary", ""),
            "source": "BOSS直聘",
            "posted_at": raw.get("last_modify_time", ""),
            "schedule_type": raw.get("job_type_name") or raw.get("job_type", ""),
            "job_id": raw.get("encrypt_job_id") or raw.get("job_id", ""),
            "security_id": raw.get("security_id", ""),
            "link": f"https://www.zhipin.com/job_detail/{raw.get('encrypt_job_id', '')}.html"
            if raw.get("encrypt_job_id")
            else "",
            "search_keyword": keyword,
            "search_city": city or "",
            "fetched_at": datetime.now().isoformat(),
            # BOSS 特有字段
            "boss_name": raw.get("boss_name", ""),
            "boss_title": raw.get("boss_title", ""),
            "experience_name": raw.get("experience_name", ""),
            "degree_name": raw.get("degree_name", ""),
            "stage_name": raw.get("stage_name", ""),
            "industry_name": raw.get("industry_name", ""),
            "scale_name": raw.get("brand_scale_name") or raw.get("scale_name", ""),
            "skills": raw.get("skills", []),
            "welfare": raw.get("welfare_list") or raw.get("welfare", []),
            "lid": raw.get("lid", ""),
        }
