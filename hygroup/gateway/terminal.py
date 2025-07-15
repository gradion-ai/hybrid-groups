import asyncio
import json
import os
import sys
import termios
import tty
from contextlib import contextmanager

import uvicorn
import websockets
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.rule import Rule
from rich.text import Text

from hygroup.agent import AgentRequest, AgentResponse, Message
from hygroup.gateway import Gateway
from hygroup.gateway.utils import extract_initial_mention, resolve_mentions
from hygroup.session import Session, SessionManager
from hygroup.user import UserNotAuthenticatedError


class TerminalGateway(Gateway):
    def __init__(
        self,
        session_manager: SessionManager,
        session_id: str | None = None,
        host: str = "0.0.0.0",
        port: int = 8723,
    ):
        self._session_manager = session_manager
        self._session_id = session_id
        self._session: Session

        self.host = host
        self.port = port

        self._connections: dict[str, WebSocket] = {}

        self._server: uvicorn.Server | None = None
        self._task: asyncio.Task | None = None

        self._app = FastAPI()
        self._app.websocket("/ws/{username}")(self.connect)

    async def start(self, join: bool = True):
        session = None

        if self._session_id:
            session = await self._session_manager.load_session(id=self._session_id)

        if session is None:
            session = self._session_manager.create_session(self._session_id)

        self._session = session
        self._session.set_gateway(self)
        self._session.sync()

        config = uvicorn.Config(self._app, host=self.host, port=self.port)

        self._server = uvicorn.Server(config)
        self._task = asyncio.create_task(self._server.serve())
        if join:
            await self._task

    async def stop(self):
        if self._server:
            self._server.should_exit = True
            self._server = None
        if self._task:
            await self._task
            self._task = None

    async def connect(self, websocket: WebSocket, username: str):
        """Handle a new WebSocket connection."""
        await websocket.accept()

        try:
            # Wait for login message
            data = await websocket.receive_json()

            if data.get("type") != "login":
                await websocket.send_json(
                    {"type": "login_response", "success": False, "message": "First message must be login"}
                )
                await websocket.close()
                return

            if not self._session.user_registry.authenticate(username, password=data.get("password", "")):
                await websocket.send_json(
                    {"type": "login_response", "success": False, "message": "Authentication failed"}
                )
                await websocket.close()
                return

            # Check if user already has a connection
            if username in self._connections:
                await websocket.send_json(
                    {"type": "login_response", "success": False, "message": "User already connected"}
                )
                await websocket.close()
                return

            # Store connection
            self._connections[username] = websocket

            # Send success response
            await websocket.send_json(
                {"type": "login_response", "success": True, "message": "Authenticated successfully"}
            )

            # Handle incoming messages
            while True:
                data = await websocket.receive_json()
                await self._handle_client_message(data, username)

        except WebSocketDisconnect:
            # Clean up on disconnect
            if username in self._connections:
                del self._connections[username]
        except Exception:
            # Clean up on any error
            if username in self._connections:
                del self._connections[username]
            raise

    async def _handle_client_message(self, data: dict, username: str):
        if data.get("type") == "chat_message":
            content = data.get("content", "")
            await self.handle_client_message(content, username)

    async def handle_client_message(self, content: str, sender: str):
        receiver, text = extract_initial_mention(content)

        # replace all @mentions with mentions (i.e. remove @)
        text = resolve_mentions(text, lambda x: x)

        if receiver in await self._session.agent_names():
            await self._session.invoke(
                request=AgentRequest(
                    query=text,
                    sender=sender,
                ),
                receiver=receiver,
            )
        else:
            await self._session.update(
                Message(
                    text=text,
                    sender=sender,
                    receiver=receiver,
                )
            )

        await self.send_message(content, sender, agent=False)

    async def handle_agent_response(self, response: AgentResponse, sender: str, receiver: str, session_id: str):
        content = response.text

        if response.handoffs:
            content += "\n\nHandoffs:"
            for agent, query in response.handoffs.items():
                content += f"\n@{agent}: {query}"

        content = f"@{receiver} {content}"
        await self.send_message(content, sender, agent=True)

    async def send_message(self, content: str, sender: str, agent: bool = False):
        message = {
            "type": "chat_message",
            "content": content,
            "sender": sender,
            "agent": agent,
        }

        # Broadcast to all connected clients
        disconnected = []
        for username, websocket in self._connections.items():
            try:
                await websocket.send_json(message)
            except Exception:
                # Mark for removal if send fails
                disconnected.append(username)

        # Remove disconnected clients
        for username in disconnected:
            del self._connections[username]


class TerminalClient:
    def __init__(self, host: str = "localhost", port: int = 8723, **terminal_kwargs):
        self.host = host
        self.port = port

        self._username: str | None = None
        self._websocket: WebSocket | None = None

        self._terminal_interface: TerminalInterface | None = None
        self._terminal_kwargs = terminal_kwargs

        self._receiver_task: asyncio.Task | None = None
        self._terminal_task: asyncio.Task | None = None

    @property
    def username(self) -> str:
        if self._username is None:
            raise UserNotAuthenticatedError("Not authenticated")
        return self._username

    async def join(self):
        if self._terminal_task is None:
            raise UserNotAuthenticatedError("Not authenticated")
        await self._terminal_task

    async def authenticate(self, username: str, password: str):
        try:
            # Create WebSocket connection
            self._websocket = await websockets.connect(f"ws://{self.host}:{self.port}/ws/{username}")

            # Send login message
            await self._websocket.send(json.dumps({"type": "login", "username": username, "password": password}))

            # Wait for login response
            response = await self._websocket.recv()
            data = json.loads(response)

            if data.get("type") == "login_response" and data.get("success"):
                self._username = username
                print(f"User {username} authenticated.")

                # Start terminal
                self._terminal_task = asyncio.create_task(self._start_interface())

                # Start message receiver loop
                self._receiver_task = asyncio.create_task(self._receive_messages())

                return True
            else:
                await self._websocket.close()
                print(f"Login failed: {data.get('message', 'Unknown error')}")
                return False

        except Exception as e:
            print(f"Connection failed: {e}")
            return False

    async def _start_interface(self):
        self._terminal_interface = TerminalInterface(self, **self._terminal_kwargs)
        await self._terminal_interface.run()

    async def _receive_messages(self):
        """Continuously receive messages from WebSocket."""
        try:
            while self._websocket:
                data = await self._websocket.recv()
                message = json.loads(data)

                if message.get("type") == "chat_message":
                    content = message.get("content", "")
                    sender = message.get("sender", "unknown")
                    agent = message.get("agent", False)
                    self.handle_message(content, sender, agent)

        except websockets.exceptions.ConnectionClosed:
            print("Connection closed by server")
            if self._terminal_interface:
                self._terminal_interface.shutdown()
        except Exception as e:
            print(f"Error receiving messages: {e}")

    def handle_message(self, content: str, sender: str, agent: bool):
        if self._terminal_interface is not None:
            self._terminal_interface.add_chat_message(content, sender, agent)

    async def send_message(self, content: str):
        if self._websocket and self._username:
            message = {"type": "chat_message", "content": content}
            await self._websocket.send(json.dumps(message))
        else:
            print("Not connected to server")
            pass


class TerminalInterface:
    def __init__(
        self,
        client: TerminalClient,
        user_color: str = "orange1",
        agent_color: str = "green",
        human_color: str = "cyan",
        input_color: str = "orange1",
        rule_color: str = "grey23",
    ):
        self._client = client
        self._user_color = user_color
        self._agent_color = agent_color
        self._human_color = human_color
        self._input_color = input_color
        self._rule_color = rule_color
        self._console = Console()

        self._live: Live = None
        self._input_buffer = ""
        self._cursor_pos = 0
        self._pending: list[tuple[str, str, bool]] = []
        self._shutdown: asyncio.Event = asyncio.Event()

    def add_chat_message(self, message: str, sender: str, agent: bool = False):
        if self._live is None:
            # Live not started yet; queue message
            self._pending.append((message, sender, agent))
            return

        if sender == self._client.username:
            sender_color = self._user_color
        elif agent:
            sender_color = self._agent_color
        else:
            sender_color = self._human_color

        self._live.console.print(Rule(style=self._rule_color))
        self._live.console.print(f"[bold {sender_color}]{sender}[/]: {message}", highlight=False)

    async def run(self):
        with self._raw_mode():
            with Live(
                self._input_panel(),
                console=self._console,
                screen=False,
                auto_refresh=False,
            ) as live:
                self._live = live

                # Flush any pending messages
                for message, sender, agent in self._pending:
                    self.add_chat_message(message, sender, agent)
                self._pending.clear()

                # Keep live display active until shutdown is requested
                while not self._shutdown.is_set():
                    await asyncio.sleep(0.1)

    def shutdown(self):
        self._shutdown.set()

    @contextmanager
    def _raw_mode(self):
        """Context manager that configures terminal in cbreak mode without echo
        and registers the stdin reader callback. Restores settings on exit."""
        loop = asyncio.get_running_loop()
        fd = sys.stdin.fileno()
        old_attrs = termios.tcgetattr(fd)
        try:
            tty.setcbreak(fd)
            new_attrs = termios.tcgetattr(fd).copy()
            new_attrs[3] &= ~termios.ECHO  # disable echo
            termios.tcsetattr(fd, termios.TCSANOW, new_attrs)
            loop.add_reader(fd, self._on_key)
            yield
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_attrs)
            loop.remove_reader(fd)

    def _on_key(self):
        """Handle key presses, cursor moves, and pasted input.

        Reads every available byte from stdin in one shot so that large
        pastes are processed immediately instead of character-by-character
        across multiple event-loop iterations.
        """

        # ----------------------------------------------------------------------------
        #  TODO: replace with a more elaborate solution using an appropriate library
        # ----------------------------------------------------------------------------

        fd = sys.stdin.fileno()
        # `add_reader` guarantees the FD is ready, so this read is non-blocking.
        data = os.read(fd, 4096).decode(errors="ignore")
        if not data:
            return

        updated = False  # Track whether the input panel needs to be refreshed
        i = 0
        length = len(data)

        while i < length:
            ch = data[i]

            # Handle newline / return (submit input)
            if ch in ("\r", "\n"):
                if self._input_buffer:
                    asyncio.create_task(self._on_enter())
                i += 1
                continue

            # Handle backspace
            if ch in ("\x7f", "\b"):
                if self._cursor_pos > 0:
                    self._input_buffer = (
                        self._input_buffer[: self._cursor_pos - 1] + self._input_buffer[self._cursor_pos :]
                    )
                    self._cursor_pos -= 1
                    updated = True
                i += 1
                continue

            # Handle simple ANSI cursor esc sequences (arrow keys)
            if ch == "\x1b" and i + 2 < length and data[i + 1] == "[":
                direction = data[i + 2]
                if direction == "C":  # Right arrow
                    if self._cursor_pos < len(self._input_buffer):
                        self._cursor_pos += 1
                        updated = True
                elif direction == "D":  # Left arrow
                    if self._cursor_pos > 0:
                        self._cursor_pos -= 1
                        updated = True
                # Skip the full escape sequence (ESC [ X)
                i += 3
                continue

            # Default: printable character – insert at cursor
            self._input_buffer = self._input_buffer[: self._cursor_pos] + ch + self._input_buffer[self._cursor_pos :]
            self._cursor_pos += 1
            updated = True
            i += 1

        # Refresh display once per batch to avoid excessive updates
        if updated and self._live is not None:
            self._live.update(self._input_panel(), refresh=True)

    async def _on_enter(self):
        _input = self._input_buffer.strip()
        self._input_buffer = ""
        self._cursor_pos = 0
        self._live.update(self._input_panel(), refresh=True)

        if _input == "/exit":
            self.shutdown()
        else:
            await self._client.send_message(_input)

    def _input_panel(self) -> Panel:
        cursor = Text("█", style="bold")
        txt = Text()

        # Add text before cursor
        if self._cursor_pos > 0:
            txt.append(self._input_buffer[: self._cursor_pos])

        # Add cursor
        txt.append(cursor)

        # Add text after cursor
        if self._cursor_pos < len(self._input_buffer):
            txt.append(self._input_buffer[self._cursor_pos :])

        return Panel(txt, title="Input", border_style=self._input_color)
