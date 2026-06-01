def send_desktop_notification(title, message):
    try:
        from plyer import notification

        notification.notify(
            title=title,
            message=message,
            app_name="AiOS Assistant",
            timeout=8,
        )
        return True
    except Exception:
        print(f"[AiOS notification] {title}: {message}")
        return False
