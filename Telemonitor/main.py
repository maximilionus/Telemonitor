from os import chdir, path
import logging

from aiogram import Bot, Dispatcher, executor, types
from aiogram.utils.markdown import bold, code

from Telemonitor import helpers as h, \
    __version__


def run():
    # Initialization
    chdir(path.dirname(__file__))
    h.init_logger()
    logger = logging.getLogger('TM.Main')

    cfg = h.TM_Config().get()
    wls = h.TM_Whitelist()
    api_token = cfg["api_key"]
    bot = Bot(token=api_token)
    dp = Dispatcher(bot)

    # Inline keyboard for controls
    ikb = h.TM_ControlInlineKB(bot, dp)

    # Handlers
    @dp.message_handler(commands=['start'])
    async def __command_start(message: types.Message):
        if wls.is_whitelisted(message.from_user.id):
            await message.reply(
                f'{bold("Welcome to the Telemonitor control panel.")}\nVersion: {code(__version__)}\n',
                reply=False,
                parse_mode=h.PARSE_MODE,
                reply_markup=ikb.get_keyboard()
            )

    print('Bot is starting')
    logger.info("Bot is starting")
    executor.start_polling(
        dp,
        skip_updates=True,
        on_startup=lambda _: h.TM_Whitelist.send_to_all(bot, code("System was booted")),
        on_shutdown=lambda _: h.TM_Whitelist.send_to_all(bot, code("System is shutting down"))
    )
