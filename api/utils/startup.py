import os
import sys
from typing import Dict, Any
from datetime import datetime
from colorama import Fore, Style, init

init(autoreset=True)


def print_startup_banner(config: Any) -> None:
    """Print a friendly startup banner"""
    print(f"\n{Fore.CYAN}{'=' * 66}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}                      Doc Sync API{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}                    Version: {config.APP_VERSION}{Style.RESET_ALL}")
    print(f"{Fore.GREEN}                 Environment: {config.ENV}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}{'=' * 66}{Style.RESET_ALL}\n")
    
    print(f"{Fore.CYAN}[STARTUP] Server Configuration:{Style.RESET_ALL}")
    print(f"   Host: {Fore.GREEN}{config.HOST}{Style.RESET_ALL}")
    print(f"   Port: {Fore.GREEN}{config.PORT}{Style.RESET_ALL}")
    print(f"   Debug: {Fore.YELLOW if config.DEBUG else Fore.GREEN}{'Enabled' if config.DEBUG else 'Disabled'}{Style.RESET_ALL}")
    print(f"   URL: {Fore.BLUE}http://{config.HOST}:{config.PORT}{Style.RESET_ALL}\n")
    
    print(f"{Fore.MAGENTA}Ready to process your documents!{Style.RESET_ALL}")
    print(f"{'-' * 66}\n")


def print_shutdown_message() -> None:
    """Print a friendly shutdown message"""
    print(f"\n{Fore.YELLOW}{'-' * 66}{Style.RESET_ALL}")
    print(f"{Fore.RED}[SHUTDOWN] Shutting down server...{Style.RESET_ALL}")
    print(f"   Thank you for using Doc Sync API!")
    print(f"{Fore.YELLOW}{'-' * 66}{Style.RESET_ALL}\n")


def suppress_werkzeug_startup() -> None:
    """Suppress default Werkzeug startup messages"""
    import logging
    
    werkzeug_logger = logging.getLogger('werkzeug')
    werkzeug_logger.setLevel(logging.ERROR)
    
    # CKDEV-NOTE: Also suppress default Flask startup messages
    cli = sys.modules.get('flask.cli')
    if cli:
        cli.show_server_banner = lambda *x: None


class StartupLogger:
    """Friendly logger for startup messages"""
    
    @staticmethod
    def info(message: str) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"{Fore.CYAN}[{timestamp}] [INFO]{Style.RESET_ALL}    {message}")
    
    @staticmethod
    def success(message: str) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"{Fore.GREEN}[{timestamp}] [SUCCESS]{Style.RESET_ALL} {message}")
    
    @staticmethod
    def warning(message: str) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"{Fore.YELLOW}[{timestamp}] [WARNING]{Style.RESET_ALL} {message}")
    
    @staticmethod
    def error(message: str) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"{Fore.RED}[{timestamp}] [ERROR]{Style.RESET_ALL}   {message}")