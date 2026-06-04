"""
AI 分析模块
使用 OpenAI API 进行岗位匹配打分、简历定制建议和招呼语生成
"""
import json
from openai import AsyncOpenAI

from app.config import settings


class AIAnalyzer:
    """AI 分析器 - 岗位匹配、简历建议、招呼语生成"""

    def __init__(self):
        self.client = AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.OPENAI_BASE_URL,
        )
        self.model = settings.OPENAI_MODEL
        self.resume_summary = settings.RESUME_SUMMARY

    async def analyze_jobs(self, jobs: list[dict], top_n: int = 20) -> list[dict]:
        """
        批量分析岗位：打分 + 简历建议 + 招呼语

        Args:
            jobs: 过滤后的岗位列表
            top_n: 最终推荐的岗位数量

        Returns:
            分析后的 Top N 岗位列表（含评分和建议）
        """
        if not jobs:
            return []

        # 先进行批量打分
        scored_jobs = await self._batch_score(jobs)

        # 按分数排序，取 Top N
        scored_jobs.sort(key=lambda x: x.get("match_score", 0), reverse=True)
        top_jobs = scored_jobs[:top_n]

        # 对 Top N 岗位生成详细建议和招呼语
        analyzed_jobs = []
        for job in top_jobs:
            if job.get("match_score", 0) >= 50:  # 只对50分以上的岗位生成详细分析
                detailed = await self._generate_details(job)
                job.update(detailed)
            else:
                job["resume_advice"] = "匹配度较低，建议优先关注更匹配的岗位"
                job["greeting"] = ""
            analyzed_jobs.append(job)

        print(f"[信息] AI 分析完成，推荐 {len(analyzed_jobs)} 个岗位")
        return analyzed_jobs

    async def _batch_score(self, jobs: list[dict]) -> list[dict]:
        """批量对岗位进行匹配度打分"""
        # 将岗位分批处理（每批5个，避免 token 过长）
        batch_size = 5
        all_scored = []

        for i in range(0, len(jobs), batch_size):
            batch = jobs[i : i + batch_size]
            scored = await self._score_batch(batch)
            all_scored.extend(scored)

        return all_scored

    async def _score_batch(self, jobs: list[dict]) -> list[dict]:
        """对一批岗位进行打分"""
        jobs_text = ""
        for idx, job in enumerate(jobs):
            jobs_text += f"\n--- 岗位 {idx + 1} ---\n"
            jobs_text += f"职位: {job['title']}\n"
            jobs_text += f"公司: {job['company']}\n"
            jobs_text += f"地点: {job['location']}\n"
            jobs_text += f"描述: {job['description'][:500]}\n"

        prompt = f"""你是一个专业的求职匹配顾问。请根据以下简历信息，对每个岗位进行匹配度评分（0-100分）。

## 我的简历摘要
{self.resume_summary}

## 待评估的岗位
{jobs_text}

## 评分标准
- 90-100分: 与专业背景和技能高度匹配，非常值得投递
- 70-89分: 匹配度较高，值得投递
- 50-69分: 部分匹配，可以考虑
- 30-49分: 匹配度一般
- 0-29分: 不太合适

请以 JSON 数组格式返回每个岗位的评分，格式如下:
[{{"index": 1, "score": 85, "reason": "一句话原因"}}, ...]

只返回 JSON，不要其他内容。"""

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
            )
            content = response.choices[0].message.content.strip()

            # 解析 JSON
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]

            scores = json.loads(content)

            # 将分数写入岗位数据
            for score_item in scores:
                idx = score_item.get("index", 0) - 1
                if 0 <= idx < len(jobs):
                    jobs[idx]["match_score"] = score_item.get("score", 0)
                    jobs[idx]["match_reason"] = score_item.get("reason", "")

        except Exception as e:
            print(f"[警告] AI 打分失败: {e}")
            # 失败时给默认分数
            for job in jobs:
                if "match_score" not in job:
                    job["match_score"] = 50
                    job["match_reason"] = "AI评分暂不可用"

        return jobs

    async def _generate_details(self, job: dict) -> dict:
        """为单个岗位生成简历建议和招呼语"""
        prompt = f"""你是一个专业的求职顾问。请根据我的简历和目标岗位，生成两样内容：

## 我的简历摘要
{self.resume_summary}

## 目标岗位
- 职位: {job['title']}
- 公司: {job['company']}
- 描述: {job['description'][:800]}

## 请生成:

### 1. 简历优化建议
针对这个具体岗位，我的简历应该如何调整？包括：
- 哪些经历需要重点突出
- 需要补充什么关键词
- 描述方式如何优化

### 2. 个性化打招呼语
生成一段适合在招聘平台发给HR的招呼语（100字以内），要求：
- 体现对岗位的了解
- 突出自身相关优势
- 自然、有诚意、不套模板

请严格按以下 JSON 格式返回:
{{"resume_advice": "简历建议内容", "greeting": "招呼语内容"}}

只返回 JSON，不要其他内容。"""

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
            )
            content = response.choices[0].message.content.strip()

            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]

            result = json.loads(content)
            return {
                "resume_advice": result.get("resume_advice", ""),
                "greeting": result.get("greeting", ""),
            }

        except Exception as e:
            print(f"[警告] 生成详细建议失败: {e}")
            return {
                "resume_advice": "生成失败，请稍后重试",
                "greeting": f"你好，我是审计专业的在校大学生，对贵公司的{job['title']}岗位很感兴趣，希望有机会进一步交流！",
            }
