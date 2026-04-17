#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MuMu 悬赏令等级检测核心逻辑。

该模块仅保留 ``EnhancedNinjaAutomation`` 使用的 OCR 检测能力。
"""

from __future__ import annotations

import logging
import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

import cv2

# 延迟导入 easyocr，避免模块级加载 torch 导致的性能问题
HAS_EASYOCR = False
_easyocr_module = None

def _lazy_import_easyocr():
    """延迟导入 easyocr 模块"""
    global HAS_EASYOCR, _easyocr_module
    if _easyocr_module is not None:
        return _easyocr_module
    
    try:
        import easyocr  # type: ignore
        _easyocr_module = easyocr
        HAS_EASYOCR = True
        return easyocr
    except (ImportError, Exception):
        HAS_EASYOCR = False
        return None

DEFAULT_LEVELS: Tuple[str, ...] = (
    "SS+",
    "SS",
    "S+",
    "S",
    "A+",
    "A",
    "B",
    "C",
    "D",
)
DEFAULT_OCR_REGION: Tuple[int, int, int, int] = (410, 560, 200, 200)
DEFAULT_OCR_CONFIDENCE: float = 0.45


@dataclass
class BountyDetection:
    """单个悬赏令识别结果。"""

    level: str
    center: Tuple[int, int]
    button: Tuple[int, int]
    confidence: float
    bbox: Tuple[int, int, int, int]
    metadata: Dict[str, Any] = field(default_factory=dict)


class BountyLevelDetector:
    """使用 easyocr 从截图中提取悬赏令等级。"""

    BUTTON_OFFSET: Tuple[int, int] = (250, 220)
    MERGE_DISTANCE: int = 40
    LEVEL_ALIASES = {
        "0": "D",
        "〇": "D",
        "Ｏ": "D",
        "5": "S",
        "５": "S",
        "8": "B",
        "８": "B",
    }

    def __init__(
        self,
        *,
        levels: Sequence[str] = DEFAULT_LEVELS,
        ocr_region: Tuple[int, int, int, int] = DEFAULT_OCR_REGION,
        ocr_confidence: float = DEFAULT_OCR_CONFIDENCE,
        dump_raw_ocr: bool = False,
    ) -> None:
        self.logger = logging.getLogger(self.__class__.__name__)
        self.levels = tuple(levels)
        self.ocr_region = ocr_region
        self.ocr_confidence = ocr_confidence
        self.dump_raw_ocr = dump_raw_ocr
        self._ocr_reader: Any = None  # 延迟初始化

    def detect_from_image(self, screenshot_path: Path) -> List[BountyDetection]:
        """对指定截图执行 OCR 检测。"""
        screenshot_path = Path(screenshot_path)
        if not screenshot_path.exists():
            raise FileNotFoundError(f"截图文件不存在: {screenshot_path}")

        detections = self._detect_with_ocr(screenshot_path)
        detections = self._merge_overlaps(detections)

        if not detections:
            self.logger.debug("OCR 未在指定区域识别到目标文本")

        return detections

    def create_debug_image(
        self,
        screenshot_path: Path,
        detections: Sequence[BountyDetection],
        output_path: Path,
    ) -> bool:
        """在截图上标注识别结果并保存。"""
        image = cv2.imread(str(screenshot_path))
        if image is None:
            self.logger.error("无法加载截图: %s", screenshot_path)
            return False

        colors = {
            "SS+": (128, 0, 128),
            "SS": (0, 0, 255),
            "S+": (255, 0, 255),
            "S": (255, 0, 0),
            "A+": (0, 255, 255),
            "A": (0, 255, 0),
            "B": (0, 165, 255),
            "C": (150, 150, 150),
            "D": (90, 90, 90),
        }

        for detection in detections:
            x, y, w, h = detection.bbox
            color = colors.get(detection.level, (255, 255, 255))

            cv2.rectangle(image, (x, y), (x + w, y + h), color, 2)
            cv2.circle(image, detection.center, 5, color, -1)
            cv2.circle(image, detection.button, 8, color, 2)
            cv2.line(image, detection.center, detection.button, color, 1)

            label = f"{detection.level} ({detection.confidence:.2f})"
            cv2.putText(
                image,
                label,
                (x, max(20, y - 10)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                color,
                2,
            )

        output_path.parent.mkdir(parents=True, exist_ok=True)
        success = cv2.imwrite(str(output_path), image)
        if success:
            self.logger.info("调试图保存到: %s", output_path)
        else:
            self.logger.error("调试图保存失败: %s", output_path)
        return success

    def _init_ocr_reader(self) -> bool:
        easyocr = _lazy_import_easyocr()
        if easyocr is None:
            self.logger.error("未检测到 easyocr，请先安装: pip install easyocr")
            return False

        if self._ocr_reader is not None:
            return True

        try:
            self._ocr_reader = easyocr.Reader(["ch_sim", "en"], gpu=True)
            self.logger.info("OCR 引擎已初始化 (尝试GPU加速)")
            return True
        except Exception as exc:  # pragma: no cover - 初始化失败仅记录
            self.logger.error("OCR 引擎初始化失败: %s", exc)
            self._ocr_reader = None
            return False

    def _detect_with_ocr(self, screenshot_path: Path) -> List[BountyDetection]:
        if not self._init_ocr_reader():
            return []

        image = cv2.imread(str(screenshot_path))
        if image is None:
            self.logger.error("无法加载截图进行 OCR: %s", screenshot_path)
            return []

        x, y, width, height = self._resolve_ocr_region(image)
        roi = image[y : y + height, x : x + width]
        if roi.size == 0:
            self.logger.error("OCR 识别区域无效: %s", (x, y, width, height))
            return []

        reader = self._ocr_reader
        if reader is None:
            return []

        results = reader.readtext(roi)

        if self.dump_raw_ocr:
            for raw_bbox, raw_text, raw_conf in results:
                normalized = raw_text.replace(" ", "").upper()
                normalized = self._apply_level_alias(normalized)
                self.logger.debug(
                    "OCR raw -> text=%s normalized=%s conf=%.3f bbox=%s",
                    raw_text,
                    normalized,
                    float(raw_conf),
                    raw_bbox,
                )

        pattern = re.compile(r"(SS|[SABCD])(\+?)级?悬赏令?")
        detections: List[BountyDetection] = []

        for bbox, text, confidence in results:
            normalized_text = text.replace(" ", "").upper()
            normalized_text = self._apply_level_alias(normalized_text)
            match = pattern.search(normalized_text)
            if not match:
                continue

            base_level = match.group(1)
            plus_flag = match.group(2)
            level = base_level + plus_flag
            if level not in self.levels:
                continue

            confidence = float(confidence)
            if confidence < self.ocr_confidence:
                continue

            xs = [float(point[0]) for point in bbox]
            ys = [float(point[1]) for point in bbox]
            center_x = int(sum(xs) / len(xs)) + x
            center_y = int(sum(ys) / len(ys)) + y

            left = int(min(xs)) + x
            top = int(min(ys)) + y
            right = int(max(xs)) + x
            bottom = int(max(ys)) + y

            button_x = center_x + self.BUTTON_OFFSET[0]
            button_y = center_y + self.BUTTON_OFFSET[1]

            detections.append(
                BountyDetection(
                    level=level,
                    center=(center_x, center_y),
                    button=(button_x, button_y),
                    confidence=float(confidence),
                    bbox=(left, top, max(1, right - left), max(1, bottom - top)),
                    metadata={
                        "ocr_text": text,
                        "ocr_text_normalized": normalized_text,
                        "ocr_confidence": float(confidence),
                        "has_plus": bool(plus_flag),
                        "base_level": base_level,
                    },
                )
            )

        return detections

    def _merge_overlaps(self, detections: List[BountyDetection]) -> List[BountyDetection]:
        merged: List[BountyDetection] = []
        for detection in detections:
            merged_detection = None

            for existing in merged:
                if detection.level != existing.level:
                    continue

                if self._distance(detection.center, existing.center) <= self.MERGE_DISTANCE:
                    merged_detection = existing
                    break

            if merged_detection is None:
                merged.append(detection)
            elif detection.confidence > merged_detection.confidence:
                merged_detection.center = detection.center
                merged_detection.button = detection.button
                merged_detection.confidence = detection.confidence
                merged_detection.bbox = detection.bbox
                merged_detection.metadata = detection.metadata

        merged.sort(key=lambda item: (-item.center[1], -item.confidence))
        return merged

    def _resolve_ocr_region(self, image: Any) -> Tuple[int, int, int, int]:
        img_h, img_w = image.shape[:2]
        x, y, width, height = self.ocr_region
        x = max(0, min(img_w, x))
        y = max(0, min(img_h, y))
        width = max(1, min(img_w - x, width))
        height = max(1, min(img_h - y, height))
        return (x, y, width, height)

    def _apply_level_alias(self, value: str) -> str:
        if not value:
            return value

        value = value.translate({ord("０"): "0", ord("５"): "5", ord("８"): "8"})
        first = value[0]
        mapped = self.LEVEL_ALIASES.get(first)
        if mapped:
            value = mapped + value[1:]
        return value

    @staticmethod
    def _distance(pt1: Tuple[int, int], pt2: Tuple[int, int]) -> float:
        return math.hypot(pt1[0] - pt2[0], pt1[1] - pt2[1])