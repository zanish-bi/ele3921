def notifications(request):
    if request.user.is_authenticated:
        try:
            count = request.user.userprofile.notifications.filter(is_read=False).count()
        except Exception:
            count = 0
        return {"unread_notifications_count": count}
    return {"unread_notifications_count": 0}
