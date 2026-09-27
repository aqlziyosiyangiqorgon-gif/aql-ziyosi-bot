"""Admin panel handlers."""

from aiogram import Router

from gatebot.handlers.admin import admins, broadcast, channels, groups, menu
from gatebot.middlewares.admin_only import AdminOnlyMiddleware

admin_router = Router(name="admin_root")
admin_router.message.middleware(AdminOnlyMiddleware())
admin_router.callback_query.middleware(AdminOnlyMiddleware())

admin_router.include_router(menu.router)
admin_router.include_router(groups.router)
admin_router.include_router(channels.router)
admin_router.include_router(admins.router)
admin_router.include_router(broadcast.router)
