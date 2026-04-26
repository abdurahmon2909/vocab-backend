from math import floor, sqrt


class XPService:
    @staticmethod
    def level_from_xp(xp: int) -> int:
        return floor(sqrt(xp / 10))

    @staticmethod
    def next_level_xp(level: int) -> int:
        return ((level + 1) ** 2) * 10

    @staticmethod
    def level_progress_percent(xp: int) -> int:
        level = XPService.level_from_xp(xp)
        current_level_xp = (level ** 2) * 10
        next_level_xp = XPService.next_level_xp(level)

        if next_level_xp == current_level_xp:
            return 100

        progress = (xp - current_level_xp) / (next_level_xp - current_level_xp)
        return max(0, min(100, int(progress * 100)))