import logging
from os import chdir, path

from aiogram import Bot, Dispatcher, executor, types
from aiogram.utils.markdown import bold, code

from telemonitor import helpers as h, __version__
from telemonitor.extensions import systemd_service
from telemonitor.helpers import TM_Whitelist, TM_ControlInlineKB, cli_arguments_parser, tm_colorama, PARSE_MODE, STRS


args = cli_arguments_parser()


def run():
    colorama = tm_colorama()
    colorama.init(autoreset=True)
    chdir(path.dirname(__file__))

    h.init_logger(args.verbose)
    logger = logging.getLogger(__name__)
    logger.info("Telemonitor is starting")

    # Initialize config and read it
    cfg = h.TM_Config().get()
    if args.config_check_only: exit()

    if args.systemd_service is not None:
        systemd_service.cli(args.systemd_service)

    api_token = cfg["bot"]["token"] if args.token_overwrite is None else args.token_overwrite
    bot = Bot(token=api_token)
    dp = Dispatcher(bot)

    # Inline keyboard for controls
    ikb = TM_ControlInlineKB(bot, dp)

    # Handlers
    @dp.message_handler(commands=['start'])
    async def __command_start(message: types.Message):
        if TM_Whitelist.is_whitelisted(message.from_user.id):
            await message.reply(
                bold(f"Welcome to the {STRS.name} control panel"),
                reply=False,
                parse_mode=PARSE_MODE,
                reply_markup=ikb.keyboard
            )

    if cfg["bot"]["enable_file_transfer"]:
        @dp.message_handler(content_types=['document', 'photo'])
        async def __file_transfer(message: types.Message):
            if TM_Whitelist.is_whitelisted(message.from_user.id):
                h.init_shared_dir()
                if message.content_type == 'document':
                    await message.document.download(path.join(h.PATH_SHARED_DIR, message.document.file_name))
                    logger.info(f'Successfully downloaded file "{message.document.file_name}" to "{path.abspath(h.PATH_SHARED_DIR)}""')
                    await message.reply(text=f"Successfully downloaded file {code(message.document.file_name)}", parse_mode=PARSE_MODE, reply=False)
                elif message.content_type == 'photo':
                    await message.photo[-1].download(h.PATH_SHARED_DIR)
                    logger.info(f'Successfully downloaded image(-s) to "{path.join(path.abspath(h.PATH_SHARED_DIR), "photos")}"')
                    await message.reply(text="Successfully downloaded image(-s)", parse_mode=PARSE_MODE, reply=False)

    print(f'{colorama.Fore.CYAN}{STRS.name}{colorama.Style.RESET_ALL} is starting. Version: {colorama.Fore.CYAN}{__version__}{colorama.Style.RESET_ALL}')
    executor.start_polling(
        dp,
        skip_updates=True,
        on_startup=(lambda _: TM_Whitelist.send_to_all(bot, STRS.message_startup)) if cfg["bot"]["state_notifications"] else None,
        on_shutdown=(lambda _: TM_Whitelist.send_to_all(bot, STRS.message_shutdown)) if cfg["bot"]["state_notifications"] and args.dev_features else None
    )


if __name__ == "__main__":
    run()
