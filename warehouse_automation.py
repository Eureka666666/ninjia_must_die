#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
仓库悬赏自动化脚本 - ADB版本
基于ADB控制的后台仓库悬赏自动化脚本
"""

import time
import json
import logging
from typing import Optional, Tuple, List
from pathlib import Path
from utils.controller import AdbController, create_controller
from utils.image_matcher import ImageMatcher
from config import COORDINATES_LIST

class WarehouseAutomationADB:
    """仓库悬赏ADB自动化类"""
    
    def __init__(self, adb_controller: AdbController):
        """
        初始化仓库自动化脚本
        
        Args:
            adb_controller: ADB控制器实例
        """
        self.adb_controller = adb_controller
        self.image_matcher = ImageMatcher(default_confidence=0.7, default_timeout=65)
        self.coords = COORDINATES_LIST
        
        # 设置日志 - 简化输出
        logging.basicConfig(
            level=logging.INFO,
            format='%(message)s'
        )
        self.logger = logging.getLogger(__name__)
    
    def execute_invitation_sequence(self):
        """执行邀请序列（步骤2-5）"""
        if len(self.coords) < 13:
            self.logger.error("[错误] 坐标数据不足")
            return
        
        # 坐标映射
        invite_friend_x, invite_friend_y = self.coords[9]    # 邀请好友图标
        chat_x, chat_y = self.coords[10]                     # 聊天
        send_invite_x, send_invite_y = self.coords[11]       # 发送邀请
        close_invite_x, close_invite_y = self.coords[12]     # 关闭邀请界面
        
        # 步骤2-5：邀请序列
        self.adb_controller.tap(invite_friend_x, invite_friend_y)
        time.sleep(1)
        self.adb_controller.tap(chat_x, chat_y)
        time.sleep(1)
        self.adb_controller.tap(send_invite_x, send_invite_y)
        time.sleep(1)
        self.adb_controller.tap(close_invite_x, close_invite_y)
        time.sleep(1)
    
    def wait_for_start_button(self) -> bool:
        """
        等待65秒检测出发图标
        
        Returns:
            是否检测到出发图标
        """
        wait_attempts = 0
        max_wait_attempts = 65
        
        while wait_attempts < max_wait_attempts:
            screenshot_path = self.adb_controller.screenshot()
            if screenshot_path:
                start_match = self.image_matcher.match_template(
                    screenshot_path, 'assets/start.png', confidence=0.7
                )
                
                if start_match:
                    self.logger.info("✓ 检测到出发图标")
                    return True
            
            time.sleep(1)
            wait_attempts += 1
            if wait_attempts % 10 == 0:
                self.logger.info(f"  等待出发图标... {wait_attempts}s")
        
        return False
    
    def execute_battle_sequence(self) -> bool:
        """
        执行战斗序列（复用现有战斗逻辑）
        
        Returns:
            是否成功完成战斗
        """
        # 等待进入战斗
        battle_started = False
        battle_check_attempts = 0
        max_battle_check = 60
        
        while battle_check_attempts < max_battle_check:
            screenshot_path = self.adb_controller.screenshot()
            if screenshot_path:
                ultimate_match = self.image_matcher.match_template(
                    screenshot_path, 'assets/ultimate_skill.png', confidence=0.7
                )
                
                if ultimate_match:
                    self.logger.info("✓ 检测到大招，进入战斗")
                    battle_started = True
                    
                    if len(self.coords) >= 6:
                        ultimate_x, ultimate_y = self.coords[5]
                        time.sleep(5)
                        self.adb_controller.tap(ultimate_x, ultimate_y)
                    else:
                        center_x, center_y = self.image_matcher.get_center(ultimate_match)
                        time.sleep(5)
                        self.adb_controller.tap(center_x, center_y)
                    break
            
            time.sleep(1)
            battle_check_attempts += 1
            if battle_check_attempts % 10 == 0:
                self.logger.info(f"  等待进入战斗... {battle_check_attempts}s")
        
        if not battle_started:
            self.logger.error("✗ 未检测到进入战斗")
            return False
        
        # 监控战斗结束
        battle_end_attempts = 0
        max_battle_end = 100
        
        while battle_end_attempts < max_battle_end:
            screenshot_path = self.adb_controller.screenshot()
            if screenshot_path:
                congrats_match = self.image_matcher.match_template(
                    screenshot_path, 'assets/congratulations_text.png', confidence=0.8
                )
                
                if congrats_match:
                    self.logger.info("✓ 战斗结束")
                    
                    if len(self.coords) >= 8:
                        end_click1_x, end_click1_y = self.coords[6]
                        end_click2_x, end_click2_y = self.coords[7]
                        self.adb_controller.tap(end_click1_x, end_click1_y)
                        time.sleep(1)
                        self.adb_controller.tap(end_click2_x, end_click2_y)
                    
                    return True
            
            time.sleep(2)
            battle_end_attempts += 1
            if battle_end_attempts % 15 == 0:
                self.logger.info(f"  等待战斗结束... {battle_end_attempts}s")
        
        self.logger.error("✗ 战斗超时")
        return False
    
    def run_single_warehouse_automation(self) -> bool:
        """
        执行一次完整的仓库悬赏自动化流程
        
        Returns:
            是否成功完成
        """
        if not self.coords or len(self.coords) < 13:
            self.logger.error("✗ 坐标数据不足")
            return False
        
        reward_icon_x, reward_icon_y = self.coords[8]
        
        # 步骤1：点击悬赏图标
        self.adb_controller.tap(reward_icon_x, reward_icon_y)
        time.sleep(2)
        
        # 邀请循环
        invitation_attempts = 0
        while True:
            invitation_attempts += 1
            self.logger.info(f"  邀请尝试 #{invitation_attempts}")
            
            self.execute_invitation_sequence()
            
            if self.wait_for_start_button():
                screenshot_path = self.adb_controller.screenshot()
                if screenshot_path:
                    start_match = self.image_matcher.match_template(
                        screenshot_path, 'assets/start.png', confidence=0.7
                    )
                    
                    if start_match:
                        center_x, center_y = self.image_matcher.get_center(start_match)
                        self.adb_controller.tap(center_x, center_y)
                        time.sleep(2)
                        break
                    else:
                        continue
            else:
                continue
        
        # 进入战斗阶段
        battle_result = self.execute_battle_sequence()
        
        if battle_result:
            self.logger.info("✓ 流程完成")
            return True
        else:
            self.logger.error("✗ 战斗失败")
            return False
    
    def run_continuous_automation(self, max_cycles: int):
        """
        循环执行仓库悬赏自动化任务
        
        Args:
            max_cycles: 最大循环次数
        """
        self.logger.info(f"🎯 开始执行 {max_cycles} 次循环 (Ctrl+C 停止)\n")
        
        cycle_count = 0
        success_count = 0
        
        try:
            while cycle_count < max_cycles:
                cycle_count += 1
                self.logger.info(f"━━━ 循环 {cycle_count}/{max_cycles} ━━━")
                
                result = self.run_single_warehouse_automation()
                
                if result:
                    success_count += 1
                    self.logger.info(f"✓ 第 {cycle_count} 次成功 (总成功: {success_count})\n")
                else:
                    self.logger.error(f"✗ 第 {cycle_count} 次失败\n")
                
                if cycle_count < max_cycles:
                    time.sleep(10)
            
            success_rate = (success_count / max_cycles) * 100
            self.logger.info(f"━━━━━━━━━━━━━━━━━━")
            self.logger.info(f"🎉 完成! 成功 {success_count}/{max_cycles} ({success_rate:.1f}%)")
            
        except KeyboardInterrupt:
            self.logger.info("\n⏹ 用户中断")
            if cycle_count > 0:
                success_rate = (success_count / cycle_count) * 100
                self.logger.info(f"📊 已完成 {cycle_count} 次，成功 {success_count} 次 ({success_rate:.1f}%)")


if __name__ == "__main__":
    print("[程序] 仓库悬赏自动化脚本")
    print("=" * 50)
    
    # 创建ADB控制器
    controller = create_controller()
    if not controller:
        print("[错误] 无法连接到ADB设备")
        exit(1)
    
    print(f"[成功] 已连接到设备: {controller.device_id}")
    
    # 创建自动化实例
    automation = WarehouseAutomationADB(controller)
    
    # 检查坐标
    if not automation.coords or len(automation.coords) < 13:
        print("[错误] 坐标数据不足")
        exit(1)
    
    print(f"[成功] 已加载 {len(automation.coords)} 个坐标")
    
    # 获取循环次数
    while True:
        try:
            max_cycles = int(input("请输入要执行的循环次数: "))
            if max_cycles > 0:
                break
            else:
                print("请输入大于0的数字")
        except ValueError:
            print("请输入有效的数字")
        except KeyboardInterrupt:
            print("\n[结束] 用户取消操作")
            exit(0)
    
    # 开始自动化
    automation.run_continuous_automation(max_cycles)
