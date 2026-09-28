"""User-facing localized texts in Uzbek Latin script."""

# Exact required strings
WELCOME_ADMIN = (
    "👑 <b>Assalomu alaykum, Administrator!</b>\n\n"
    "AQL ZIYOSI Gatekeeper boshqaruv tizimiga xush kelibsiz.\n\n"
    "⚙️ Guruhlar, majburiy kanallar, statistika va xabarnomalarni boshqarish uchun quyidagi <b>Admin panel</b> tugmasidan foydalaning.\n"
    "➕ Botingizni yangi guruh yoki kanallarga tezkor admin qilib biriktirish uchun quyidagi tugmalarni bosing:"
)
NOT_ADMIN = "⛔️ Bu buyruq faqat administratorlar uchun."
DECLINE_DM = (
    "⛔️ Kechirasiz, guruhga qo'shilish uchun avval quyidagi kanal(lar)ga a'zo bo'lishingiz kerak:\n"
    "{channels}\n\n"
    "Barcha kanallarga a'zo bo'lgach, quyidagi «✅ Obuna bo'ldim» tugmasini bosing."
)
APPROVE_DM = "✅ Xush kelibsiz! Siz «{group_title}» guruhiga qabul qilindingiz."
NEW_GROUP_DETECTED = (
    "🆕 Bot yangi guruhga admin qilib qo'shildi: «{title}»\n\n"
    "Uni himoyalangan guruhlar ro'yxatiga qo'shaymi?"
)
NEW_CHANNEL_DETECTED = (
    "🆕 Bot yangi kanalga admin qilib qo'shildi: «{title}»\n\n"
    "Uni majburiy kanallar ro'yxatiga qo'shaymi?"
)
LEFT_NON_ADMIN_ADD = "Meni faqat administrator qo'sha oladi. Chiqib ketdim."
GENERIC_ERROR = "⚠️ Texnik xatolik yuz berdi."

# Additional texts for buttons & navigation
BTN_CONFIRM_PROTECT = "✅ Ha, himoyalash"
BTN_REJECT_PROTECT = "❌ Yo'q"
BTN_CONFIRM_REQUIRED = "✅ Ha, majburiy qilish"
BTN_REJECT_REQUIRED = "❌ Yo'q"
BTN_BACK = "⬅️ Orqaga"
BTN_MAIN_MENU = "🏠 Bosh menyu"

ADMIN_MENU_TITLE = "⚙️ <b>Administrator paneli</b>\n\nKerakli bo'limni tanlang:"
ADMIN_BTN_GROUPS = "🛡 Himoyalangan guruhlar ({count})"
ADMIN_BTN_CHANNELS = "📢 Majburiy kanallar ({count})"
ADMIN_BTN_ADMINS = "👥 Administratorlar ({count})"

WARN_NO_INVITE_PERMISSION = (
    "⚠️ <b>Diqqat:</b> Bot «{title}» guruhida taklif qilish (invite users / manage join requests) "
    "huquqiga ega emas. So'rovlarni avtomatik qabul qilish uchun botga ushbu huquqni bering."
)
ALERT_ACCESS_LOST = (
    "⚠️ <b>Ogohlantirish!</b> Bot «{title}» (ID: <code>{chat_id}</code>) kanaliga a'zolikni "
    "tekshirish huquqini yo'qotdi. Iltimos, bot adminlik huquqlarini tekshiring!"
)
ALERT_BOT_REMOVED = (
    "ℹ️ Bot «{title}» (ID: <code>{chat_id}</code>) {chat_type}idan chiqarildi yoki adminlikdan olindi. "
    "Ushbu ob'ekt nofaol holatga o'tkazildi."
)
ALERT_NON_ADMIN_ATTEMPT = (
    "⚠️ Noma'lum foydalanuvchi (ID: <code>{user_id}</code>) botni «{title}» (ID: <code>{chat_id}</code>) "
    "guruhiga qo'shishga urindi. Bot guruhdan chiqib ketdi."
)

PUBLIC_GREETING = (
    "👋 <b>Assalomu alaykum!</b>\n\n"
    "Men guruhlarni tozalovchi va a'zolikni nazorat qiluvchi aqlli yordamchi botman.\n\n"
    "✨ <b>Asosiy imkoniyatlarim:</b>\n"
    "• 🧹 <b>Kirdi-chiqdilarni tozalash:</b> Guruhdagi <i>«Falonchi qo'shildi»</i> va <i>«Falonchi chiqib ketdi»</i> degan keraksiz xabarlarni avtomatik o'chirib, guruhingizni doimo ozoda saqlayman.\n"
    "• 🛡 <b>A'zolik nazorati:</b> Guruhga kirish so'rovlarini qabul qilib, spamlardan himoya qilaman.\n\n"
    "🚀 <b>Mendan foydalanish uchun:</b>\n"
    "Quyidagi tugma orqali meni guruhingizga qo'shing va <b>Administrator</b> huquqini bering. Men o'sha zahotiyoq guruhni tozalashni boshlayman!"
)
ASK_CHANNEL_URL = (
    "🔗 «{title}» kanali uchun foydalanuvchilarga ko'rsatiladigan havola (link) yuboring:\n"
    "Misol: https://t.me/+abcdef yoki @kanal_nomi"
)
CHANNEL_URL_SAVED = "✅ «{title}» kanali uchun havola muvaffaqiyatli saqlandi: {url}"
GROUP_SAVED = "✅ «{title}» guruhi himoyalangan guruhlar ro'yxatiga qo'shildi."
GROUP_IGNORED = "❌ «{title}» guruhi saqlanmadi."
CHANNEL_SAVED = "✅ «{title}» kanali majburiy kanallar ro'yxatiga qo'shildi."
CHANNEL_IGNORED = "❌ «{title}» kanali saqlanmadi."
ADMIN_ADDED = "✅ Foydalanuvchi <code>{tg_id}</code> administrator sifatida qo'shildi."
ADMIN_REMOVED = "✅ Foydalanuvchi <code>{tg_id}</code> administratorlar ro'yxatidan o'chirildi."
