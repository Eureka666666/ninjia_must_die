#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""战斗处理器模块"""

import time
import logging
from typing import List, Optional
from pathlib import Path


class BattleHandler:
    """战斗处理器类 - 处理战斗阶段的所有操作"""

    def __init__(self, adb_controller, image_matcher, coords: List, *, silent_mode: bool = False):
        """
        初始化战斗处理器
        
        Args:
            adb_controller: ADB控制器实例
            image_matcher: 图像匹配器实例
            coords: 坐标列表
            silent_mode: 是否静默模式（不输出日志）
        """
        self.adb_controller = adb_controller
        self.image_matcher = image_matcher
        self.coords = coords
        self.silent_mode = silent_mode
        
        # 设置日志
        self.logger = logging.getLogger(__name__)
        if self.silent_mode:
            self.logger.setLevel(logging.CRITICAL)
        else:
            self.logger.setLevel(logging.INFO)

    def _tap(self, x: int, y: int) -> None:
        """执行点击操作"""
        self.adb_controller.tap(x, y)

    def handle_battle_phase(self) -> bool:
        """
        处理战斗阶段
        
        Returns:
            是否成功完成战斗
        """
        if len(self.coords) < 8:
            self.logger.error("坐标数据不足，无法处理战斗")
            return False
        
        # 获取战斗相关坐标
        ultimate_x, ultimate_y = self.coords[5]  # 大招坐标
        battle_end_1_x, battle_end_1_y = self.coords[6]  # 战斗结束点击1
        battle_end_2_x, battle_end_2_y = self.coords[7]  # 战斗结束点击2
        
        self.logger.info("等待战斗开始...")
        time.sleep(3)
        
        # 战斗循环
        max_battle_time = 180  # 最大战斗时间3分钟
        start_time = time.time()
        skill_interval = 10  # 大招间隔
        last_skill_time = 0
        check_count = 0  # 检查次数计数
        
        while time.time() - start_time < max_battle_time:
            check_count += 1
            elapsed = int(time.time() - start_time)
            
            # 检查是否战斗结束
            screenshot_path = self.adb_controller.screenshot()
            if screenshot_path:
                # 检查战斗结束界面（恭喜获得文字） - 提高置信度并记录
                congrats_match = self.image_matcher.match_template(
                    screenshot_path, 'assets/congratulations_text.png', confidence=0.7
                )
                if congrats_match:
                    conf = congrats_match[4] if len(congrats_match) > 4 else 0
                    self.logger.info(f"检测到战斗结束界面 (置信度: {conf:.2f})，准备点击确认...")
                    
                    # 点击确认按钮
                    time.sleep(1)
                    self.logger.info(f"点击确认按钮1: ({battle_end_1_x}, {battle_end_1_y})")
                    self._tap(battle_end_1_x, battle_end_1_y)
                    time.sleep(1)
                    self.logger.info(f"点击确认按钮2: ({battle_end_2_x}, {battle_end_2_y})")
                    self._tap(battle_end_2_x, battle_end_2_y)
                    time.sleep(2)
                    self.logger.info("战斗结束处理完成")
                    return True
                else:
                    # 每10次检查输出一次状态
                    if check_count % 10 == 0:
                        self.logger.info(f"战斗进行中... (已过 {elapsed}s / {max_battle_time}s)")
            
            # 定期释放大招
            current_time = time.time()
            if current_time - last_skill_time >= skill_interval:
                self.logger.debug(f"释放大招: ({ultimate_x}, {ultimate_y})")
                self._tap(ultimate_x, ultimate_y)
                last_skill_time = current_time
            
            time.sleep(1)
        
        # 超时处理
        self.logger.warning(f"战斗超时 ({max_battle_time}s)，未检测到结束界面")
        return False
