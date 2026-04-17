#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
图像匹配器模块
基于OpenCV实现的图像识别和匹配功能，替代PyAutoGUI的图像识别
"""

import cv2
import numpy as np
import time
import logging
from typing import Tuple, Optional, List, Union
from pathlib import Path

class ImageMatcher:
    """图像匹配器类"""
    
    def __init__(self, default_confidence: float = 0.8, default_timeout: int = 10):
        """
        初始化图像匹配器
        
        Args:
            default_confidence: 默认匹配置信度 (0.0-1.0)
            default_timeout: 默认超时时间（秒）
        """
        self.default_confidence = default_confidence
        self.default_timeout = default_timeout
        
        # 设置日志
        self.logger = logging.getLogger(__name__)
        
        # 图像缓存
        self._template_cache = {}
    
    def _load_template(self, template_path: str) -> Optional[np.ndarray]:
        """
        加载模板图像
        
        Args:
            template_path: 模板图像路径
            
        Returns:
            图像数组或None
        """
        if template_path in self._template_cache:
            return self._template_cache[template_path]
        
        if not Path(template_path).exists():
            self.logger.error(f"模板图像不存在: {template_path}")
            return None
        
        try:
            # 加载图像
            template = cv2.imread(template_path, cv2.IMREAD_COLOR)
            if template is None:
                self.logger.error(f"无法加载图像: {template_path}")
                return None
            
            # 缓存图像
            self._template_cache[template_path] = template
            
            self.logger.debug(f"加载模板图像: {template_path}, 尺寸: {template.shape}")
            return template
            
        except Exception as e:
            self.logger.error(f"加载图像异常: {e}")
            return None
    
    def _load_screenshot(self, screenshot_path: str) -> Optional[np.ndarray]:
        """
        加载截图
        
        Args:
            screenshot_path: 截图路径
            
        Returns:
            图像数组或None
        """
        if not Path(screenshot_path).exists():
            self.logger.error(f"截图不存在: {screenshot_path}")
            return None
        
        try:
            screenshot = cv2.imread(screenshot_path, cv2.IMREAD_COLOR)
            if screenshot is None:
                self.logger.error(f"无法加载截图: {screenshot_path}")
                return None
            
            return screenshot
            
        except Exception as e:
            self.logger.error(f"加载截图异常: {e}")
            return None
    
    def match_template(self, screenshot_path: str, template_path: str, 
                      confidence: Optional[float] = None) -> Optional[Tuple[int, int, int, int, float]]:
        """
        模板匹配
        
        Args:
            screenshot_path: 截图路径
            template_path: 模板图像路径
            confidence: 置信度阈值
            
        Returns:
            (x, y, width, height, confidence) 或 None
        """
        confidence = confidence or self.default_confidence
        
        # 加载图像
        screenshot = self._load_screenshot(screenshot_path)
        template = self._load_template(template_path)
        
        if screenshot is None or template is None:
            return None
        
        try:
            # 获取模板尺寸
            template_h, template_w = template.shape[:2]
            
            # 执行模板匹配
            result = cv2.matchTemplate(screenshot, template, cv2.TM_CCOEFF_NORMED)
            
            # 获取最佳匹配位置
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
            
            if max_val >= confidence:
                x, y = max_loc
                match_confidence = float(max_val)
                
                self.logger.debug(f"找到匹配: {template_path}, 位置: ({x}, {y}), 置信度: {match_confidence:.3f}")
                return (x, y, template_w, template_h, match_confidence)
            else:
                self.logger.debug(f"匹配失败: {template_path}, 最高置信度: {max_val:.3f}, 要求: {confidence}")
                return None
                
        except Exception as e:
            self.logger.error(f"模板匹配异常: {e}")
            return None
    
    def find_all_matches(self, screenshot_path: str, template_path: str, 
                        confidence: Optional[float] = None) -> List[Tuple[int, int, int, int, float]]:
        """
        查找所有匹配
        
        Args:
            screenshot_path: 截图路径
            template_path: 模板图像路径
            confidence: 置信度阈值
            
        Returns:
            匹配结果列表 [(x, y, width, height, confidence), ...]
        """
        confidence = confidence or self.default_confidence
        
        # 加载图像
        screenshot = self._load_screenshot(screenshot_path)
        template = self._load_template(template_path)
        
        if screenshot is None or template is None:
            return []
        
        try:
            # 获取模板尺寸
            template_h, template_w = template.shape[:2]
            
            # 执行模板匹配
            result = cv2.matchTemplate(screenshot, template, cv2.TM_CCOEFF_NORMED)
            
            # 找到所有匹配位置
            locations = np.where(result >= confidence)
            matches = []
            
            for pt in zip(*locations[::-1]):  # 切换 x, y 坐标
                x, y = pt
                match_confidence = float(result[y, x])
                matches.append((x, y, template_w, template_h, match_confidence))
            
            # 去除重叠的匹配（非极大值抑制）
            if matches:
                matches = self._non_max_suppression(matches, 0.3)
            
            self.logger.debug(f"找到 {len(matches)} 个匹配: {template_path}")
            return matches
            
        except Exception as e:
            self.logger.error(f"查找所有匹配异常: {e}")
            return []
    
    def _non_max_suppression(self, matches: List[Tuple[int, int, int, int, float]], 
                           overlap_threshold: float = 0.3) -> List[Tuple[int, int, int, int, float]]:
        """
        非极大值抑制，去除重叠的匹配
        
        Args:
            matches: 匹配结果列表
            overlap_threshold: 重叠阈值
            
        Returns:
            过滤后的匹配结果
        """
        if not matches:
            return []
        
        # 按置信度排序
        matches = sorted(matches, key=lambda x: x[4], reverse=True)
        
        suppressed = []
        
        for i, match1 in enumerate(matches):
            x1, y1, w1, h1, conf1 = match1
            
            is_suppressed = False
            
            for match2 in suppressed:
                x2, y2, w2, h2, conf2 = match2
                
                # 计算重叠面积
                overlap_x = max(0, min(x1 + w1, x2 + w2) - max(x1, x2))
                overlap_y = max(0, min(y1 + h1, y2 + h2) - max(y1, y2))
                overlap_area = overlap_x * overlap_y
                
                # 计算并集面积
                area1 = w1 * h1
                area2 = w2 * h2
                union_area = area1 + area2 - overlap_area
                
                # 计算重叠比例
                if union_area > 0:
                    overlap_ratio = overlap_area / union_area
                    if overlap_ratio > overlap_threshold:
                        is_suppressed = True
                        break
            
            if not is_suppressed:
                suppressed.append(match1)
        
        return suppressed
    
    def get_center(self, match_result: Tuple[int, int, int, int, float]) -> Tuple[int, int]:
        """
        获取匹配结果的中心点坐标
        
        Args:
            match_result: 匹配结果 (x, y, width, height, confidence)
            
        Returns:
            中心点坐标 (center_x, center_y)
        """
        x, y, w, h, conf = match_result
        center_x = x + w // 2
        center_y = y + h // 2
        return (center_x, center_y)
    
    def wait_for_image(self, screenshot_callback, template_path: str, 
                      confidence: Optional[float] = None, timeout: Optional[int] = None, 
                      check_interval: float = 1.0) -> Optional[Tuple[int, int, int, int, float]]:
        """
        等待图像出现
        
        Args:
            screenshot_callback: 截图回调函数，返回截图路径
            template_path: 模板图像路径
            confidence: 置信度阈值
            timeout: 超时时间（秒）
            check_interval: 检查间隔（秒）
            
        Returns:
            匹配结果或None
        """
        confidence = confidence or self.default_confidence
        timeout = timeout or self.default_timeout
        
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            # 获取新截图
            try:
                screenshot_path = screenshot_callback()
                if screenshot_path:
                    # 尝试匹配
                    match_result = self.match_template(screenshot_path, template_path, confidence)
                    if match_result:
                        self.logger.info(f"等待图像成功: {template_path}")
                        return match_result
            except Exception as e:
                self.logger.error(f"等待图像时截图失败: {e}")
            
            time.sleep(check_interval)
        
        self.logger.warning(f"等待图像超时: {template_path}")
        return None
    
    def wait_for_any_image(self, screenshot_callback, template_paths: List[str], 
                          confidence: Optional[float] = None, timeout: Optional[int] = None, 
                          check_interval: float = 1.0) -> Optional[Tuple[str, Tuple[int, int, int, int, float]]]:
        """
        等待任意图像出现
        
        Args:
            screenshot_callback: 截图回调函数
            template_paths: 模板图像路径列表
            confidence: 置信度阈值
            timeout: 超时时间（秒）
            check_interval: 检查间隔（秒）
            
        Returns:
            (匹配的模板路径, 匹配结果) 或 None
        """
        confidence = confidence or self.default_confidence
        timeout = timeout or self.default_timeout
        
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                screenshot_path = screenshot_callback()
                if screenshot_path:
                    # 检查所有模板
                    for template_path in template_paths:
                        match_result = self.match_template(screenshot_path, template_path, confidence)
                        if match_result:
                            self.logger.info(f"检测到图像: {template_path}")
                            return (template_path, match_result)
            except Exception as e:
                self.logger.error(f"等待任意图像时截图失败: {e}")
            
            time.sleep(check_interval)
        
        self.logger.warning(f"等待任意图像超时: {template_paths}")
        return None
    
    def save_debug_image(self, screenshot_path: str, template_path: str, 
                        match_result: Optional[Tuple[int, int, int, int, float]], 
                        output_path: str) -> bool:
        """
        保存调试图像（在截图上标记匹配结果）
        
        Args:
            screenshot_path: 截图路径
            template_path: 模板路径
            match_result: 匹配结果
            output_path: 输出路径
            
        Returns:
            是否保存成功
        """
        try:
            screenshot = self._load_screenshot(screenshot_path)
            if screenshot is None:
                return False
            
            debug_image = screenshot.copy()
            
            if match_result:
                x, y, w, h, conf = match_result
                
                # 绘制矩形框
                cv2.rectangle(debug_image, (x, y), (x + w, y + h), (0, 255, 0), 2)
                
                # 绘制中心点
                center_x, center_y = self.get_center(match_result)
                cv2.circle(debug_image, (center_x, center_y), 5, (0, 0, 255), -1)
                
                # 添加文本
                text = f"Conf: {conf:.3f}"
                cv2.putText(debug_image, text, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
            
            # 保存图像
            cv2.imwrite(output_path, debug_image)
            self.logger.debug(f"调试图像已保存: {output_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"保存调试图像失败: {e}")
            return False
    
    def clear_cache(self):
        """清除图像缓存"""
        self._template_cache.clear()
        self.logger.debug("图像缓存已清除")


# 便捷函数
def find_image_on_screen(screenshot_path: str, template_path: str, 
                        confidence: float = 0.8) -> Optional[Tuple[int, int]]:
    """
    在屏幕截图中查找图像
    
    Args:
        screenshot_path: 截图路径
        template_path: 模板图像路径
        confidence: 置信度
        
    Returns:
        中心点坐标或None
    """
    matcher = ImageMatcher(default_confidence=confidence)
    match_result = matcher.match_template(screenshot_path, template_path)
    
    if match_result:
        return matcher.get_center(match_result)
    return None


def wait_and_click_image(adb_controller, template_path: str, 
                        confidence: float = 0.8, timeout: int = 10) -> bool:
    """
    等待图像出现并点击
    
    Args:
        adb_controller: ADB控制器实例
        template_path: 模板图像路径
        confidence: 置信度
        timeout: 超时时间
        
    Returns:
        是否成功点击
    """
    matcher = ImageMatcher(default_confidence=confidence, default_timeout=timeout)
    
    def screenshot_callback():
        return adb_controller.screenshot()
    
    match_result = matcher.wait_for_image(screenshot_callback, template_path)
    
    if match_result:
        center_x, center_y = matcher.get_center(match_result)
        return adb_controller.tap(center_x, center_y)
    
    return False


if __name__ == "__main__":
    # 测试代码
    print("测试图像匹配器...")
    
    matcher = ImageMatcher()
    
    # 这里需要实际的截图和模板图像进行测试
    print("[成功] 图像匹配器初始化成功")
    print("请确保有截图和模板图像进行实际测试")