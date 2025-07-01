from typing import Callable, Sequence

from hygroup.agent.base import AgentRequest, Message, Thread

QUERY_TEMPLATE = """You are the receiver of the following query:

<query sender="{sender}" receiver="{receiver}">
{query}
</query>

Please respond to this query."""


MESSAGE_TEMPLATE = """<message sender="{sender}" receiver="{receiver}">
{text}
</message>"""


UPDATES_TEMPLATE = """

New messages between others in the current thread:

<updates>
{messages}
</updates>"""

THREAD_TEMPLATE = """<thread id="{thread_id}">
{messages}
</thread>"""

THREADS_TEMPLATE = """

Messages in other threads:

<threads>
{threads}
</threads>"""


TEMPLATE = """{formatted_query} You may use the following messages as context:

<context>{updates}{threads}
</context>"""


InputFormatter = Callable[[AgentRequest, str, Sequence[Message], Sequence[Thread]], str]


def format_input(
    request: AgentRequest,
    receiver: str,
    updates: Sequence[Message],
    threads: Sequence[Thread],
) -> str:
    formatted_query = QUERY_TEMPLATE.format(query=request.query, sender=request.sender, receiver=receiver)

    formatted_updates = ""
    if updates:
        formatted_messages = "\n".join(format_message(msg) for msg in updates)
        formatted_updates = UPDATES_TEMPLATE.format(messages=formatted_messages)

    formatted_threads = ""
    if threads:
        formatted_thread_list = []
        for thread in threads:
            formatted_messages = "\n".join(format_message(msg) for msg in thread.messages)
            formatted_thread_list.append(
                THREAD_TEMPLATE.format(thread_id=thread.session_id, messages=formatted_messages)
            )
        formatted_threads = THREADS_TEMPLATE.format(threads="\n".join(formatted_thread_list))

    return TEMPLATE.format(formatted_query=formatted_query, updates=formatted_updates, threads=formatted_threads)


def format_message(message: Message) -> str:
    return MESSAGE_TEMPLATE.format(text=message.text, sender=message.sender, receiver=message.receiver or "")


def example():
    request = AgentRequest(query="What's the weather?", sender="user1")
    updates = [
        Message(sender="user1", receiver="agent1", text="Hello"),
        Message(sender="agent1", receiver="user1", text="Hi there!"),
    ]
    threads = [
        Thread(
            session_id="thread1",
            messages=[
                Message(sender="user2", receiver="agent1", text="Can you help me?"),
                Message(sender="agent1", receiver=None, text="Of course!"),
            ],
        )
    ]

    result = format_input(request, "agent1", updates=updates, threads=threads)
    print(result)


if __name__ == "__main__":
    example()
