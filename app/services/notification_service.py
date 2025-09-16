import httpx
from app.core.config import settings
from app.db.base import User, Task

class NotificationService:
    def __init__(self, bot_token: str):
        self.bot_token = bot_token
        self.api_url = f"https://api.telegram.org/bot{self.bot_token}"

    async def send_task_creation_notification(self, user: User, task: Task):
        if not user.telegram_chat_id:
            return

        message = (
            f"🚀 New Task Created for Project: {task.project.name}\n\n"
            f"🔹 *Task:* {task.title}\n"
            f"📝 *Description:* {task.description or 'N/A'}\n"
            f"🔗 *Link:* {task.link or 'N/A'}\n"
            f"⏰ *Deadline:* {task.deadline.strftime('%Y-%m-%d %H:%M') if task.deadline else 'N/A'}"
        )

        async with httpx.AsyncClient() as client:
            try:
                await client.post(
                    f"{self.api_url}/sendMessage",
                    json={
                        "chat_id": user.telegram_chat_id,
                        "text": message,
                        "parse_mode": "Markdown",
                    },
                )
            except httpx.RequestError as e:
                print(f"An error occurred while sending Telegram notification: {e}")

notification_service = NotificationService(bot_token=settings.TELEGRAM_BOT_TOKEN)

