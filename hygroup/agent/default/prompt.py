from typing import Callable, Sequence

from hygroup.agent.base import AgentRequest, Attachment, Message, Thread

INPUT_TEMPLATE = """<input>
<query sender="{sender}" receiver="{receiver}">
{query}{attachments}
</query>
<context>{updates}{threads}
</context>
</input>"""

MESSAGE_TEMPLATE = """<message sender="{sender}" receiver="{receiver}">
{text}{attachments}{threads}
</message>"""

ATTACHMENT_TEMPLATE = """<attachment name="{name}" media_type="{media_type}">
{path}
</attachment>"""

ATTACHMENTS_TEMPLATE = """
<attachments>
{attachments}
</attachments>"""

UPDATES_TEMPLATE = """
<updates>
{updates}
</updates>"""

THREAD_TEMPLATE = """<thread id="{thread_id}">
{messages}
</thread>"""

THREADS_TEMPLATE = """
<threads>
{threads}
</threads>"""


InputFormatter = Callable[[AgentRequest, Sequence[Message]], str]


def format_input(
    request: AgentRequest,
    updates: Sequence[Message],
) -> str:
    return INPUT_TEMPLATE.format(
        query=request.query,
        sender=request.sender,
        receiver=request.receiver or "",
        threads=format_threads(request.threads),
        updates=format_updates(updates),
        attachments=format_attachments(request.attachments),
    )


def format_message(message: Message) -> str:
    return MESSAGE_TEMPLATE.format(
        text=message.text,
        sender=message.sender,
        receiver=message.receiver or "",
        threads=format_threads(message.threads),
        attachments=format_attachments(message.attachments),
    )


def format_thread(thread: Thread) -> str:
    formatted_messages = "\n".join(format_message(message) for message in thread.messages)
    return THREAD_TEMPLATE.format(thread_id=thread.session_id, messages=formatted_messages)


def format_threads(threads: Sequence[Thread]) -> str:
    if threads:
        return THREADS_TEMPLATE.format(threads="\n".join(format_thread(thread) for thread in threads))
    return ""


def format_attachment(attachment: Attachment) -> str:
    return ATTACHMENT_TEMPLATE.format(
        name=attachment.name,
        media_type=attachment.media_type,
        path=attachment.path,
    )


def format_attachments(attachments: Sequence[Attachment]) -> str:
    if attachments:
        return ATTACHMENTS_TEMPLATE.format(
            attachments="\n".join(format_attachment(attachment) for attachment in attachments)
        )
    return ""


def format_updates(updates: Sequence[Message]) -> str:
    if updates:
        return UPDATES_TEMPLATE.format(updates="\n".join(format_message(msg) for msg in updates))
    return ""


def example():
    threads = [
        Thread(
            session_id="thread1",
            messages=[
                Message(sender="user2", receiver="agent1", text="Can you help me?"),
                Message(sender="agent1", receiver=None, text="Of course!"),
            ],
        )
    ]
    attachments = [
        Attachment(path="/path/to/image.png", name="image.png", media_type="image/png"),
        Attachment(path="/path/to/doc.pdf", name="document.pdf", media_type="application/pdf"),
    ]
    request = AgentRequest(
        query="What's the weather?", sender="user1", receiver="agent1", threads=threads, attachments=attachments
    )
    updates = [
        Message(
            sender="user1",
            receiver="agent1",
            text="Hello",
            threads=threads,
            attachments=[Attachment(path="/path/to/file.txt", name="file.txt", media_type="text/plain")],
        ),
        Message(sender="agent1", receiver="user1", text="Hi there!"),
    ]

    result = format_input(request, updates=updates)
    print(result)


if __name__ == "__main__":
    example()
