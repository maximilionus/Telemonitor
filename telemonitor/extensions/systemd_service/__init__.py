from sys import platform
from logging import getLogger
from os import path, remove

from telemonitor.helpers import TM_Config, DEF_CFG


__version = 1
__logger = getLogger(__name__)

# All relative paths are starting from root directory of module `telemonitor`,
# Not from this directory!
__service_config_template_path = './extensions/systemd_service/files/telemonitor-bot-template.service'
__shell_launch_script_path = './extensions/systemd_service/files/telemonitor_start.sh'
__service_config_final_path = '/lib/systemd/system/telemonitor-bot.service'


def cli(mode: str):
    if platform == 'linux':
        if mode == 'install':
            if service_install():
                print("Successfully installed Telemonitor systemd service to your linux system!",
                      f"\nName of the service is: {path.basename(__service_config_final_path)}",
                      "\n\nNow the only thing you need to do is to run command to detect new service:",
                      "\n\tsystemctl daemon-reload",
                      "\n\nAnd now you can manually control this service with:",
                      f"\n\tsystemctl status {path.basename(__service_config_final_path)}  # View Telemonitor logs and current status",
                      f"\n\tsystemctl start {path.basename(__service_config_final_path)}   # Start the Telemonitor service",
                      f"\n\tsystemctl stop {path.basename(__service_config_final_path)}    # Stop the Telemonitor service"
                      f"\n\tsystemctl enable {path.basename(__service_config_final_path)}  # Start Telemonitor service on system launch"
                      f"\n\tsystemctl disable {path.basename(__service_config_final_path)} # Disable Telemonitor service automatic startup",
                      "\n\nPlease note, that the commands above will require root user privileges to run."
                      )
            else:
                print("Telemonitor systemd service is already installed on this system")

        elif mode == 'upgrade':
            service_upgrade()

        elif mode == 'remove':
            if service_remove():
                print("Successfully removed service from system")
            else:
                print("Systemd service configuration file doesn't exist, nothing to remove")

        elif mode == 'status':
            cfg_service = TM_Config.get()['systemd_service']
            service_exists = __systemd_config_exists()
            text = f"Telemonitor Systemd Service - Status\
                     \n\n- Is installed: {service_exists}"

            if service_exists:
                text += f"\n- Version: {cfg_service['version']}\
                          \n- Installation path: {__service_config_final_path}"
            print(text)

    else:
        print(f"This feature is available only for linux platforms with systemd support.\nYour platform is {platform}.")
        __logger.error(f"Requested feature is available only on 'linux' platforms with systemd support. Your platform is {platform}")

    exit()


def service_install() -> bool:
    """ Install systemd service

    Returns:
        bool: Was service installed
    """
    __logger.info("Begin systemd service installation")
    result = False

    if not __systemd_config_exists():
        try:
            template_service_file = open(__service_config_template_path, 'rt')
            final_service_file = open(__service_config_final_path, 'wt')

            text = template_service_file.read()
            text = text.replace('<SHELL_SCRIPT_PATH>', path.abspath(__shell_launch_script_path))

            final_service_file.write(text)
        except Exception as e:
            e_text = f"Can't write systemd service config file to {__service_config_final_path} due to {str(e)}"
            print(e_text + '\n')
            __logger.error(e_text)
        else:
            __update_cfg_values('install')
            __logger.info("Systemd service was successfully installed on system.")
            result = True
        finally:
            template_service_file.close()
            final_service_file.close()

    else:
        __logger.error(f"Service file already exists in '{__service_config_final_path}'")

    return result


def service_upgrade() -> bool:
    """ Check systemd service config files and upgrade them to newer version if available

    Returns:
        bool: Was service updated
    """
    was_updated = False
    __logger.info("Begin systemd service upgrade check")

    if __systemd_config_exists():
        config = TM_Config.get()

        builtin_version = __version
        installed_version = config["systemd_service"]["version"]

        if installed_version < builtin_version:
            choice = input(f"Service file can be upgraded to version '{builtin_version}' (Current version: '{installed_version}'). Upgrade? [y/n]: ")
            if choice[0].lower() == 'y':
                print(f"\n- Removing installed version '{installed_version}' service from system...")
                if service_remove():
                    print(
                        "- Installed version of service was removed",
                        f"\n- Installing the systemd service version '{builtin_version}' to system..."
                    )
                    if service_install():
                        print("- Successfully installed new systemd service")
                        __update_cfg_values('upgrade')
                        print(f"\nService was successfully upgraded from version '{installed_version}' to '{builtin_version}'")
                        was_updated = True
    else:
        text = "Service is not installed, nothing to upgrade"
        __logger.info(text)
        print(text)

    return was_updated


def service_remove() -> bool:
    """ Remove all systemd service files, generated by Telemonitor, from system

    Returns:
        bool:
            True - Successfully removed service from system
            False - Can't remove service
    """
    __logger.info("Begin systemd service removal")
    result = False

    if __systemd_config_exists():
        try:
            remove(__service_config_final_path)
        except Exception as e:
            text = f"Can't remove systemd service file in {__service_config_final_path} due to {str(e)}"
            print(text)
            __logger.error(text)
        else:
            __update_cfg_values('remove')
            __logger.info(f"Successfully removed service file on path {__service_config_final_path}")
            result = True
    else:
        __logger.error("Systemd service configuration file doesn't exist, nothing to remove")

    return result


def __systemd_config_exists() -> bool:
    """ Check for systemd config existence

    Returns:
        bool:
            True - Config exists
            False - Can't find any config file
    """
    return path.isfile(__service_config_final_path)


def __update_cfg_values(mode: str):
    """ Update config values related to systemd service

    Args:
        mode (str): [
            'install' - Set config values to fresh install version.
            'upgrade' - Upgrade value of `version` key in config.
            'remove' - Reset `systemd_service` dict to default values.
        ]
    """
    options = ('install', 'upgrade', 'remove')
    if mode not in options:
        raise Exception(f"Option '{mode}' doesn't exist in this function")

    cfg = TM_Config.get()

    if mode == 'install':
        cfg['systemd_service'] = {
            "version": __version
        }
    elif mode == 'upgrade':
        cfg['systemd_service']["version"] = __version
    elif mode == 'remove':
        cfg['systemd_service'] = DEF_CFG['systemd_service']

    TM_Config.write(cfg)
    __logger.debug(f"Updated configuration dict 'systemd_service' to mode '{mode}'")
