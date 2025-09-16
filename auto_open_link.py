import logging
import signal
import sys
import sqlite3
from datetime import (
    datetime,
    timedelta,
)
from datetime import date

import pytz
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# States for conversation handler
ENTER_LINK_NAME, ENTER_LINK, ENTER_SCHEDULE, ENTER_DAILY_TIME, ENTER_INTERVAL_START, ENTER_INTERVAL_END, ENTER_INTERVAL, INPUT_TIMEZONE, ENTER_TIMEZONE = range(9)


# SQLite setup
def init_db():
    conn = sqlite3.connect('scheduled_links.db')
    c = conn.cursor()
    # Create users table
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY, user_id INTEGER UNIQUE, username TEXT, timezone TEXT)''')
    # Create scheduled_links table
    c.execute('''CREATE TABLE IF NOT EXISTS scheduled_links
                 (id INTEGER PRIMARY KEY, user_id INTEGER, link_name TEXT, link TEXT, scheduled_time TEXT,
                 is_daily BOOLEAN, daily_time TEXT, is_interval BOOLEAN,
                 interval_start TEXT, interval_end TEXT, interval_minutes INTEGER,
                 FOREIGN KEY (user_id) REFERENCES users (user_id))''')
    c.execute('''CREATE TABLE IF NOT EXISTS schedule_jobs
                 (id INTEGER PRIMARY KEY, link_id INTEGER, job_id TEXT,
                 FOREIGN KEY (link_id) REFERENCES scheduled_links (id))''')
    conn.commit()
    conn.close()


def create_schedule_links_jobs(link_id, job_id):
    conn = sqlite3.connect('scheduled_links.db')
    c = conn.cursor()
    c.execute("INSERT INTO schedule_jobs (link_id, job_id) VALUES (?, ?)", (link_id, job_id))
    conn.commit()
    conn.close()


def job_exists(application: Application, user_id: int, link: str) -> bool:
    """Check if a job already exists in the job queue."""
    for job in application.job_queue.jobs():
        if job.data['user_id'] == user_id and job.data['link'] == link:
            return True
    return False


def init_jobs_from_db(application: Application) -> None:
    """Initialize jobs from the database."""
    conn = sqlite3.connect('scheduled_links.db')
    c = conn.cursor()
    
    c.execute('''SELECT u.user_id, link.link_name, link.link, link.scheduled_time, link.is_daily, link.daily_time, link.is_interval, 
                        link.interval_start, link.interval_end, link.interval_minutes, u.timezone, link.id
                 FROM scheduled_links as link
                 JOIN users as u ON link.user_id = u.user_id''')
    scheduled_links = c.fetchall()
    conn.close()

    for link in scheduled_links:
        # if job_exists(application, link[0], link[2]):
        #     continue

        user_id, link_name, link, scheduled_time, is_daily, daily_time, is_interval, interval_start, interval_end, interval_minutes, timezone, link_id = link
        
        user_timezone = get_user_timezone(user_id)  # Default to UTC if not set
        local_tz = pytz.timezone(user_timezone)
        if is_daily:
            daily_time_obj = datetime.strptime(daily_time, "%H:%M").time()
            daily_time_utc = local_tz.localize(datetime.combine(date.today(), daily_time_obj)).astimezone(pytz.utc).time()
            job = application.job_queue.run_daily(
                open_link, daily_time_utc,
                data={'chat_id': user_id, 'link': link, 'user_id': user_id, 'name': link_name},
                days=(0, 1, 2, 3, 4, 5, 6)
            )
            create_schedule_links_jobs(link_id, job.id)
        elif is_interval:
            interval_start_obj = datetime.strptime(interval_start, "%H:%M").time()
            interval_end_obj = datetime.strptime(interval_end, "%H:%M").time()
            current_time = datetime.now().replace(hour=interval_start_obj.hour, minute=interval_start_obj.minute, second=0, microsecond=0)
            end_time = datetime.now().replace(hour=interval_end_obj.hour, minute=interval_end_obj.minute, second=0, microsecond=0)
            local_current_time = local_tz.localize(current_time)
            local_end_time = local_tz.localize(end_time)

            # Convert to UTC
            current_time_utc = local_current_time.astimezone(pytz.utc)
            end_time_utc = local_end_time.astimezone(pytz.utc)

            while current_time_utc <= end_time_utc:
                job = application.job_queue.run_daily(
                    open_link, current_time_utc.time(),
                    data={'chat_id': user_id, 'link': link, 'user_id': user_id, 'name': link_name},
                    days=(0, 1, 2, 3, 4, 5, 6)
                )
                current_time_utc += timedelta(minutes=interval_minutes)
                create_schedule_links_jobs(link_id, job.id)

def add_user_to_db(user_id, username):
    conn = sqlite3.connect('scheduled_links.db')
    c = conn.cursor()
    c.execute("INSERT INTO users (user_id, username) VALUES (?, ?)", (user_id, username))
    conn.commit()
    conn.close()

def check_user_exist(user_id):
    conn = sqlite3.connect('scheduled_links.db')
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = c.fetchone()
    conn.close()
    return user

def add_link_to_db(user_id, link_name, link, scheduled_time, is_daily=False, daily_time=None,
                   is_interval=False, interval_start=None, interval_end=None, interval_minutes=None, username=None):
    user_exist = check_user_exist(user_id)
    if not user_exist:
        add_user_to_db(user_id, username)

    conn = sqlite3.connect('scheduled_links.db')
    c = conn.cursor()
    c.execute('''INSERT INTO scheduled_links
                 (user_id, link_name, link, scheduled_time, is_daily, daily_time, is_interval, interval_start, interval_end, interval_minutes) 
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
              (user_id, link_name, link, scheduled_time.isoformat(), is_daily, daily_time,
               is_interval, interval_start, interval_end, interval_minutes))
    conn.commit()

    c.execute("SELECT * FROM scheduled_links WHERE user_id = ? AND link = ?", (user_id, link))
    latest_record = c.fetchone()
    link_id = latest_record[0]
    conn.close()

    return link_id


def get_links_from_db(user_id):
    conn = sqlite3.connect('scheduled_links.db')
    c = conn.cursor()
    c.execute('''SELECT u.user_id, u.timezone, sl.id, sl.link_name, sl.link, sl.scheduled_time, sl.is_daily, 
                        sl.daily_time, sl.is_interval, sl.interval_start, sl.interval_end, sl.interval_minutes 
                 FROM users u 
                 JOIN scheduled_links sl ON u.user_id = sl.user_id 
                 WHERE u.user_id = ?''', (user_id,))
    links = c.fetchall()
    conn.close()
    return links


def delete_link_from_db(link_id):
    conn = sqlite3.connect('scheduled_links.db')
    c = conn.cursor()
    c.execute("DELETE FROM scheduled_links WHERE id = ?", (link_id,))
    conn.commit()
    clear_job_of_link_from_db(link_id=link_id)
    conn.close()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Welcome to the Mini App Scheduler Bot!\n\n"
        "Available commands:\n"
        "/create - Tạo nhắc nhở sau khoảng thời gian (phút) \n"
        "/create_daily - Tạo nhắc nhở định kì hàng ngày\n"
        "/create_interval - Tạo nhắc nhở định kì hàng ngày trong khoảng thời gian \n"
        "/list - Danh sách nhắc nhở \n"
        "/delete - Xóa nhắc nhở \n"
        "/delete_all - Xóa tất cả nhắc nhở \n"
        "/add_timezone - Chọn khu vực thời gian \n"
    )
    return ENTER_TIMEZONE


async def input_timezone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Nhập khu vực thời gian (e.g., 'Asia/Ho_Chi_Minh', 'Asia/Tokyo', 'Asia/Seoul'):")
    return ENTER_TIMEZONE


async def enter_timezone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_timezone = update.message.text.strip()
    user_id = update.effective_user.id
    try:
        # Validate the timezone
        pytz.timezone(user_timezone)
        # Save timezone to user table
        conn = sqlite3.connect('scheduled_links.db')
        c = conn.cursor()
        c.execute("UPDATE users SET timezone = ? WHERE user_id = ?", (user_timezone, user_id))
        conn.commit()
        conn.close()
        
        await update.message.reply_text(f"Timezone set to {user_timezone}. You can now schedule links.")
        return ConversationHandler.END
    except pytz.UnknownTimeZoneError:
        await update.message.reply_text("Invalid timezone. Please enter a valid timezone (e.g., 'Asia/Ho_Chi_Minh', 'Asia/Tokyo', 'Asia/Seoul').")
        return ENTER_TIMEZONE


async def create_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Tên link:")
    return ENTER_LINK_NAME


async def enter_link_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['link_name'] = update.message.text
    await update.message.reply_text("Nhập link:")
    return ENTER_LINK


async def enter_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['link'] = update.message.text
    await update.message.reply_text(
        "Nhập số phút để nhắc nhở mở link (tính từ hiện tại): "
    )
    return ENTER_SCHEDULE


def remove_schedule_from_db(user_id, link_name, link):
    conn = sqlite3.connect('scheduled_links.db')
    c = conn.cursor()
    c.execute("DELETE FROM scheduled_links WHERE user_id = ? AND link_name = ? AND link = ?", (user_id, link_name, link))
    conn.commit()
    conn.close()

async def enter_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        minutes = int(update.message.text)
        if minutes <= 0:
            raise ValueError("Minutes must be positive")

        user_timezone = get_user_timezone(update.effective_user.id)  # Default to UTC if not set
        local_tz = pytz.timezone(user_timezone)
        open_time = (datetime.now() + timedelta(minutes=minutes)).astimezone(local_tz)
        link_name = context.user_data['link_name']
        link = context.user_data['link']
        user_id = update.effective_user.id

        link_id = add_link_to_db(user_id, link_name, link, open_time)

        job = context.job_queue.run_once(
            open_link,
            timedelta(minutes=minutes),
            data={
                'chat_id': update.effective_chat.id,
                'link': link,
                'user_id': user_id,
                'name': link_name,
            }
        )
        remove_schedule_from_db(user_id, link_name, link)

        await update.message.reply_text(f"Link '{link_name}' sẽ được nhắc mở lúc {open_time.strftime('%H:%M')}.")
    except ValueError:
        await update.message.reply_text("Please enter a valid positive number of minutes.")
        return ENTER_SCHEDULE

    return ConversationHandler.END


async def create_daily_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['link_name'] = update.message.text
    await update.message.reply_text("Nhập link: ")
    return ENTER_LINK


async def enter_daily_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['link'] = update.message.text
    await update.message.reply_text(
        "Nhập thời gian nhắc nhở mở link (định dạng HH:MM , 24-hour clock):"
    )
    return ENTER_DAILY_TIME


async def schedule_daily_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        daily_time = datetime.strptime(update.message.text, "%H:%M").time()
        link = context.user_data['link']
        user_id = update.effective_user.id

        user_timezone = get_user_timezone(user_id)  # Default to UTC if not set
        local_tz = pytz.timezone(user_timezone)
        now = datetime.now(local_tz)
        schedule_time = now.replace(hour=daily_time.hour, minute=daily_time.minute, second=0, microsecond=0)
        if schedule_time <= now:
            schedule_time += timedelta(days=1)

        link_name = context.user_data['link_name']
        link_id = add_link_to_db(user_id, link_name, link, schedule_time, is_daily=True, daily_time=daily_time.strftime("%H:%M"))

        # Schedule job in UTC
        job = context.job_queue.run_daily(
            open_link, schedule_time.astimezone(pytz.utc).time(),  # Convert to UTC
            data={'chat_id': update.effective_chat.id, 'link': link, 'user_id': user_id, 'name': link_name},
            days=(0, 1, 2, 3, 4, 5, 6)
        )
        create_schedule_links_jobs(link_id, job.id)

        await update.message.reply_text(f"Tạo nhắc nhở mở link hàng ngày thành công. Tin nhắn gửi lúc {daily_time.strftime('%H:%M')}.")
    except ValueError:
        await update.message.reply_text("Please enter a valid time in HH:MM format.")
        return ENTER_DAILY_TIME

    return ConversationHandler.END


async def create_interval_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['link_name'] = update.message.text
    await update.message.reply_text("Nhập link:")
    return ENTER_LINK


async def enter_interval_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['link'] = update.message.text
    await update.message.reply_text(
        "Nhập thời gian bắt đầu tạo tin nhắn nhắc nhở (in HH:MM format, 24-hour clock):"
    )
    return ENTER_INTERVAL_START


async def enter_interval_end(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['interval_start'] = update.message.text
    await update.message.reply_text(
        "Nhập thời gian kết thúc tạo tin nhắn nhắc nhở (in HH:MM format, 24-hour clock):"
    )
    return ENTER_INTERVAL_END


async def enter_interval(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['interval_end'] = update.message.text
    await update.message.reply_text(
        "Thời gian mỗi lần nhắc nhở:"
    )
    return ENTER_INTERVAL

def get_user_timezone(user_id):
    conn = sqlite3.connect('scheduled_links.db')
    c = conn.cursor()
    c.execute("SELECT timezone FROM users WHERE user_id = ?", (user_id,))
    timezone = c.fetchone()
    conn.close()

    return timezone[0] if (timezone and timezone[0]) else 'Asia/Ho_Chi_Minh'

async def schedule_interval_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_timezone = get_user_timezone(update.effective_user.id)  # Default to UTC if not set
    local_tz = pytz.timezone(user_timezone)

    try:
        interval_minutes = int(update.message.text)
        if interval_minutes <= 0:
            raise ValueError("Interval must be positive")

        link = context.user_data['link']
        interval_start = datetime.strptime(context.user_data['interval_start'], "%H:%M").time()
        interval_end = datetime.strptime(context.user_data['interval_end'], "%H:%M").time()
        user_id = update.effective_user.id

        now = datetime.now(local_tz)
        schedule_time = now.replace(hour=interval_start.hour, minute=interval_start.minute, second=0, microsecond=0)
        if schedule_time <= now:
            schedule_time += timedelta(days=1)

        link_name = context.user_data['link_name']
        link_id = add_link_to_db(user_id, link_name, link, schedule_time, is_interval=True,
                       interval_start=interval_start.strftime("%H:%M"),
                       interval_end=interval_end.strftime("%H:%M"),
                       interval_minutes=interval_minutes)

        # Schedule jobs in UTC
        current_time = schedule_time.astimezone(pytz.utc)  # Convert to UTC
        end_time = schedule_time.replace(hour=interval_end.hour, minute=interval_end.minute).astimezone(pytz.utc)  # Convert to UTC
        while current_time <= end_time:
            job =context.job_queue.run_daily(
                open_link, current_time.time(),
                data={'chat_id': update.effective_chat.id, 'link': link, 'user_id': user_id, 'name': link_name},
                days=(0, 1, 2, 3, 4, 5, 6)
            )
            create_schedule_links_jobs(link_id, job.id)
            current_time += timedelta(minutes=interval_minutes)

        await update.message.reply_text(
            f"Thành công! Nhắc nhở sẽ gửi mỗi {interval_minutes} phút từ {interval_start.strftime('%H:%M')} tới {interval_end.strftime('%H:%M')} mỗi ngày."
        )
    except ValueError as e:
        await update.message.reply_text(f"Invalid input: {str(e)}")
        return ENTER_INTERVAL

    return ConversationHandler.END


def clear_all_jobs(application: Application) -> None:
    """Clear all scheduled jobs."""
    for job in application.job_queue.jobs():
        job.schedule_removal()


def clear_job(application: Application, job_id: str) -> None:
    """Clear a specific job by job ID."""
    jobs = application.job_queue.jobs()  # Get all jobs
    job = next((j for j in jobs if j.id == job_id), None)  # Find the job by ID
    if job:
        job.schedule_removal()


async def open_link(context: ContextTypes.DEFAULT_TYPE) -> None:
    job = context.job
    link = job.data['link']
    name = job.data['name']
    message = f"Đã tới giờ mở app: <a href='{link}'>{name}</a>"
    await context.bot.send_message(
        job.data['chat_id'],
        text=message,
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True
    )
    # TODO: combine message with message open in same time


async def list_links(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    links = get_links_from_db(user_id)
    local_tz = pytz.timezone(get_user_timezone(user_id))

    if not links:
        await update.message.reply_text("No scheduled links.")
        return

    message = "Scheduled links:\n\n"
    for link in links:
        scheduled_time = datetime.fromisoformat(link[5]).astimezone(local_tz).strftime('%H:%M %d-%m-%Y')
        if link[6]:
            message += f"Name: {link[3]}\nLink: {link[4]}\nScheduled daily at: {scheduled_time}\n\n"
        elif link[8]:
            start_time = datetime.strptime(link[9], "%H:%M").time()
            end_time = datetime.strptime(link[10], "%H:%M").time()
            message += f"Name: {link[3]}\nLink: {link[4]}\nScheduled every {link[11]} minutes from {start_time} to {end_time} daily\n\n"
        else:
            message += f"Name: {link[3]}\nLink: {link[4]}\nScheduled for: {scheduled_time}\n\n"

    await update.message.reply_text(message)


async def delete_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    links = get_links_from_db(user_id)
    local_tz = pytz.timezone('Asia/Ho_Chi_Minh')
    if not links:
        await update.message.reply_text("No scheduled links to delete.")
        return

    keyboard = [
        [InlineKeyboardButton(f"Delete: {link[3]}", callback_data=f"delete_{link[2]}")]
        for link in links
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Select a link to delete:", reply_markup=reply_markup)


async def delete_all_links(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    links = get_links_from_db(user_id)

    if not links:
        await update.message.reply_text("No scheduled links to delete.")
        return

    for link in links:
        delete_link_from_db(link[2])
    
    clear_all_jobs(context.application)
    await update.message.reply_text("Deleted all scheduled links.")


def get_all_job_of_link_from_db(link_id):
    conn = sqlite3.connect('scheduled_links.db')
    c = conn.cursor()
    c.execute("SELECT job_id FROM schedule_jobs WHERE link_id = ?", (link_id,))
    job_ids = c.fetchall()
    conn.close()
    return [job_id[0] for job_id in job_ids]


def clear_job_of_link_from_db(link_id):
    conn = sqlite3.connect('scheduled_links.db')
    c = conn.cursor()
    c.execute("DELETE FROM schedule_jobs WHERE link_id = ?", (link_id,))
    conn.commit()
    conn.close()

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    if query.data.startswith("delete_"):
        link_id = int(query.data[7:])
        delete_link_from_db(link_id)
        job_ids = get_all_job_of_link_from_db(link_id)
        for job_id in job_ids:
            clear_job(context.application, job_id)
        await query.edit_message_text(f"Xóa thành công!")


async def run_now(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    links = get_links_from_db(user_id)

    if not links:
        await update.message.reply_text("No scheduled links to run.")
        return

    keyboard = [
        [InlineKeyboardButton(f"Run: {link[1]}", callback_data=f"run_{link[0]}")]
        for link in links
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Select a link to run now:", reply_markup=reply_markup)


async def run_now_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    if query.data.startswith("run_"):
        link_id = int(query.data[4:])
        links = get_links_from_db(update.effective_user.id)
        link = next((l for l in links if l[0] == link_id), None)
        if link:
            await open_link(context.job_queue.jobs()[0])
            await query.edit_message_text(f"Ran scheduled link with ID: {link_id}")
        else:
            await query.edit_message_text("This link doesn't exist.")



def signal_handler(sig, frame):
    """Handle termination signals."""
    print("Stopping the bot and clearing all jobs...")
    clear_all_jobs(application)  # Clear all jobs
    sys.exit(0)  # Exit the program


def get_all_reminders_from_db(user_id):
    conn = sqlite3.connect('scheduled_links.db')
    c = conn.cursor()
    c.execute('''SELECT sl.link_name, sl.link, sl.scheduled_time, sl.is_daily, sl.daily_time, sl.is_interval, sl.interval_start, sl.interval_end, sl.interval_minutes,
                u.user_id, u.timezone
                 FROM scheduled_links sl
                 JOIN users u ON sl.user_id = u.user_id
                 WHERE u.user_id = ?''', (user_id,))
    reminders = c.fetchall()
    conn.close()
    return reminders


async def show_all_reminders(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    reminders = get_all_reminders_from_db(user_id)

    if not reminders:
        await update.message.reply_text("No scheduled reminders found.")
        return

    message = "All Scheduled Reminders:\n\n"
    for reminder in reminders:
        link_name, link, scheduled_time, is_daily, daily_time, is_interval, interval_start, interval_end, interval_minutes, user_id, timezone = reminder
        message += f"User ID: {user_id}\nTimezone: {timezone or 'Asia/Ho_Chi_Minh'}\n\n"
        message += f"Name: {link_name}\nLink: {link}\nScheduled Time: {scheduled_time}\n"
        if is_daily:
            message += f"Daily Reminder at: {daily_time}\n"
        if is_interval:
            message += f"Interval Reminder from {interval_start} to {interval_end} every {interval_minutes} minutes\n"
        message += "\n"

    await update.message.reply_text(message)


def main() -> None:
    application = Application.builder().token('7399222125:AAGw45eR4V8cswcZC-jGRDWviy6VdiX4WAo').build()

    init_db()
    init_jobs_from_db(application)

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('create', create_link)],
        states={
            ENTER_LINK_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_link_name)],
            ENTER_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_link)],
            ENTER_SCHEDULE: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_schedule)],
        },
        fallbacks=[CommandHandler('cancel', lambda u, c: ConversationHandler.END)],
    )

    daily_conv_handler = ConversationHandler(
        entry_points=[CommandHandler('create_daily', create_link)],
        states={
            ENTER_LINK_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, create_daily_link)],
            ENTER_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_daily_time)],
            ENTER_DAILY_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, schedule_daily_link)],
        },
        fallbacks=[CommandHandler('cancel', lambda u, c: ConversationHandler.END)],
    )

    interval_conv_handler = ConversationHandler(
        entry_points=[CommandHandler('create_interval', create_link)],
        states={
            ENTER_LINK_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, create_interval_link)],
            ENTER_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_interval_start)],
            ENTER_INTERVAL_START: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_interval_end)],
            ENTER_INTERVAL_END: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_interval)],
            ENTER_INTERVAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, schedule_interval_link)],
        },
        fallbacks=[CommandHandler('cancel', lambda u, c: ConversationHandler.END)],
    )

    add_timezone_handler = ConversationHandler(
        entry_points=[CommandHandler('add_timezone', input_timezone)],
        states={
            ENTER_TIMEZONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_timezone)],
        },
        fallbacks=[CommandHandler('cancel', lambda u, c: ConversationHandler.END)],
    )
    application.add_handler(add_timezone_handler)

    application.add_handler(CommandHandler("start", start))
    application.add_handler(conv_handler)
    application.add_handler(daily_conv_handler)
    application.add_handler(interval_conv_handler)
    application.add_handler(CommandHandler("list", list_links))
    application.add_handler(CommandHandler("delete", delete_link))
    application.add_handler(CommandHandler("run_now", run_now))
    application.add_handler(CommandHandler("delete_all", delete_all_links))
    application.add_handler(CallbackQueryHandler(button_callback, pattern="^delete_"))
    application.add_handler(CallbackQueryHandler(run_now_callback, pattern="^run_"))
    application.add_handler(CommandHandler("show_reminders", show_all_reminders))
    application.add_handler(CommandHandler("show_all_reminders", show_all_reminders))

    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
