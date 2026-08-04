import re
import math
from dataclasses import dataclass, field
from typing import List, Optional, Union

@dataclass
class ProjectData:
    """Модель данных для генерации MegaTool."""
    project_name: str = ""
    pcb_side: str = ""                # "BOT" или "TOP"
    board_dimensions: str = ""        # "X;Y;Z"
    multiplication: str = ""          # "X;Y"
    has_rotation: bool = False        # есть ли развороты блоков
    rotated_blocks: List[int] = field(default_factory=list)  # номера блоков с разворотом
    pitch_x: float = 0.0
    pitch_y: float = 0.0
    fiducial_bot1: str = "0;0"
    fiducial_bot2: str = "0;0"
    fiducial_top1: str = "0;0"
    fiducial_top2: str = "0;0"
    need_rotation: bool = False       # поворот всей платы на мультизаготовке
    rotation_angle: int = 0
    need_sn_label: bool = False
    sn_label_coords: str = ""         # "X;Y;Angle"
    move_refdes: str = ""             # для коррекции Move Auto
    move_newx: float = 0.0
    move_newy: float = 0.0
    move_delta_x: float = 0.0
    move_delta_y: float = 0.0

    @staticmethod
    def validate_dimensions(value: str) -> bool:
        return bool(re.match(r'^[\d.]+;[\d.]+;[\d.]+$', value))

    @staticmethod
    def validate_multiplication(value: str) -> bool:
        return bool(re.match(r'^\d+;\d+$', value))

    @staticmethod
    def validate_coords(value: str) -> bool:
        return bool(re.match(r'^-?\d+(\.\d+)?;-?\d+(\.\d+)?$', value))

    @staticmethod
    def validate_coords_with_angle(value: str) -> bool:
        return bool(re.match(r'^-?\d+(\.\d+)?;-?\d+(\.\d+)?;-?\d+(\.\d+)?$', value))

    def get_board_width(self) -> float:
        try:
            return float(self.board_dimensions.split(';')[0])
        except:
            return 0.0

    def get_board_height(self) -> float:
        try:
            return float(self.board_dimensions.split(';')[1])
        except:
            return 0.0

    def get_mult_x(self) -> int:
        try:
            return int(self.multiplication.split(';')[0])
        except:
            return 1

    def get_mult_y(self) -> int:
        try:
            return int(self.multiplication.split(';')[1])
        except:
            return 1

    def total_blocks(self) -> int:
        return self.get_mult_x() * self.get_mult_y()
