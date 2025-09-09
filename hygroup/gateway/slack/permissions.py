from uuid import uuid4

from markdown_to_mrkdwn import SlackMarkdownConverter

from hygroup.agent import PermissionRequest
from hygroup.gateway.slack.context import SlackContext


class SlackPermissionHandler:
    def __init__(self, context: SlackContext):
        self.context = context
        self.converter = SlackMarkdownConverter()

        # Register action listeners
        self.context.app.action("once_button")(self._handle_permission_response)
        self.context.app.action("session_button")(self._handle_permission_response)
        self.context.app.action("always_button")(self._handle_permission_response)
        self.context.app.action("deny_button")(self._handle_permission_response)

    async def handle_permission_request(self, request: PermissionRequest, sender: str, receiver: str, thread_id: str):
        thread = self.context.threads[thread_id]
        corr_id = str(uuid4())

        thread.permission_requests[corr_id] = request

        text = f"*Execute action:*\n\n```\n{request.call}\n```\n\n"
        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": self.converter.convert(text),
                },
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Once"},
                        "action_id": "once_button",
                        "value": corr_id,
                        "style": "primary",
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Session"},
                        "action_id": "session_button",
                        "value": corr_id,
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Always"},
                        "action_id": "always_button",
                        "value": corr_id,
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Deny"},
                        "action_id": "deny_button",
                        "value": corr_id,
                        "style": "danger",
                    },
                ],
            },
        ]

        await self.context.send_slack_message(
            thread=thread,
            text=text,
            sender=sender,
            blocks=blocks,
            user=self.context.resolve_slack_user_id(receiver),
        )

    async def _handle_permission_response(self, ack, body):
        await ack()

        message = body.get("message") or body["container"]
        thread_id = message["thread_ts"]
        thread = self.context.threads.get(thread_id)

        if thread is None:
            return

        action = body["actions"][0]
        cid = action.get("value")

        if cid in thread.permission_requests:
            request = thread.permission_requests.pop(cid)
            match action["action_id"]:
                case "once_button":
                    request.grant_once()
                case "session_button":
                    request.grant_session()
                case "always_button":
                    request.grant_always()
                case "deny_button":
                    request.deny()
                case _:
                    raise ValueError(f"Unknown action: {action['action_id']}")
