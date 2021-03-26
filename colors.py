from enum import Enum

class Colors(Enum):
    """
        values are in RGB
    """
    RED = (255, 0, 0)
    GREEN = (0, 255, 0)
    BLUE = (0, 0, 255)
    BLACK = (0, 0, 0)
    WHITE = (255, 255, 255)

colors_to_bgr_map = {
    Colors.RED: (0, 0, 255),
    Colors.GREEN: (0, 255, 0),
    Colors.BLUE: (255, 0, 0),
    Colors.BLACK: (0, 0, 0),
    Colors.WHITE: (255, 255, 255)
}