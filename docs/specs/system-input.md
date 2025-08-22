## Input Query Structure

The system agent input is provided in an XML-like format. It describes a query from a user to an agent, along with relevant contextual information.

### Root Element: `<query>`

The main container is the `<query>` element.

```xml
<query sender="sender_id" receiver="receiver_id">
    The user's direct query text.
    {threads}
    {updates}
</query>
```

-   **Attributes**:
    -   `sender`: The name of the sender of the query.
    -   `receiver`: The name of the receiver of the query. Is "" if not defined.
-   **Content**:
    -   The raw text of the user's query.
    -   An optional `<threads>` section.
    -   An optional `<updates>` section.

---

### Contextual Information: `<threads>` and `<updates>`

These optional sections provide context for the query.

-   **`<threads>`**: Contains one or more `<thread>` elements. This section is used to provide the messages contained in other referenced group chats (= threads).
-   **`<updates>`**: Contains one or more `<message>` elements. This section provides recent group chat messages that were not sent as query messages to the system agent. This are request and response messages between users and non-system agents where the non-system agents are the direct receivers of the messages, bypassing the system agent.

Both `<threads>` and `<updates>` are optional.

---

### The Recursive Structure: `<thread>` and `<message>`

An external group chat is referenced as `<thread>` element containing the group chat's `<message>` elements.

-   **`<thread>`**: Represents a single external group chat.
    -   **Attribute**: `id` (a unique identifier for the thread i.e. group session id).
    -   **Content**: Contains one or more `<message>` elements that form the thread.

-   **`<message>`**: Represents a single message within a thread, or within an updates element.
    -   **Attributes**:
        -   `sender`: The name of the message sender.
        -   `receiver`: The name of the message receiver (can be "").
    -   **Content**:
        -   The text content of the message.
        -   An optional `<threads>` element.

**Recursion**: A `<message>` can itself contain a `<threads>` block. This allows for complex, nested group chat references.

---

### Example

Here is a full example demonstrating the structure:

```xml
<query sender="user1" receiver="agent1">
What's the weather?
<threads>
  <thread id="thread1">
    <message sender="user2" receiver="agent1">
      Can you help me?
    </message>
    <message sender="agent1" receiver="">
      Of course!
    </message>
  </thread>
</threads>
<updates>
  <message sender="user1" receiver="agent1">
    Hello
    <threads>
      <thread id="thread1">
        <message sender="user2" receiver="agent1">
          Can you help me?
        </message>
        <message sender="agent1" receiver="">
          Of course!
        </message>
      </thread>
    </threads>
  </message>
  <message sender="agent1" receiver="user1">
    Hi there!
  </message>
</updates>
</query>
```

Important: The example uses an indent=2 for readability but real messages sent to the system agent will have indent=0.
