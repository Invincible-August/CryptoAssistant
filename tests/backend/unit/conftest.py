"""
测试配置文件。
设置Python路径以便导入app模块。
"""
import sys
import os

# 将backend目录添加到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "backend"))
