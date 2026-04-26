@router.get("/user")
async def get_user(
        db: AsyncSession = Depends(get_db),
        user=Depends(get_current_user),
):
    # 🔥 XP va Streak ni alohida so'rab olish
    xp_result = await db.execute(
        select(UserXP).where(UserXP.user_id == user.tg_id)
    )
    xp_row = xp_result.scalar_one_or_none()

    streak_result = await db.execute(
        select(Streak).where(Streak.user_id == user.tg_id)
    )
    streak_row = streak_result.scalar_one_or_none()

    xp = xp_row.total_xp if xp_row else 0
    level = XPService.level_from_xp(xp)

    missions = await MissionService.get_daily_missions(db, user.tg_id)

    display_name = (
            user.nickname
            or user.first_name
            or user.username
            or "Learner"
    )

    return {
        "telegram": {
            "id": user.tg_id,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "username": user.username,
            "photo_url": user.photo_url,
        },
        "nickname": user.nickname,
        "display_name": display_name,
        "xp": xp,
        "level": level,
        "level_progress": XPService.level_progress_percent(xp),
        "next_level_xp": XPService.next_level_xp(level),
        "streak": streak_row.streak if streak_row else 0,
        "best_streak": streak_row.best_streak if streak_row else 0,
        "missions": missions,
    }