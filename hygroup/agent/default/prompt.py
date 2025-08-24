from typing import Callable, Sequence

from hygroup.agent.base import AgentRequest, Message, Thread

INPUT_TEMPLATE = """<input>
<query sender="{sender}" receiver="{receiver}">
{query}
</query>
<context>{updates}{threads}
</context>
</input>"""

MESSAGE_TEMPLATE = """<message sender="{sender}" receiver="{receiver}">
{text}{threads}
</message>"""

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
    formatted_updates = ""

    if updates:
        formatted_updates = "\n".join(format_message(msg) for msg in updates)
        formatted_updates = UPDATES_TEMPLATE.format(updates=formatted_updates)
    else:
        formatted_updates = ""

    return INPUT_TEMPLATE.format(
        query=request.query,
        sender=request.sender,
        receiver=request.receiver or "",
        threads=format_threads(request.threads),
        updates=formatted_updates,
    )


def format_message(message: Message) -> str:
    return MESSAGE_TEMPLATE.format(
        text=message.text,
        sender=message.sender,
        receiver=message.receiver or "",
        threads=format_threads(message.threads),
    )


def format_thread(thread: Thread) -> str:
    formatted_messages = "\n".join(format_message(message) for message in thread.messages)
    return THREAD_TEMPLATE.format(thread_id=thread.session_id, messages=formatted_messages)


def format_threads(threads: Sequence[Thread]) -> str:
    if threads:
        return THREADS_TEMPLATE.format(threads="\n".join(format_thread(thread) for thread in threads))
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
    request = AgentRequest(query="What's the weather?", sender="user1", receiver="agent1", threads=threads)
    updates = [
        Message(sender="user1", receiver="agent1", text="Hello", threads=threads),
        Message(sender="agent1", receiver="user1", text="Hi there!"),
    ]

    result = format_input(request, updates=updates)
    print(result)


if __name__ == "__main__":
    example()
