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
        print(f"\n🌐 Opening browser to: {url}")
        webbrowser.open(url)

    timer = Timer(delay, _open)
    timer.daemon = True
    timer.start()


def main():
    parser = argparse.ArgumentParser(description="App Registration")
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
        default=PROJECT_ROOT_PATH.parent / ".secrets/github-apps",
        help=f"Folder to store GitHub App private keys (default: {PROJECT_ROOT_PATH.parent / '.secrets/github-apps'}",
    )

    args = parser.parse_args()

    port = args.port if args.port else find_available_port()

    private_key_folder = Path(args.key_folder)
    if not private_key_folder.is_absolute():
        private_key_folder = PROJECT_ROOT_PATH.parent / private_key_folder

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
        host=args.host,
        port=port,
        credential_manager=credential_manager,
    )

    app_path = f"/{args.app_type}-app"
    url = f"http://{args.host}:{port}{app_path}"

    print(f"🚀 Starting {args.app_type.capitalize()} App Registration server")
    print(f"📍 Host: {args.host}")
    print(f"🔌 Port: {port}")
    print(f"🔗 URL: {url}")
    print("\n✨ Server starting...\n")

    open_browser(url)

    uvicorn.run(
        app,
        host=args.host,
        port=port,
        log_level="info",
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
