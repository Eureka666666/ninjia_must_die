#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""辅助函数模块"""

from typing import List
from config import COORDINATES, COORDINATES_LIST


def get_coordinate(key: str) -> List[int]:
    """根据键名获取坐标
    
    Args:
        key: 坐标键名
        
    Returns:
        [x, y] 坐标列表
    """
    return COORDINATES.get(key, [0, 0])


def get_coordinate_by_index(index: int) -> List[int]:
    """根据索引获取坐标（兼容旧版本）
    
    Args:
        index: 坐标索引
        
    Returns:
        [x, y] 坐标列表
    """
    if 0 <= index < len(COORDINATES_LIST):
        return COORDINATES_LIST[index]
    return [0, 0]
