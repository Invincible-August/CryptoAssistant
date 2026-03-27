"""
AI自我学习占位模块。
预留自我学习接口，当前版本仅保存反馈数据，
后续版本将基于反馈数据进行模型微调或prompt优化。
"""
from typing import Any, Dict, Optional

from loguru import logger


class LearningPlaceholder:
    """
    AI学习占位类，预留未来扩展接口。

    当前版本的所有方法都只做数据记录和日志输出，
    实际的学习逻辑将在后续版本中实现。
    这样设计是为了尽早在系统架构中预留学习接口，
    确保后续实现时不需要大幅修改上游调用代码。
    """

    async def record_feedback(
        self,
        record_id: int,
        feedback_type: str,
        feedback_text: str,
    ) -> Dict[str, Any]:
        """
        记录用户对AI分析结果的反馈。

        当前仅保存数据到日志，后续版本将：
        - 持久化反馈到数据库
        - 基于反馈统计优化Prompt模板
        - 调整模型参数（如temperature）

        Args:
            record_id: 关联的AI分析记录ID
            feedback_type: 反馈类型，如 "accurate"（准确）、"inaccurate"（不准确）、
                          "partially_correct"（部分正确）
            feedback_text: 用户的文字反馈说明

        Returns:
            Dict[str, Any]: 反馈处理结果，包含状态和提示信息
        """
        logger.info(
            f"收到AI反馈: record_id={record_id}, "
            f"type={feedback_type}, text={feedback_text[:100]}"
        )
        return {
            "status": "recorded",
            "message": "反馈已记录，将在后续版本中用于AI优化",
            "record_id": record_id,
            "feedback_type": feedback_type,
        }

    async def learn_from_history(self, limit: int = 100) -> Dict[str, Any]:
        """
        从历史数据中学习（占位接口）。

        当前版本返回占位信息。后续版本计划实现的功能：
        - 从 ai_analysis_records 表中提取历史分析记录
        - 对比分析结果与实际市场走势，计算准确率
        - 基于准确率反馈优化Prompt模板中的分析框架
        - 动态调整各因子在分析中的权重建议

        Args:
            limit: 用于学习的历史记录数量上限

        Returns:
            Dict[str, Any]: 学习结果占位信息，包含计划功能列表
        """
        logger.info(f"AI学习接口被调用（占位），limit={limit}")
        return {
            "status": "placeholder",
            "message": "自我学习功能将在后续版本中实现",
            "planned_features": [
                "基于历史反馈的prompt优化",
                "基于回测结果的策略参数调优",
                "基于市场变化的模型适应性调整",
            ],
        }

    async def evaluate_past_predictions(
        self,
        symbol: Optional[str] = None,
        days: int = 7,
    ) -> Dict[str, Any]:
        """
        评估过去预测的准确性（占位接口）。

        计划实现的逻辑：
        - 获取过去N天的AI分析记录
        - 对比分析时的预测方向与实际价格走势
        - 计算方向预测准确率、入场区间命中率、止损/止盈触及率
        - 生成评估报告

        Args:
            symbol: 交易对名称（可选），为空时评估所有交易对
            days: 回溯天数

        Returns:
            Dict[str, Any]: 评估结果占位信息
        """
        logger.info(
            f"AI预测评估接口被调用（占位），symbol={symbol}, days={days}"
        )
        return {
            "status": "placeholder",
            "message": "预测评估功能将在后续版本中实现",
            "planned_metrics": [
                "方向预测准确率",
                "入场区间命中率",
                "止盈触及率",
                "止损触及率",
                "综合盈亏比",
            ],
        }

    async def get_learning_status(self) -> Dict[str, Any]:
        """
        获取AI学习模块的当前状态（占位接口）。

        Returns:
            Dict[str, Any]: 学习模块状态信息
        """
        return {
            "status": "placeholder",
            "version": "0.1.0",
            "learning_enabled": False,
            "total_feedback_count": 0,
            "last_learning_time": None,
            "message": "学习模块尚未激活，当前版本仅记录反馈数据",
        }


# 全局学习服务单例
learning_service = LearningPlaceholder()
