#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ADB控制器模块
提供对Android设备的完整控制功能，专为MuMu模拟器优化
"""

import subprocess
import time
import os
import tempfile
import logging
from typing import Tuple, Optional, List, Union
from pathlib import Path

class AdbController:
    """ADB设备控制器"""
    
    def __init__(self, device_id: Optional[str] = None, adb_path: str = "adb", timeout: int = 30):
        """
        初始化ADB控制器
        
        Args:
            device_id: 设备ID，如 "127.0.0.1:16384"
            adb_path: ADB可执行文件路径
            timeout: 命令执行超时时间
        """
        self.device_id = device_id
        self.adb_path = adb_path
        self.timeout = timeout
        self.connected = False
        
        # 设置日志
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
        
        # 自动检测和连接设备
        if not self.device_id:
            self.device_id = self._auto_detect_device()
        
        if self.device_id:
            self.connected = self._test_connection()
            if self.connected:
                self.logger.info(f"[成功] 成功连接到设备: {self.device_id}")
            else:
                self.logger.warning(f"设备连接测试失败: {self.device_id}")
    
    def _run_command(self, command: str, timeout: Optional[int] = None) -> Tuple[bool, str, str]:
        """
        执行系统命令
        
        Args:
            command: 要执行的命令
            timeout: 超时时间
            
        Returns:
            (成功标志, 标准输出, 错误输出)
        """
        timeout = timeout or self.timeout
        
        try:
            self.logger.debug(f"执行命令: {command}")
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                encoding='utf-8'
            )
            
            success = result.returncode == 0
            stdout = result.stdout.strip()
            stderr = result.stderr.strip()
            
            if not success:
                self.logger.debug(f"命令执行失败: {stderr}")
            
            return success, stdout, stderr
            
        except subprocess.TimeoutExpired:
            self.logger.error(f"命令执行超时: {command}")
            return False, "", "命令执行超时"
        except Exception as e:
            self.logger.error(f"命令执行异常: {e}")
            return False, "", str(e)
    
    def _adb_command(self, command: str, timeout: Optional[int] = None) -> Tuple[bool, str, str]:
        """
        执行ADB命令
        
        Args:
            command: ADB命令（不包含adb前缀）
            timeout: 超时时间
            
        Returns:
            (成功标志, 标准输出, 错误输出)
        """
        if self.device_id:
            full_command = f"{self.adb_path} -s {self.device_id} {command}"
        else:
            full_command = f"{self.adb_path} {command}"
        
        return self._run_command(full_command, timeout)
    
    def _auto_detect_device(self) -> Optional[str]:
        """
        自动检测MuMu模拟器设备
        
        Returns:
            设备ID或None
        """
        self.logger.info("自动检测MuMu模拟器...")
        
        # 常见MuMu端口
        common_ports = ["16384", "7555", "5555"]
        
        for port in common_ports:
            device_id = f"127.0.0.1:{port}"
            self.logger.info(f"尝试连接 {device_id}...")
            
            # 尝试连接
            success, stdout, stderr = self._run_command(f"{self.adb_path} connect {device_id}")
            
            if success and ("connected" in stdout.lower() or "already connected" in stdout.lower()):
                # 验证设备是否在线
                success, stdout, stderr = self._run_command(f"{self.adb_path} devices")
                if success and device_id in stdout:
                    self.logger.info(f"[成功] 检测到设备: {device_id}")
                    return device_id
        
        self.logger.warning("[错误] 未检测到MuMu模拟器设备")
        return None
    
    def _test_connection(self) -> bool:
        """
        测试设备连接
        
        Returns:
            连接是否成功
        """
        if not self.device_id:
            return False
        
        success, stdout, stderr = self._adb_command("shell echo 'test'")
        return success and "test" in stdout
    
    def connect(self, device_id: Optional[str] = None) -> bool:
        """
        连接设备
        
        Args:
            device_id: 设备ID
            
        Returns:
            连接是否成功
        """
        if device_id:
            self.device_id = device_id
        
        if not self.device_id:
            self.logger.error("未指定设备ID")
            return False
        
        # 连接设备
        success, stdout, stderr = self._run_command(f"{self.adb_path} connect {self.device_id}")
        
        if success:
            self.connected = self._test_connection()
            if self.connected:
                self.logger.info(f"[成功] 成功连接设备: {self.device_id}")
            else:
                self.logger.error(f"[错误] 设备连接后测试失败: {self.device_id}")
        else:
            self.logger.error(f"[错误] 连接失败: {stderr}")
            self.connected = False
        
        return self.connected
    
    def disconnect(self) -> bool:
        """
        断开设备连接
        
        Returns:
            断开是否成功
        """
        if not self.device_id:
            return True
        
        success, stdout, stderr = self._run_command(f"{self.adb_path} disconnect {self.device_id}")
        
        if success:
            self.connected = False
            self.logger.info(f"[成功] 已断开设备: {self.device_id}")
        else:
            self.logger.error(f"[错误] 断开失败: {stderr}")
        
        return success
    
    def get_device_info(self) -> dict:
        """
        获取设备信息
        
        Returns:
            设备信息字典
        """
        if not self.connected:
            return {}
        
        info = {}
        
        # 获取设备型号
        success, stdout, stderr = self._adb_command("shell getprop ro.product.model")
        if success:
            info['model'] = stdout
        
        # 获取Android版本
        success, stdout, stderr = self._adb_command("shell getprop ro.build.version.release")
        if success:
            info['android_version'] = stdout
        
        # 获取屏幕分辨率
        success, stdout, stderr = self._adb_command("shell wm size")
        if success:
            # 解析 "Physical size: 1280x720" 格式
            if ":" in stdout:
                resolution = stdout.split(":")[1].strip()
                if "x" in resolution:
                    width, height = resolution.split("x")
                    info['screen_width'] = int(width)
                    info['screen_height'] = int(height)
                    info['resolution'] = resolution
        
        # 获取设备品牌
        success, stdout, stderr = self._adb_command("shell getprop ro.product.brand")
        if success:
            info['brand'] = stdout
        
        return info
    
    def screenshot(self, save_path: Optional[str] = None) -> Optional[str]:
        """
        截屏
        
        Args:
            save_path: 保存路径，如果为None则保存到临时文件
            
        Returns:
            截图文件路径或None
        """
        if not self.connected:
            self.logger.error("设备未连接")
            return None
        
        if save_path is None:
            save_path = os.path.join(tempfile.gettempdir(), f"screenshot_{int(time.time())}.png")
        
        # 在设备上截图
        success, stdout, stderr = self._adb_command("shell screencap -p /sdcard/temp_screenshot.png")
        if not success:
            self.logger.error(f"设备截图失败: {stderr}")
            return None
        
        # 拉取截图到本地
        success, stdout, stderr = self._adb_command(f"pull /sdcard/temp_screenshot.png \"{save_path}\"")
        if not success:
            self.logger.error(f"截图文件拉取失败: {stderr}")
            return None
        
        # 清理设备上的临时文件
        self._adb_command("shell rm /sdcard/temp_screenshot.png")
        
        if os.path.exists(save_path):
            self.logger.debug(f"截图保存到: {save_path}")
            return save_path
        else:
            self.logger.error(f"截图文件未找到: {save_path}")
            return None
    
    def tap(self, x: int, y: int, duration: int = 100) -> bool:
        """
        点击屏幕
        
        Args:
            x: X坐标
            y: Y坐标
            duration: 点击持续时间（毫秒）
            
        Returns:
            点击是否成功
        """
        if not self.connected:
            self.logger.error("设备未连接")
            return False
        
        if duration > 100:
            # 长按
            command = f"shell input swipe {x} {y} {x} {y} {duration}"
        else:
            # 普通点击
            command = f"shell input tap {x} {y}"
        
        success, stdout, stderr = self._adb_command(command)
        
        if success:
            self.logger.debug(f"点击坐标: ({x}, {y})")
        else:
            self.logger.error(f"点击失败: {stderr}")
        
        return success
    
    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration: int = 500) -> bool:
        """
        滑动
        
        Args:
            x1: 起始X坐标
            y1: 起始Y坐标
            x2: 结束X坐标
            y2: 结束Y坐标
            duration: 滑动持续时间（毫秒）
            
        Returns:
            滑动是否成功
        """
        if not self.connected:
            self.logger.error("设备未连接")
            return False
        
        success, stdout, stderr = self._adb_command(f"shell input swipe {x1} {y1} {x2} {y2} {duration}")
        
        if success:
            self.logger.debug(f"滑动: ({x1}, {y1}) -> ({x2}, {y2})")
        else:
            self.logger.error(f"滑动失败: {stderr}")
        
        return success
    
    def send_text(self, text: str) -> bool:
        """
        发送文本
        
        Args:
            text: 要发送的文本
            
        Returns:
            发送是否成功
        """
        if not self.connected:
            self.logger.error("设备未连接")
            return False
        
        # 转义特殊字符
        escaped_text = text.replace(" ", "%s").replace("&", "\\&")
        
        success, stdout, stderr = self._adb_command(f"shell input text \"{escaped_text}\"")
        
        if success:
            self.logger.debug(f"发送文本: {text}")
        else:
            self.logger.error(f"发送文本失败: {stderr}")
        
        return success
    
    def press_key(self, key_code: Union[int, str]) -> bool:
        """
        按键
        
        Args:
            key_code: 按键码（数字或字符串）
            常用按键：KEYCODE_BACK(4), KEYCODE_HOME(3), KEYCODE_MENU(82)
            
        Returns:
            按键是否成功
        """
        if not self.connected:
            self.logger.error("设备未连接")
            return False
        
        success, stdout, stderr = self._adb_command(f"shell input keyevent {key_code}")
        
        if success:
            self.logger.debug(f"按键: {key_code}")
        else:
            self.logger.error(f"按键失败: {stderr}")
        
        return success
    
    def install_app(self, apk_path: str) -> bool:
        """
        安装应用
        
        Args:
            apk_path: APK文件路径
            
        Returns:
            安装是否成功
        """
        if not self.connected:
            self.logger.error("设备未连接")
            return False
        
        if not os.path.exists(apk_path):
            self.logger.error(f"APK文件不存在: {apk_path}")
            return False
        
        success, stdout, stderr = self._adb_command(f"install \"{apk_path}\"", timeout=120)
        
        if success and "Success" in stdout:
            self.logger.info(f"[成功] 应用安装成功: {apk_path}")
        else:
            self.logger.error(f"[错误] 应用安装失败: {stderr}")
        
        return success and "Success" in stdout
    
    def start_app(self, package_name: str, activity_name: Optional[str] = None) -> bool:
        """
        启动应用
        
        Args:
            package_name: 包名
            activity_name: Activity名称（可选）
            
        Returns:
            启动是否成功
        """
        if not self.connected:
            self.logger.error("设备未连接")
            return False
        
        if activity_name:
            command = f"shell am start -n {package_name}/{activity_name}"
        else:
            command = f"shell monkey -p {package_name} -c android.intent.category.LAUNCHER 1"
        
        success, stdout, stderr = self._adb_command(command)
        
        if success:
            self.logger.info(f"[成功] 应用启动: {package_name}")
        else:
            self.logger.error(f"[错误] 应用启动失败: {stderr}")
        
        return success
    
    def stop_app(self, package_name: str) -> bool:
        """
        停止应用
        
        Args:
            package_name: 包名
            
        Returns:
            停止是否成功
        """
        if not self.connected:
            self.logger.error("设备未连接")
            return False
        
        success, stdout, stderr = self._adb_command(f"shell am force-stop {package_name}")
        
        if success:
            self.logger.info(f"[成功] 应用停止: {package_name}")
        else:
            self.logger.error(f"[错误] 应用停止失败: {stderr}")
        
        return success
    
    def is_app_running(self, package_name: str) -> bool:
        """
        检查应用是否在运行
        
        Args:
            package_name: 包名
            
        Returns:
            应用是否在运行
        """
        if not self.connected:
            return False
        
        success, stdout, stderr = self._adb_command(f"shell pidof {package_name}")
        return success and stdout.strip() != ""
    
    def get_current_activity(self) -> Optional[str]:
        """
        获取当前Activity
        
        Returns:
            当前Activity名称或None
        """
        if not self.connected:
            return None
        
        success, stdout, stderr = self._adb_command("shell dumpsys window windows | grep -E 'mCurrentFocus'")
        
        if success and stdout:
            # 解析输出获取Activity名称
            try:
                parts = stdout.split()
                for part in parts:
                    if "/" in part and "}" in part:
                        return part.split("}")[0]
            except:
                pass
        
        return None
    
    def wait_for_device(self, timeout: int = 30) -> bool:
        """
        等待设备连接
        
        Args:
            timeout: 超时时间
            
        Returns:
            设备是否连接成功
        """
        success, stdout, stderr = self._run_command(f"{self.adb_path} wait-for-device", timeout)
        
        if success:
            self.connected = True
            self.logger.info("[成功] 设备已连接")
        else:
            self.logger.error(f"[错误] 等待设备超时: {stderr}")
        
        return success


# 便捷函数
def create_controller(device_id: Optional[str] = None) -> Optional[AdbController]:
    """
    创建ADB控制器实例
    
    Args:
        device_id: 设备ID，如果为None则自动检测
        
    Returns:
        ADB控制器实例或None
    """
    controller = AdbController(device_id)
    return controller if controller.connected else None


if __name__ == "__main__":
    # 测试代码
    print("[测试] 测试ADB控制器...")
    
    controller = create_controller()
    if controller:
        print("[成功] 控制器创建成功")
        
        # 获取设备信息
        info = controller.get_device_info()
        print(f"设备信息: {info}")
        
        # 截图测试
        screenshot_path = controller.screenshot("./test_adb_screenshot.png")
        if screenshot_path:
            print(f"[成功] 截图成功: {screenshot_path}")
        
        # 点击测试（安全坐标）
        if controller.tap(400, 600):
            print("[成功] 点击测试成功")
    else:
        print("[错误] 控制器创建失败")