import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from database import *

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

PANEL_SUPPORT_ID = 1991147205
REPRESENTATIVE_ID = 5452850794
ADMINS = {PANEL_SUPPORT_ID, REPRESENTATIVE_ID}

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    raise ValueError("توکن ربات در متغیر محیطی TELEGRAM_BOT_TOKEN تنظیم نشده است.")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    add_user(user.id, user.username, user.first_name)

    if is_blocked(user.id):
        await update.message.reply_text("⛔ شما مسدود شده‌اید.")
        return

    keyboard = [[KeyboardButton("پشتیبانی")]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)

    welcome_text = """
سلام! به ربات پشتیبانی و پنل ساماندهی خوش آمدید.

برای ورود به پنل کاربری، روی دکمه پایین (mini app) کلیک کنید 👇🏻👇🏻👇🏻👇🏻.
🔸 در صورت بروز مشکل، برای چت و ارتباط با پشتیبانی پنل کاربری و یا نماینده، روی دکمه «پشتیبانی» کلیک کنید.

⚠️ نکته مهم:
برای ورود به پنل کاربری VPN نیاز دارید.
در صورت بروز مشکل، لطفاً VPN خود را تغییر دهید.
    """

    await update.message.reply_text(welcome_text, reply_markup=reply_markup)

async def support_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if is_blocked(user.id):
        await update.message.reply_text("⛔ شما مسدود شده‌اید.")
        return

    keyboard = [
        [InlineKeyboardButton("🛠 مشکلات پنل کاربری", callback_data='support_panel')],
        [InlineKeyboardButton("🤝 ارتباط با نماینده", callback_data='support_rep')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("لطفاً نوع پشتیبانی مورد نیاز خود را انتخاب کنید:", reply_markup=reply_markup)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user = update.effective_user
    if is_blocked(user.id):
        await query.edit_message_text("⛔ شما مسدود شده‌اید.")
        return

    if query.data == 'support_panel':
        context.user_data['support_type'] = 'panel'
        await query.edit_message_text("🔹 پیام خود را در مورد مشکلات پنل کاربری ارسال کنید. پیام شما برای پشتیبانی ارسال خواهد شد.")
    elif query.data == 'support_rep':
        context.user_data['support_type'] = 'representative'
        await query.edit_message_text("🔹 پیام خود را برای ارتباط با نماینده ارسال کنید.")

async def forward_to_support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if is_blocked(user.id):
        await update.message.reply_text("⛔ شما مسدود شده‌اید.")
        return

    support_type = context.user_data.get('support_type')
    if not support_type:
        return

    target_admin = PANEL_SUPPORT_ID if support_type == 'panel' else REPRESENTATIVE_ID

    user_info = f"""
📩 پیام جدید:
👤 نام: {user.first_name}
🔖 یوزرنیم: @{user.username if user.username else 'ندارد'}
🆔 آیدی عددی: {user.id}
📝 پیام:
{update.message.text if update.message.text else '[رسانه]'}
    """

    try:
        sent_message = await context.bot.send_message(
            chat_id=target_admin,
            text=user_info
        )
        save_message_map(user.id, sent_message.message_id, update.message.message_id, support_type)
    except Exception as e:
        logger.error(f"Error sending to admin: {e}")

async def admin_reply_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        return

    admin_msg_id = update.message.reply_to_message.message_id
    result = get_user_id_by_admin_message(admin_msg_id)

    if not result:
        return

    user_id, support_type = result

    reply_text = update.message.text or "[رسانه]"
    footer = "\n\n> _برای پاسخ به این پیام، روی آن ریپلای بزنید._"

    try:
        await context.bot.send_message(
            chat_id=user_id,
            text=reply_text + footer
        )
    except Exception as e:
        logger.error(f"Error replying to user: {e}")

async def block_user_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMINS:
        return

    if len(context.args) == 0:
        await update.message.reply_text("UsageId: /block <user_id>")
        return

    try:
        user_id = int(context.args[0])
        block_user(user_id)
        await update.message.reply_text(f"✅ کاربر {user_id} مسدود شد.")
    except Exception as e:
        await update.message.reply_text(f"❌ خطا: {e}")

async def unblock_user_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMINS:
        return

    if len(context.args) == 0:
        await update.message.reply_text("UsageId: /unblock <user_id>")
        return

    try:
        user_id = int(context.args[0])
        unblock_user(user_id)
        await update.message.reply_text(f"✅ کاربر {user_id} آزاد شد.")
    except Exception as e:
        await update.message.reply_text(f"❌ خطا: {e}")

async def list_blocked_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMINS:
        return

    blocked_users = get_blocked_users()
    if not blocked_users:
        await update.message.reply_text("📭 هیچ کاربر مسدود شده‌ای وجود ندارد.")
        return

    text = "📋 لیست کاربران مسدود شده:\n\n"
    for uid, uname, fname in blocked_users:
        text += f"• {fname} (@{uname if uname else '---'}) - {uid}\n"

    await update.message.reply_text(text)

async def broadcast_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMINS:
        return

    if not context.args:
        await update.message.reply_text("UsageId: /broadcast <پیام>")
        return

    message = ' '.join(context.args)
    users = get_all_users()
    success, failed = 0, 0

    for uid in users:
        try:
            await context.bot.send_message(chat_id=uid, text=message)
            success += 1
        except:
            failed += 1

    await update.message.reply_text(f"📬 پیام ارسال شد:\n✅ موفق: {success}\n❌ ناموفق: {failed}")

def main():
    init_db()
    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.Text("پشتیبانی"), support_menu))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE, forward_to_support))
    application.add_handler(MessageHandler(filters.REPLY & filters.Chat(ADMINS), admin_reply_handler))

    application.add_handler(CommandHandler("block", block_user_handler))
    application.add_handler(CommandHandler("unblock", unblock_user_handler))
    application.add_handler(CommandHandler("blocked", list_blocked_handler))
    application.add_handler(CommandHandler("broadcast", broadcast_handler))

    application.run_polling()

if __name__ == "__main__":
    main()