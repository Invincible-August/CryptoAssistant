"""
任务调度模块。
使用APScheduler管理定时任务。
"""
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from loguru import logger


class TaskScheduler:
    """异步任务调度器"""

    def __init__(self):
        self._scheduler = AsyncIOScheduler()
        self._is_running = False

    def start(self):
        """启动调度器"""
        if not self._is_running:
            self._scheduler.start()
            self._is_running = True
            logger.info("任务调度器已启动")

    def stop(self):
        """停止调度器"""
        if self._is_running:
            self._scheduler.shutdown()
            self._is_running = False
            logger.info("任务调度器已停止")

    def add_interval_job(self, func, seconds: int, job_id: str = None, **kwargs):
        """添加间隔定时任务"""
        self._scheduler.add_job(
            func,
            "interval",
            seconds=seconds,
            id=job_id,
            replace_existing=True,
            **kwargs,
        )
        logger.info(f"定时任务已添加: {job_id or func.__name__}, 间隔{seconds}秒")

    def add_cron_job(self, func, cron_expr: dict, job_id: str = None, **kwargs):
        """添加Cron定时任务"""
        self._scheduler.add_job(
            func,
            "cron",
            id=job_id,
            replace_existing=True,
            **cron_expr,
            **kwargs,
        )
        logger.info(f"Cron任务已添加: {job_id or func.__name__}")

    def remove_job(self, job_id: str):
        """移除定时任务"""
        try:
            self._scheduler.remove_job(job_id)
            logger.info(f"定时任务已移除: {job_id}")
        except Exception as e:
            logger.warning(f"移除任务失败 {job_id}: {e}")

    def list_jobs(self):
        """列出所有任务"""
        return [
            {
                "id": job.id,
                "name": job.name,
                "next_run": str(job.next_run_time),
            }
            for job in self._scheduler.get_jobs()
        ]


task_scheduler = TaskScheduler()
