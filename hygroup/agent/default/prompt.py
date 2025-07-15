from typing import Callable, Sequence

from hygroup.agent.base import AgentRequest, Message, Thread

QUERY_TEMPLATE = """You are the receiver of the following query:

<query sender="{sender}" receiver="{receiver}">
{query}{threads}
</query>

Please respond to this query."""

MESSAGE_TEMPLATE = """<message sender="{sender}" receiver="{receiver}">
{text}{threads}
</message>"""

THREADS_TEMPLATE = """
<referenced-threads>
{threads}
</referenced-threads>"""

UPDATES_TEMPLATE = """ You may use the following messages, enclosed in <updates> tags, as context:

<updates>
{messages}
</updates>"""

THREAD_TEMPLATE = """<thread id="{thread_id}">
{messages}
</thread>"""

TEMPLATE = """{formatted_query}{updates}"""


InputFormatter = Callable[[AgentRequest, str, Sequence[Message]], str]


def format_input(
    request: AgentRequest,
    receiver: str,
    updates: Sequence[Message],
) -> str:
    formatted_query = format_query(request, receiver)
    formatted_updates = ""

    if updates:
        formatted_messages = "\n".join(format_message(msg) for msg in updates)
        formatted_updates = UPDATES_TEMPLATE.format(messages=formatted_messages)

    return TEMPLATE.format(formatted_query=formatted_query, updates=formatted_updates)


def format_query(request: AgentRequest, receiver: str) -> str:
    return QUERY_TEMPLATE.format(
        query=request.query, sender=request.sender, receiver=receiver, threads=format_threads(request.threads)
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
    request = AgentRequest(query="What's the weather?", sender="user1", threads=threads)
    updates = [
        Message(sender="user1", receiver="agent1", text="Hello", threads=threads),
        Message(sender="agent1", receiver="user1", text="Hi there!"),
    ]

    result = format_input(request, "agent1", updates=updates)
    print(result)


if __name__ == "__main__":
    example()
