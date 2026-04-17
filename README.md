# 忍者必须死 自动化脚本

基于 ADB 的游戏自动化脚本集合，当前包含两类流程：

- 智能悬赏令自动化（等级检测版本）
- 仓库悬赏自动化

## 功能概览

- 图像匹配检测关键按钮与战斗状态（assets 模板图）
- ADB 后台点击与截图控制
- 可循环执行并输出日志
- 启动批处理可一键选择运行模式

## 目录说明

- `auto_click_advanced.py`：智能悬赏令自动化主脚本
- `warehouse_automation.py`：仓库悬赏自动化主脚本
- `utils/`：ADB 控制、图像匹配、战斗处理等通用模块
- `config/`：设备与坐标配置
- `assets/`：模板图资源
- `启动脚本.bat`：Windows 下快速启动入口

## 运行环境

- Windows
- Python 3.10+
- ADB 已安装并可在命令行使用
- 手机已开启开发者模式与 USB 调试，并可被 `adb devices` 识别

## 快速开始

1. 安装依赖（在项目根目录）

```bash
pip install opencv-python pillow numpy adbutils
```

2. 连接设备并确认 ADB 可用

```bash
adb devices
```

3. 运行脚本（二选一）

```bash
python auto_click_advanced.py
```

```bash
python warehouse_automation.py
```

或直接双击运行 `启动脚本.bat`。

## 注意事项

- 先根据你的设备分辨率与界面位置调整坐标配置。
- 自动化脚本仅用于学习与个人测试，请遵守游戏与平台规则。