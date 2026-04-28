def get_difficulty_level(score: float) -> str:
    """
    difficulty_score:
    0.0 - juda oson
    1.0 - juda qiyin
    """
    safe_score = max(0.0, min(1.0, float(score or 0.5)))

    if safe_score < 0.3:
        return "easy"

    if safe_score < 0.6:
        return "medium"

    return "hard"
