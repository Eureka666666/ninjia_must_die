#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
忍者必须死智能悬赏令自动化脚本 - 等级检测版本
基于ADB控制的后台自动化脚本，支持悬赏令等级检测和限制功能
"""

import time
import json
import logging
from typing import Optional, Tuple, Dict, List, Set
from pathlib import Path
from dataclasses import dataclass
from utils.controller import AdbController, create_controller
from utils.image_matcher import ImageMatcher
from utils.bounty_monitor import BountyLevelDetector, BountyDetection
from utils.battle_handler import BattleHandler
from config import COORDINATES_LIST

@dataclass
class BountyLevelConfig:
    """悬赏令等级配置"""
    level: str
    enabled: bool
    max_count: int
    current_count: int = 0
    unlimited: bool = False  # S/S+ 级无限制
    limit_detection_count: int = 0  # 检测到"已打满"的次数


class EnhancedNinjaAutomation:
    """增强版忍者必须死自动化类 - 支持等级检测"""

    def __init__(self, adb_controller: AdbController, *, save_debug_images: bool = True):
        """
        初始化自动化脚本
        
        Args:
            adb_controller: ADB控制器实例
        """
        self.adb_controller = adb_controller
        self.image_matcher = ImageMatcher(default_confidence=0.7, default_timeout=30)
        self.bounty_detector = BountyLevelDetector(
            levels=("SS+", "SS", "S+", "S", "A+", "A", "B", "C", "D"),
            ocr_region=(410, 590, 200, 220),
            ocr_confidence=0.45
        )
        self.coords = []
        self.bounty_configs: Dict[str, BountyLevelConfig] = {}
        self.blacklisted_levels: Set[str] = set()  # 已满的悬赏令等级红名单（不再使用）
        self.current_bounty_level: Optional[str] = None  # 当前尝试的悬赏令等级
        self.save_debug_images = save_debug_images
        
        # 设置日志 - 启用INFO级别
        logging.basicConfig(
            level=logging.INFO,  # 启用INFO级别日志
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',  # 详细格式
            datefmt='%H:%M:%S'
        )
        self.logger = logging.getLogger(__name__)
        
        # 用于显示进度的单独logger
        self.progress_logger = logging.getLogger('progress')
        self.progress_logger.setLevel(logging.INFO)
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter('%(message)s'))
        self.progress_logger.addHandler(handler)
        self.progress_logger.propagate = False
        
        # 调试图像输出目录
        self.debug_images_dir: Optional[Path] = None
        if self.save_debug_images:
            self.debug_images_dir = Path("debug_images")
            self.debug_images_dir.mkdir(exist_ok=True)
        
        # 直接从config.py加载坐标
        self.coords = COORDINATES_LIST
        
        # 初始化等级配置
        self.setup_bounty_configs()
        
        # 初始化战斗处理器（启用日志）
        self.battle_handler = BattleHandler(
            adb_controller=self.adb_controller,
            image_matcher=self.image_matcher,
            coords=self.coords,
            silent_mode=False  # 关闭静默模式以显示日志
        )

    def _tap(self, x: int, y: int, label: Optional[str] = None, log: bool = True) -> None:
        """包装ADB点击，可选择是否输出日志"""
        if log and label:
            self.logger.info(f"点击: {label} ({x}, {y})")
        self.adb_controller.tap(x, y)
    
    def _maybe_refresh(self, x: int, y: int, attempts_since_refresh: int) -> bool:
        """根据尝试次数控制刷新操作"""
        if attempts_since_refresh >= 5:
            self.logger.info("刷新悬赏令列表")
            self._tap(x, y, label="刷新按钮", log=True)
            time.sleep(1.0)
            return True
        return False
    
    def setup_bounty_configs(self):
        """设置悬赏令等级配置"""
        # 默认等级配置 - 所有启用等级都无限制，永远不打SS+
        default_limits = {
            "SS+": {"enabled": False, "max_count": 0, "unlimited": False},  # 永远不打SS+
            "SS": {"enabled": True, "max_count": 0, "unlimited": True},
            "S+": {"enabled": True, "max_count": 0, "unlimited": True},
            "S": {"enabled": True, "max_count": 0, "unlimited": True},
            "A+": {"enabled": True, "max_count": 0, "unlimited": True},
            "A": {"enabled": True, "max_count": 0, "unlimited": True},
            "B": {"enabled": True, "max_count": 0, "unlimited": True},
            "C": {"enabled": True, "max_count": 0, "unlimited": True},
            "D": {"enabled": True, "max_count": 0, "unlimited": True},
        }
        
        for level, config in default_limits.items():
            self.bounty_configs[level] = BountyLevelConfig(
                level=level,
                enabled=config["enabled"],
                max_count=config["max_count"],
                unlimited=config["unlimited"]
            )
    
    def select_levels_interactive(self):
        """GUI 勾选要打的悬赏令等级"""
        import tkinter as tk

        selectable = ["SS", "S+", "S", "A+", "A", "B", "C", "D"]

        root = tk.Tk()
        root.title("悬赏令等级选择")
        root.resizable(False, False)

        # ── 标题 ──────────────────────────────────────────
        tk.Label(root, text="请勾选要打的悬赏令等级",
                 font=("微软雅黑", 13, "bold"), pady=8).pack()

        # ── 说明 ──────────────────────────────────────────
        hint = ("勾选的等级：打满后仍会加入队伍\n"
                "但检测到「已打满」提示时，会自动退出队伍，不进行战斗\n"
                "SS+ 永远不打")
        tk.Label(root, text=hint, font=("微软雅黑", 9),
                 fg="#555555", justify="left", padx=16, pady=4).pack(anchor="w")

        tk.Frame(root, height=1, bg="#cccccc").pack(fill="x", padx=12, pady=4)

        # ── 复选框 ────────────────────────────────────────
        vars_: Dict[str, tk.BooleanVar] = {}
        frame = tk.Frame(root, padx=24, pady=4)
        frame.pack(anchor="w")

        # 等级颜色映射（仅装饰用）
        level_colors = {
            "SS": "#cc0000", "S+": "#cc44cc", "S": "#0055cc",
            "A+": "#cc8800", "A": "#228822",
            "B": "#cc5500", "C": "#666666", "D": "#444444",
        }

        for level in selectable:
            var = tk.BooleanVar(value=self.bounty_configs[level].enabled)
            vars_[level] = var
            color = level_colors.get(level, "#000000")
            tk.Checkbutton(
                frame, text=f"  {level}  级",
                variable=var,
                font=("微软雅黑", 11, "bold"),
                fg=color,
                activeforeground=color,
                selectcolor="#f0f0f0",
                anchor="w",
            ).pack(anchor="w", pady=2)

        # SS+ 禁用项（仅展示）
        tk.Frame(root, height=1, bg="#cccccc").pack(fill="x", padx=12, pady=4)
        tk.Label(root, text="  SS+  级（永远不打，不可选）",
                 font=("微软雅黑", 11, "bold"), fg="#aaaaaa",
                 padx=24).pack(anchor="w")

        tk.Frame(root, height=1, bg="#cccccc").pack(fill="x", padx=12, pady=8)

        # ── 确认按钮 ──────────────────────────────────────
        def on_confirm():
            root.destroy()

        tk.Button(
            root, text="确认并开始",
            font=("微软雅黑", 11, "bold"),
            bg="#2d7dd2", fg="white",
            activebackground="#1a5fa8", activeforeground="white",
            relief="flat", padx=20, pady=6,
            command=on_confirm,
        ).pack(pady=(0, 16))

        root.update_idletasks()
        w, h = root.winfo_reqwidth(), root.winfo_reqheight()
        sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
        root.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")

        root.mainloop()

        # 应用选择结果
        for level in selectable:
            self.bounty_configs[level].enabled = vars_[level].get()
        self.bounty_configs["SS+"].enabled = False

        enabled = [lv for lv in selectable if vars_[lv].get()]
        disabled = [lv for lv in selectable if not vars_[lv].get()]
        print("\n已确认等级配置：")
        if enabled:
            print(f"  启用: {', '.join(enabled)}")
        if disabled:
            print(f"  禁用: {', '.join(disabled)}")

    def _blacklist_level(self, level: str, reason: str = "") -> None:
        """所有等级都不加入黑名单，仅记录日志"""
        if level:
            self.logger.info(f"检测到 {level} 级已打满，但继续打")
    
    def execute_exit_operation(self) -> bool:
        """
        执行退出操作
        
        Returns:
            是否执行成功
        """
        if len(self.coords) >= 5:
            exit_button1_x, exit_button1_y = self.coords[3]
            exit_button2_x, exit_button2_y = self.coords[4]
            
            # 执行退出操作
            self._tap(exit_button1_x, exit_button1_y, label="退出按钮1", log=True)
            time.sleep(1)
            self._tap(exit_button2_x, exit_button2_y, label="退出按钮2", log=True)
            return True
        else:
            return False
    
    def detect_and_join_bounty(self) -> bool:
        """
        检测悬赏令等级并智能加入队伍
        
        Returns:
            是否成功加入队伍
        """
        self.current_bounty_level = None
        attempt = 0
        refresh_button_x, refresh_button_y = 120, 951
        attempts_since_refresh = 0

        while True:
            screenshot_path = self.adb_controller.screenshot()
            if not screenshot_path:
                attempt += 1
                attempts_since_refresh += 1
                if self._maybe_refresh(refresh_button_x, refresh_button_y, attempts_since_refresh):
                    attempts_since_refresh = 0
                time.sleep(0.2)
                continue

            try:
                ready_match = self.image_matcher.match_template(
                    screenshot_path, 'assets/ready_button.png', confidence=0.7
                )
                if ready_match:
                    return True

                detections = self.bounty_detector.detect_from_image(Path(screenshot_path))

                available_levels: List[str] = []
                skipped_blacklisted: List[str] = []
                target_detection: Optional[BountyDetection] = None

                if detections:
                    for detection in detections:
                        config = self.bounty_configs.get(detection.level)
                        if not config or not config.enabled:
                            continue

                        available_levels.append(detection.level)
                        if target_detection is None:
                            target_detection = detection

                    self.save_debug_image(screenshot_path, detections, "bounty_detection")

                    if target_detection:
                        level = target_detection.level
                        button_x, button_y = target_detection.button
                        self.current_bounty_level = level
                        self.logger.info(f"尝试加入 {level} 级悬赏令")
                        self._tap(button_x, button_y, label=f"{level}级悬赏令", log=True)
                        time.sleep(0.8)

                        follow_up_path = self.adb_controller.screenshot()
                        if follow_up_path:
                            ready_match = self.image_matcher.match_template(
                                follow_up_path, 'assets/ready_button.png', confidence=0.7
                            )
                            if ready_match:
                                config = self.bounty_configs.get(level)
                                if config:
                                    config.current_count += 1
                                return True

                            limit_match = self.image_matcher.match_template(
                                follow_up_path, 'assets/reaching_limit.png', confidence=0.6
                            )
                            if limit_match:
                                self.logger.info(f"{level} 级已打满，退出队伍")
                                self.execute_exit_operation()
                                self.current_bounty_level = None
                                # 不 return，继续外层循环寻找下一个悬赏令

                        self.current_bounty_level = None

                else:
                    if attempt % 5 == 0:
                        self.save_debug_image(screenshot_path, [], "no_bounty_detected")

                attempt += 1
                attempts_since_refresh += 1

                if self._maybe_refresh(refresh_button_x, refresh_button_y, attempts_since_refresh):
                    attempts_since_refresh = 0

                time.sleep(0.1)

            except Exception as e:
                attempt += 1
                attempts_since_refresh += 1
                if self._maybe_refresh(refresh_button_x, refresh_button_y, attempts_since_refresh):
                    attempts_since_refresh = 0
                time.sleep(0.5)

        # 逻辑上不会到达此处，循环会持续尝试直到成功或外部中断
    
    def save_debug_image(self, screenshot_path: str, detections: List[BountyDetection], prefix: str = "bounty_detection") -> None:
        """
        保存带检测标记的调试图像
        
        Args:
            screenshot_path: 截图路径
            detections: 检测结果列表
            prefix: 文件名前缀
        """
        if not self.save_debug_images or not self.debug_images_dir:
            return

        try:
            import cv2
            import numpy as np
            
            # 读取原始图像
            image = cv2.imread(screenshot_path)
            if image is None:
                return
            
            # 复制图像用于标记
            debug_image = image.copy()
            
            # 定义颜色映射
            colors = {
                "SS": (0, 0, 255),     # 红色
                "S+": (255, 0, 255),   # 紫色
                "S": (255, 0, 0),      # 蓝色
                "A+": (0, 255, 255),   # 黄色
                "A": (0, 255, 0),      # 绿色
                "B": (0, 165, 255),    # 橙色
                "C": (128, 128, 128),  # 灰色
                "D": (64, 64, 64),     # 深灰色
            }
            
            # 标记OCR识别区域
            ocr_x, ocr_y, ocr_w, ocr_h = self.bounty_detector.ocr_region
            cv2.rectangle(debug_image, (ocr_x, ocr_y), (ocr_x + ocr_w, ocr_y + ocr_h), (255, 255, 255), 2)
            cv2.putText(debug_image, "OCR Region", (ocr_x, max(20, ocr_y - 10)), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            
            # 标记每个检测到的悬赏令
            for i, detection in enumerate(detections):
                level = detection.level
                color = colors.get(level, (255, 255, 255))  # 默认白色
                
                # 标记文本检测框
                x, y, w, h = detection.bbox
                cv2.rectangle(debug_image, (x, y), (x + w, y + h), color, 2)
                
                # 标记文本中心点
                center_x, center_y = detection.center
                cv2.circle(debug_image, (center_x, center_y), 5, color, -1)
                
                # 标记按钮位置
                button_x, button_y = detection.button
                cv2.circle(debug_image, (button_x, button_y), 8, color, 2)
                
                # 绘制从文本到按钮的连线
                cv2.line(debug_image, (center_x, center_y), (button_x, button_y), color, 2)
                
                # 添加等级标签
                label = f"{level} ({detection.confidence:.2f})"
                label_y = max(20, y - 10)
                cv2.putText(debug_image, label, (x, label_y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
                
                # 添加序号
                cv2.putText(debug_image, str(i+1), (center_x-10, center_y-15), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
            
            # 添加统计信息
            stats_text = f"Detected: {len(detections)} bounties"
            cv2.putText(debug_image, stats_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            
            # 保存调试图像
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filename = f"{prefix}_{timestamp}_{len(detections)}bounties.png"
            output_path = self.debug_images_dir / filename
            
            # 静默保存调试图像，不输出日志
            cv2.imwrite(str(output_path), debug_image)
                
        except ImportError:
            pass  # 静默处理缺少opencv的情况
        except Exception:
            pass  # 静默处理调试图像保存错误
    
    def wait_and_handle_ready(self) -> str:
        """
        等待并处理准备阶段
        
        Returns:
            处理结果状态字符串
        """
        if len(self.coords) < 3:
            return "error"
        
        ready_button_x, ready_button_y = self.coords[2]
        
        # 检查是否达到上限，若打满则退出队伍
        screenshot_path = self.adb_controller.screenshot()
        if screenshot_path:
            limit_match = self.image_matcher.match_template(
                screenshot_path, 'assets/reaching_limit.png', confidence=0.6
            )
            if limit_match:
                level = self.current_bounty_level or "未知"
                self.logger.info(f"{level} 级已打满，退出队伍")
                self.execute_exit_operation()
                self.current_bounty_level = None
                return "limit_reached"
        
        # 点击准备按钮
        self.logger.info("点击准备按钮")
        self._tap(ready_button_x, ready_button_y, label="准备按钮", log=True)
        time.sleep(0.5)
        
        # 移动到安全位置
        self._tap(ready_button_x - 200, ready_button_y, log=False)
        wait_attempts = 0
        max_wait_attempts = 60
        
        while wait_attempts < max_wait_attempts:
            screenshot_path = self.adb_controller.screenshot()
            if screenshot_path:
                # 检查是否出现剧情
                story_match = self.image_matcher.match_template(
                    screenshot_path, 'assets/story.png', confidence=0.7
                )
                if story_match:
                    self.logger.info("检测到剧情界面")
                    self.current_bounty_level = None
                    return "story_detected"
                
                # 检查是否已进入战斗（检测大招图标）
                if len(self.coords) >= 6:
                    # 尝试检测大招区域，判断是否进入战斗
                    # 这里简单检测屏幕变化，或者可以添加大招图标检测
                    ultimate_detected = self.image_matcher.match_template(
                        screenshot_path, 'assets/ultimate_skill.png', confidence=0.6
                    )
                    if ultimate_detected:
                        self.logger.info("检测到大招图标，已进入战斗阶段")
                        return "matched"
            
            time.sleep(1)
            wait_attempts += 1
        
        # 超时后检查队伍匹配结果
        self.logger.info(f"等待超时({max_wait_attempts}秒)，检查匹配状态...")
        screenshot_path = self.adb_controller.screenshot()
        if screenshot_path:
            cancel_match = self.image_matcher.match_template(
                screenshot_path, 'assets/cancel_ready.png', confidence=0.7
            )
            
            if cancel_match:
                self.execute_exit_operation()
                self.current_bounty_level = None
                return "no_match"
            else:
                return "matched"
        
        self.current_bounty_level = None
        return "unknown"
    
    def handle_battle_phase(self) -> bool:
        """
        处理战斗阶段（调用战斗处理器，静默模式）
        
        Returns:
            是否成功完成战斗
        """
        return self.battle_handler.handle_battle_phase()
    
    def display_statistics(self, show_all: bool = False):
        """显示统计信息
        
        Args:
            show_all: 是否显示所有等级（包括0次的）
        """
        if show_all:
            print("\n" + "="*50)
            print("悬赏令统计")
            print("="*50)
        
        total_completed = 0
        status_parts = []
        
        # SS单独显示
        ss_config = self.bounty_configs.get("SS")
        if ss_config and ss_config.enabled:
            ss_count = ss_config.current_count
            total_completed += ss_count
            status_parts.append(f"SS: {ss_count}次")
        
        # S+和S合并显示
        sp_config = self.bounty_configs.get("S+")
        s_config = self.bounty_configs.get("S")
        if (sp_config and sp_config.enabled) or (s_config and s_config.enabled):
            sp_count = sp_config.current_count if sp_config else 0
            s_count = s_config.current_count if s_config else 0
            combined_count = sp_count + s_count
            total_completed += combined_count
            status_parts.append(f"S+/S: {combined_count}次")
        
        # A+和A合并显示
        ap_config = self.bounty_configs.get("A+")
        a_config = self.bounty_configs.get("A")
        if (ap_config and ap_config.enabled) or (a_config and a_config.enabled):
            ap_count = ap_config.current_count if ap_config else 0
            a_count = a_config.current_count if a_config else 0
            combined_count = ap_count + a_count
            total_completed += combined_count
            status_parts.append(f"A+/A: {combined_count}次")
        
        # B, C, D单独显示
        for level in ["B", "C", "D"]:
            config = self.bounty_configs.get(level)
            if not config or not config.enabled:
                continue
                
            count = config.current_count
            total_completed += count
            status_parts.append(f"{level}: {count}次")
        
        # 显示一行简洁的统计
        print(", ".join(status_parts))
        
        if show_all:
            print(f"\n总完成: {total_completed} 次")
            print("="*50)
    
    def run_single_automation(self) -> str:
        """
        执行一次完整的自动化流程
        
        Returns:
            执行结果状态
        """
        if not self.coords or len(self.coords) < 8:
            return "error"
        
        # 获取基础坐标
        chat_button_x, chat_button_y = self.coords[0]
        province_button_x, province_button_y = self.coords[1]
        
        # 进入悬赏令界面
        self._tap(chat_button_x, chat_button_y, label="聊天按钮", log=True)
        time.sleep(1)
        self._tap(province_button_x, province_button_y, label="地区按钮", log=True)
        time.sleep(1)
        
        # 智能检测并加入队伍
        if not self.detect_and_join_bounty():
            return "refresh_failed"
        
        # 处理准备阶段
        ready_result = self.wait_and_handle_ready()
        
        if ready_result in ["limit_reached", "no_match", "story_detected"]:
            return ready_result
        elif ready_result != "matched":
            return "ready_failed"
        
        # 战斗阶段
        if self.handle_battle_phase():
            self.current_bounty_level = None
            return "success"
        else:
            self.current_bounty_level = None
            return "battle_failed"
    
    def run_continuous_automation(self):
        """循环执行自动化任务"""
        print("\n" + "="*50)
        print("忍者必须死智能悬赏令自动化")
        print("="*50)
        print("运行中... (按 Ctrl+C 停止)\n")
        
        cycle_count = 0
        
        try:
            while True:
                cycle_count += 1
                
                # 执行一次自动化流程
                result = self.run_single_automation()
                
                # 每次循环后显示统计（简洁版）
                self.display_statistics(show_all=False)
                
                # 每50次循环显示详细统计
                if cycle_count % 50 == 0:
                    self.display_statistics(show_all=True)
                
                if result not in ["success", "limit_reached", "no_match", "story_detected", "refresh_failed"]:
                    if result == "join_failed":
                        break
                
                # 等待后开始下一次循环
                if result != "join_failed":
                    time.sleep(5)
                
        except KeyboardInterrupt:
            print("\n")
            print("="*50)
            print("程序已停止")
            print("="*50)
            
            # 显示最终统计
            self.display_statistics(show_all=True)
            print("\n感谢使用！")


if __name__ == "__main__":
    # 启用INFO级别日志
    logging.getLogger('utils.controller').setLevel(logging.INFO)
    logging.getLogger('BountyLevelDetector').setLevel(logging.INFO)
    logging.getLogger('utils.battle_handler').setLevel(logging.INFO)
    logging.getLogger('utils.image_matcher').setLevel(logging.INFO)
    
    # 创建ADB控制器
    controller = create_controller()
    if not controller:
        print("[错误] 无法连接到ADB设备")
        exit(1)
    
    # 创建自动化实例
    automation = EnhancedNinjaAutomation(controller, save_debug_images=False)
    
    # 检查坐标
    if not automation.coords or len(automation.coords) < 8:
        print("[错误] 坐标数据不足")
        exit(1)
    
    # 初始化OCR检测器
    if not automation.bounty_detector._init_ocr_reader():
        print("[错误] OCR引擎初始化失败")
        exit(1)
    
    # 让用户勾选要打的悬赏令等级
    automation.select_levels_interactive()

    # 直接开始自动化
    automation.run_continuous_automation()