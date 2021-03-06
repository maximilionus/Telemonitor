import os
import json
import logging
import platform
import argparse
import subprocess
from math import floor
from time import strftime, asctime
from sys import platform as sys_platform

import colorama
from uptime import uptime
from aiogram import types, Dispatcher, Bot
from aiogram.utils.markdown import code, bold, italic
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ParseMode

from telemonitor import __version__


MAX_LOGS = 30
DIR_LOG = "./Logs"
PATH_CFG = "./config.json"
PATH_SHARED_DIR = "./Shared"
PARSE_MODE = ParseMode.MARKDOWN_V2
DEF_CFG = {
    "config_version": 2,
    "log_files_max": MAX_LOGS,
    "bot": {
        "token": "",
        "whitelisted_users": [],
        "state_notifications": True,
        "enable_file_transfer": True
    },
    "systemd_service": {
        "version": -1
    }
}


class STRS:
    name = "Telemonitor"
    description = "Telegram bot for monitoring your system."
    reboot = "Rebooting the system"
    shutdown = "Shutting down the system"
    message_startup = code("System was booted")
    message_shutdown = code("System is shutting down")


def tm_colorama() -> colorama:
    """ Wrapper around colorama module with feature to disable the colored output

    Returns:
        colorama: Colorama module ready for use
    """
    from telemonitor.main import args

    colorama_obj = colorama

    if args.disable_colored_output:
        # Overwrite all class variables with empty string to disable colored print
        for attr in ("Back", "Cursor", "Fore", "Style"):
            attr_dict = getattr(colorama_obj, attr).__dict__

            for k in attr_dict:
                attr_dict[k] = ""

    return colorama_obj


def init_logger(is_verbose: bool = False):
    """ Initialize python `logging` module

    Args:
        is_verbose (bool, optional): Write more detailed information to log file. Defaults to False.
    """
    colorama = tm_colorama()

    if not os.path.isdir(DIR_LOG):
        os.makedirs(DIR_LOG)
    else:
        log_files = [f for f in os.listdir(DIR_LOG) if os.path.isfile(os.path.join(DIR_LOG, f))]
        log_files_len = len(log_files)
        if log_files_len > (TM_Config.get().get("log_files_max", MAX_LOGS) if TM_Config.is_exist() else MAX_LOGS):
            print(f"- Clearing logs folder. {colorama.Fore.RED}{log_files_len}{colorama.Fore.RESET} files will be removed")
            for log_file in log_files:
                os.remove(os.path.join(DIR_LOG, log_file))

    log_level = logging.DEBUG if is_verbose else logging.INFO
    filename = f'{DIR_LOG}/TMLog_{strftime("%Y-%m-%d_%H-%M-%S")}.log'
    logging.basicConfig(filename=filename, format="[%(asctime)s][%(levelname)s][%(name)s->%(funcName)s]: %(message)s", level=log_level)

    with open(filename, 'wt') as f:
        f.write(f"{STRS.name} ({__version__}) : [ {asctime()} ]\n\n")


def construct_sysinfo() -> str:
    """ Get system information and construct message from it.

    Returns:
        str: Constructed and formatted message, ready for Telegram.
    """
    __uname = platform.uname()
    __sysname = f"{__uname.system} {__uname.release} ({__uname.version})"
    __userhost = f"{os.path.basename(os.path.expanduser('~'))}@{__uname.node}"

    __uptime_raw = uptime()
    __uptime_dict = {
        "days": str(floor(__uptime_raw / (24 * 3600))),
        "hours": str(floor(__uptime_raw / 3600)),
        "mins": str(floor(__uptime_raw / 60 % 60)),
        "secs": str(floor(__uptime_raw % 60))
    }
    __uptime_dict.update({k: f"0{__uptime_dict[k]}" for k in __uptime_dict if len(__uptime_dict[k]) == 1})
    __uptime = f"{__uptime_dict['days']}:{__uptime_dict['hours']}:{__uptime_dict['mins']}:{__uptime_dict['secs']}"

    string_final = f"{bold('System')}: {code(__sysname)}\n{bold('Uptime')} {italic('dd:hh:mm:ss')}: {code(__uptime)}\n{bold('User@Host')}: {code(__userhost)}"
    return string_final


def init_shared_dir() -> bool:
    """ Initialize dir for shared files

    Returns:
        bool:
            True - Dir doesn't exist and was created.
            False - Dir already exists.
    """
    if not os.path.exists(PATH_SHARED_DIR):
        os.makedirs(PATH_SHARED_DIR)
        return True
    else:
        return False


def cli_arguments_parser() -> object:
    """ Parse all startup arguments

    Returns:
        object: Namespace object, generated by `argparse` module
    """
    argparser = argparse.ArgumentParser(
        prog=STRS.name,
        description=STRS.description,
    )
    argparser.add_argument('--version', action='version', version=f'%(prog)s {__version__}')
    argparser.add_argument('--systemd-service', action='store', choices=['install', 'upgrade', 'remove', 'status'], dest='systemd_service', help='linux systemd Telemonitor service control')
    argparser.add_argument('--no-color', action='store_true', dest='disable_colored_output', help="disable colored output (ANSI escape sequences)")

    bot_group = argparser.add_argument_group('bot control optional arguments')
    bot_group.add_argument('--token', action='store', type=str, dest='token_overwrite', metavar='STR', help='force the bot to run with token from the argument instead of the configuration file')
    bot_group.add_argument('--whitelist', action='store', type=int, dest='whitelist_overwrite', metavar='INT', nargs='+', help='force the bot to check whitelisted users from argument instead of the of the configuration file')

    adv_group = argparser.add_argument_group('advanced optional arguments')
    adv_group.add_argument('--dev', help='enable unstable development features', action='store_true', dest='dev_features')
    adv_group.add_argument('--verbose', '-v', help='write debug information to log file', action='store_true')
    adv_group.add_argument('--config-check', action='store_true', help='run config file initialization procedure and exit', dest='config_check_only')
    adv_group.add_argument('--no-config-check', action='store_true', help="don't scan configuration file on start", dest='disable_config_check')

    return argparser.parse_args()


class TM_ControlInlineKB:
    def __init__(self, bot: Bot, dispatcher: Dispatcher):
        """ Generate telegram inline keyboard for bot.

        Args:
            bot (Bot): aiogram Bot object.
            dispatcher (Dispatcher): aiogram Dispatcher object.
        """
        self.__inline_kb = InlineKeyboardMarkup()

        self.__btn_get_sysinfo = InlineKeyboardButton('Sys Info', callback_data='button-sysinfo-press')
        self.__btn_reboot = InlineKeyboardButton('Reboot', callback_data='button-reboot-press')
        self.__btn_shutdown = InlineKeyboardButton('Shutdown', callback_data='button-shutdown-press')

        self.__inline_kb.add(self.__btn_get_sysinfo)
        self.__inline_kb.row(self.__btn_reboot, self.__btn_shutdown)

        @dispatcher.callback_query_handler()
        async def __callback_ctrl_press(callback_query: types.CallbackQuery):
            if not TM_Whitelist.is_whitelisted(callback_query.from_user.id): return False

            data = callback_query.data
            if data == 'button-sysinfo-press':
                await bot.answer_callback_query(callback_query.id)
                message = construct_sysinfo()
                await bot.send_message(callback_query.from_user.id, message, parse_mode=PARSE_MODE)

            elif data == 'button-reboot-press':
                await bot.answer_callback_query(callback_query.id, STRS.reboot, show_alert=True)

                if sys_platform == 'linux': subprocess.run(['shutdown', '-r', 'now'])
                elif sys_platform == 'darwin': subprocess.run(['shutdown', '-r', 'now'])
                elif sys_platform == 'win32': subprocess.run(['shutdown', '/r', '/t', '0'])

            elif data == 'button-shutdown-press':
                await bot.answer_callback_query(callback_query.id, STRS.shutdown, show_alert=True)

                if sys_platform == 'linux': subprocess.run(['shutdown', 'now'])
                elif sys_platform == 'darwin': subprocess.run(['shutdown', '-h', 'now'])
                elif sys_platform == 'win32': subprocess.run(['shutdown', '/s', '/t', '0'])

    @property
    def keyboard(self) -> object:
        """ Get generated inline keyboard.

        Returns:
            object: Inline keyboard.
        """
        return self.__inline_kb


class TM_Whitelist:
    __logger = logging.getLogger(__name__)

    @classmethod
    def is_whitelisted(cls, user_id: int) -> bool:
        """ Check is user in whitelist.

        Args:
            user_id (int): Telegram user id.

        Returns:
            bool:
                True - User is whitelisted.
                False - User is not whitelisted.
        """
        users = cls.get_whitelist()
        return user_id in users

    @classmethod
    def get_whitelist(cls) -> list:
        """ Get all whitelisted users from config file.

        Returns:
            list: All whitelisted users.
        """
        from telemonitor.main import args
        cls.__logger.debug('Whitelist read request')
        whitelist = TM_Config.get()["bot"]["whitelisted_users"] if args.whitelist_overwrite is None else args.whitelist_overwrite
        cls.__logger.debug(f"Whitelist content: {whitelist}")

        return whitelist

    @classmethod
    async def send_to_all(cls, bot: object, message: str) -> bool:
        """ Send message to all users in whitelist.

        Args:
            bot (object): aiogram bot object.
            message (str): Text of the message.

        Returns:
            bool:
                True - Message sent.
                False - Message not sent.
        """
        for user in cls.get_whitelist():
            try:
                await bot.send_message(user, message, parse_mode=PARSE_MODE)
                cls.__logger.debug(f"Successfully sent startup message to user [{user}]")
                return True
            except Exception as e:
                cls.__logger.error(f"Can't send message to whitelisted user [{user}]: < {str(e)} >")
                return False


class TM_Config:
    __config = {}
    __last_mod_time = None
    __logger = logging.getLogger(__name__)

    def __init__(self):
        """
        Initialize configuration file.
        If the configuration file is not found - it will be created.
        If the configuration file is found - it will be checked for all necessary values.
        """
        from telemonitor.main import args

        colorama = tm_colorama()
        if not self.is_exist():
            self.create()
            self.__logger.info("First start detected")
            print(f"Config file was generated in {colorama.Fore.CYAN}{os.path.abspath(PATH_CFG)}")

            if args.token_overwrite and args.whitelist_overwrite:
                text = "Reading bot token and whitelist from input arguments"
                self.__logger.info(text)
                print('- ' + text)
            else:
                # Generate config file and exit if no token and whitelist startup args provided
                print("First, you need to configure it's values and then run the script again.")
                exit()

        cfg = self.get()

        if args.disable_config_check:
            self.__logger.info('Configuration file check skipped')
        else:
            config_check_result = self.config_check(cfg)

            if not config_check_result[0] or config_check_result[1] or config_check_result[2]:
                self.write(cfg)

            log_message = "Config file "
            if config_check_result[0]:
                log_message += "is up-to-date"
            else:
                log_message += "was updated with new keys"

            if config_check_result[1]:
                log_message += " and deprecated keys were removed"

            self.__logger.info(log_message)

    @classmethod
    def create(cls):
        """ Create config file with default values. """
        cls.write(DEF_CFG)
        cls.__logger.info("Config file was generated.")

    @classmethod
    def write(cls, config_dict: dict):
        """ Rewrite configuration file with new values.

        Args:
            config_dict (dict): Dictionary with new config values.
        """
        with open(PATH_CFG, 'wt') as f:
            json.dump(config_dict, f, indent=4)
        cls.__logger.debug("Successful write request to configuration file")

    @classmethod
    def get(cls) -> dict:
        """ Get json configuration file values.

        If config file wasn't changed from last read - get values from variable,
        Else - Read values from modified file.

        Returns:
            dict: Parsed configuration json file.
        """
        if cls.is_modified():
            with open(PATH_CFG, 'rt') as f:
                cls.__config = json.load(f)
            cls.__last_mod_time = os.path.getmtime(PATH_CFG)

        return cls.__config

    @classmethod
    def is_modified(cls) -> bool:
        """ Check if config file was modified from the last load.

        Returns:
            bool:
                True - On first config request and if file was modified.
                False - File is is up-to-date with loaded values.
        """
        if cls.__last_mod_time is None:
            return True
        else:
            cfg_modtime = os.path.getmtime(PATH_CFG)
            return cfg_modtime > cls.__last_mod_time

    @staticmethod
    def is_exist() -> bool:
        """ Check configuration file existence.

        Returns:
            bool:
                True - Config file exists.
                False - Config file doesn't exist.
        """
        return True if os.path.isfile(PATH_CFG) else False

    @classmethod
    def config_check(cls, config: dict) -> tuple:
        """ Configuration file recursive check system

        Args:
            config (dict): Parsed configuration file that will be modified

        Returns:
            tuple: (
                bool,  # up to date
                bool,  # has deprecated keys
                bool   # was merged to newer version
            )
        """
        def special_update_check() -> bool:
            """ Non-automatic config updater for correct merge between major config file updates

            Returns:
                bool: Was config file updated
            """
            is_updated = False

            if "config_version" not in config:
                # Update config dict to version 2
                # First version of config file doesn't have key 'config_version'
                config.update({
                    "bot": {
                        "token": config.get("api_key", ""),
                        "whitelisted_users": config.get("whitelisted_users", []),
                        "state_notifications": config.get("state_notifications", DEF_CFG["bot"]["state_notifications"]),
                        "enable_file_transfer": config.get("enable_file_transfer", DEF_CFG["bot"]["enable_file_transfer"])
                    }
                })
                is_updated = True
                cls.__logger.info("Successfully merged config file to version 2")

            return is_updated

        def add_new_keys(default_config=DEF_CFG, user_config=config) -> bool:
            up_to_date = True

            for k, v in list(default_config.items()):
                if type(v) == dict:
                    if k not in user_config:
                        user_config[k] = v
                        up_to_date = False
                    else:
                        up_to_date = add_new_keys(v, user_config[k])
                elif k not in user_config:
                    up_to_date = False
                    user_config.update({k: v})
                    cls.__logger.debug(f"Adding new key '{k}' to user configuration file")

            return up_to_date

        def remove_deprecated(default_config=DEF_CFG, user_config=config) -> bool:
            has_deprecated_values = False

            for k, v in list(user_config.items()):
                if type(v) == dict:
                    has_deprecated_values = remove_deprecated(default_config[k], v)
                elif k not in default_config:
                    has_deprecated_values = True
                    del(user_config[k])
                    cls.__logger.debug(f"Removing deprecated key '{k}' from user configuration file")

            return has_deprecated_values

        # Prepare output in right order
        special_check = special_update_check()
        any_deprecated = remove_deprecated()
        any_new = add_new_keys()

        return (
            any_new,
            any_deprecated,
            special_check
        )
