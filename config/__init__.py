#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
忍者必须死自动化配置包
统一导出所有配置项
生成时间: 2025-10-14
"""

from .device import DEVICE_ID, ADB_PREFIX
from .coordinates import COORDINATES, COORDINATES_LIST

__all__ = [
    "DEVICE_ID",
    "ADB_PREFIX",
    "COORDINATES",
    "COORDINATES_LIST",
]

