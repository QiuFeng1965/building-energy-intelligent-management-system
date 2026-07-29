# -*- coding: utf-8 -*-
"""
pytest 配置文件
设置 Python 路径，确保测试能导入 app 包
"""
import sys
import os

# 将 backend 目录加入 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
