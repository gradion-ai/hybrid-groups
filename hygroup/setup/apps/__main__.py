import argparse
import logging
import socket
import webbrowser
from pathlib import Path
from threading import Timer

import uvicorn

from hygroup import PROJECT_ROOT_PATH
from hygroup.setup.apps.app import create_app
from hygroup.setup.apps.credentials import CredentialManager


def find_available_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        s.listen(1)
        port = s.getsockname()[1]
    return port


def open_browser(url: str, delay: float = 1.5):
    def _open():
        webbrowser.open(url)

    timer = Timer(delay, _open)
    timer.daemon = True
    timer.start()


def main(
    app_type: str,
    host: str,
    port: int,
    key_folder: str,
    open_browser_flag: bool = True,
):
    private_key_folder = Path(key_folder)

    if not private_key_folder.exists():
        private_key_folder.mkdir(parents=True, exist_ok=True)

    env_file = PROJECT_ROOT_PATH.parent / ".env"
    if not env_file.exists():
        env_file.touch()

    credential_manager = CredentialManager(
        key_folder=private_key_folder,
        env_file=env_file,
    )
    app = create_app(
        host=host,
        port=port,
        credential_manager=credential_manager,
    )

    app_path = f"/{app_type}-app"
    url = f"http://{host}:{port}{app_path}"

    logging.info("")
    logging.info("⚙️  Application Setup")
    logging.info("")

    # Create centered box with URL
    box_width = 60
    header_text = "🌐 OPEN THIS URL IN YOUR BROWSER:"
    url_text = f"➜ {url}"

    logging.info("╔" + "═" * box_width + "╗")
    logging.info("║" + " " * box_width + "║")
    logging.info("║" + header_text.center(box_width - 1) + "║")
    logging.info("║" + " " * box_width + "║")
    logging.info("║" + url_text.center(box_width) + "║")
    logging.info("║" + " " * box_width + "║")
    logging.info("╚" + "═" * box_width + "╝")
    logging.info("")
    logging.info("⏳ Waiting for you to complete the setup in your browser...")
    logging.info("")

    if open_browser_flag:
        open_browser(url)

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        log_level="info",
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    parser = argparse.ArgumentParser(description="GitHub App Registration")
    parser.add_argument(
        "app_type",
        choices=["github", "slack"],
        help="Type of app to register (github or slack)",
    )
    parser.add_argument(
        "--host",
        type=str,
        default="localhost",
        help="Server host (default: localhost)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Server port (default: random available port)",
    )
    parser.add_argument(
        "--key-folder",
        type=str,
        default=".data/secrets/github-apps",
        help="Relative path to the folder to store GitHub App private keys (default: '.data/secrets/github-apps')",
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Don't open browser automatically",
    )

    args = parser.parse_args()

    main(
        app_type=args.app_type,
        host=args.host,
        port=args.port or find_available_port(),
        key_folder=args.key_folder,
        open_browser_flag=not args.no_browser,
    )
