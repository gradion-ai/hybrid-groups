## Overview

*Hybrid Groups* is a multi-user, multi-agent platform that enables teams to collaborate with proactive and reactive agents in Slack and GitHub. It adds background reasoning to Slack threads and GitHub issues to intelligently activate agents based on chat messages and context. 

<div class="image-row">
  <div class="image-item">
    <div class="image-zoom">
      <a href="/images/intro/intro-1.png" target="_blank"><img src="/images/intro/intro-1.png" class="thumbnail"></a>
      <a href="/images/intro/intro-1.png" target="_blank" class="large-link"><img src="/images/intro/intro-1.png" class="large"></a>
    </div>
    <p class="caption"><b>Figure 1:</b> A <i>Hybrid Groups</i> thread in Slack.</p>
  </div>
  <div class="image-item">
    <div class="image-zoom">
      <a href="/images/intro/intro-2.png" target="_blank"><img src="/images/intro/intro-2.png" class="thumbnail"></a>
      <a href="/images/intro/intro-2.png" target="_blank" class="large-link"><img src="/images/intro/intro-2.png" class="large"></a>
    </div>
    <p class="caption"><b>Figure 2:</b> The <i>Hybrid Groups</i> Slack app home view.</p>
  </div>
  <div class="image-item">
    <div class="image-zoom">
      <a href="/images/intro/intro-3.png" target="_blank"><img src="/images/intro/intro-3-crop.png" class="thumbnail"></a>
      <a href="/images/intro/intro-3.png" target="_blank" class="large-link"><img src="/images/intro/intro-3.png" class="large"></a>
    </div>
    <p class="caption"><b>Figure 3:</b> A <i>Hybrid Groups</i> thread in GitHub.</p>
  </div>
</div>

Agents reason, act and respond specific to a user's identity, preferences and history, and can take actions on behalf of a user. In Slack, users can build custom agents with a simple *agent builder*. More advanced agents or agentic systems can be integrated with the *Hybrid Groups* Python SDK.

## Features

| Feature | Example| Description |
|---|---|---|
| **Group sessions** | <div class="image-zoom"><a href="/images/features/feature-4.png" target="_blank"><img src="/images/features/feature-4.png" class="thumbnail"></a><a href="/images/features/feature-4.png" target="_blank" class="large-link"><img src="/images/features/feature-4.png" class="large"></a></div> | In *Hybrid Groups*, users and agents collaborate in *group sessions*. A group session corresponds to a [thread](https://slack.com/help/articles/115000769927-Use-threads-to-organize-discussions) in Slack or an [issue](https://docs.github.com/en/issues/tracking-your-work-with-issues/about-issues) in GitHub. Agents have the full context of their session, seeing all messages, senders, and receivers. Each session runs their own instances of agents and background reasoners to isolate them from other sessions. To include context from other sessions, *Hybrid Groups* supports session references, e.g. via issue references in GitHub issues.|
| **Background reasoning** | <div class="image-zoom"><a href="/images/features/feature-1.png" target="_blank"><img src="/images/features/feature-1.png" class="thumbnail"></a><a href="/images/features/feature-1.png" target="_blank" class="large-link"><img src="/images/features/feature-1.png" class="large"></a></div> | The system analyzes messages to determine if an agent could contribute to a conversation without being mentioned, allowing for proactive assistance. For example, if two users discuss a topic, a search agent may proactively provide context information. This process is guided by an *agent activation policy* ([example](selector.md)) and its status is indicated with emoji reactions on user messages: :eyes: reasoning started, :robot: agent activated, and :ballot_box_with_check: no further action. On GitHub, the corresponding emojis are :eyes: :rocket: and :+1:.|
| **Agent activation** | <div class="image-zoom"><a href="/images/features/feature-2.png" target="_blank"><img src="/images/features/feature-2.png" class="thumbnail"></a><a href="/images/features/feature-2.png" target="_blank" class="large-link"><img src="/images/features/feature-2.png" class="large"></a></div> | An agent can be activated either via background reasoning or by directly mentioning it at the beginning of a user message. Mentioning an agent bypasses background reasoning, resulting in lower response latencies.|
| **User preferences** | <div class="image-zoom"><a href="/images/features/feature-5.png" target="_blank"><img src="/images/features/feature-5.png" class="thumbnail"></a><a href="/images/features/feature-5.png" target="_blank" class="large-link"><img src="/images/features/feature-5.png" class="large"></a></div> | Users can set preferences in plain English to personalize how agents interact with them. Agents respect these settings for every user in a session, tailoring their behavior and response style to each person's preferences.|
| **User secrets** | <div class="image-zoom"><a href="/images/features/feature-6.png" target="_blank"><img src="/images/features/feature-6.png" class="thumbnail"></a><a href="/images/features/feature-6.png" target="_blank" class="large-link"><img src="/images/features/feature-6.png" class="large"></a></div> | Users can provide secrets, such as API keys, to authorize agents to perform actions on their behalf. These secrets are encrypted at rest and used at runtime to securely access private resources for that user. They are never shared with other users.|
| **Tool permissions** | <div class="image-zoom"><a href="/images/features/feature-7.png" target="_blank"><img src="/images/features/feature-7.png" class="thumbnail"></a><a href="/images/features/feature-7.png" target="_blank" class="large-link"><img src="/images/features/feature-7.png" class="large"></a></div> | Agents use tools to perform actions. Tool execution permissions can be granted once, for the duration of a session or permanently on a per-user basis. A permission request is sent to a user via a private channel. In Slack, for example, a permission request is sent as [ephemeral message](https://api.slack.com/surfaces/messages#ephemeral) that is only visible to the user who triggered the execution.|
| **Task handoff** | <div class="image-zoom"><a href="/images/features/feature-8.png" target="_blank"><img src="/images/features/feature-8.png" class="thumbnail"></a><a href="/images/features/feature-8.png" target="_blank" class="large-link"><img src="/images/features/feature-8.png" class="large"></a></div> | Agents can be configured to handoff tasks to other, more specialized agents in the registry. User context is preserved during a handoff, or even a chain of handoffs. For example, in a handoff chain `User 1 -> Agent A -> Agent B -> Agent C`, `Agent C` still acts on behalf of the `User 1`.|
| **Agent builder** | <div class="image-zoom"><a href="/images/features/feature-10.png" target="_blank"><img src="/images/features/feature-10.png" class="thumbnail"></a><a href="/images/features/feature-10.png" target="_blank" class="large-link"><img src="/images/features/feature-10.png" class="large"></a></div> | The Slack app includes a simple [agent builder](builder.md) to create and edit agents from the app's home view. Users can build custom agents by defining their system prompt, model, tools, and criteria for for being activated by background reasoning. For integrating more advanced agents or agentic systems, use the *Hybrid Groups* Python SDK.|
| **Python SDK**| | The Slack and GitHub integrations are built on our Python SDK, which provides the building blocks for developing custom multi-user, multi-agent applications. For interacting with agents, it defines an `Agent` abstraction that we currently implement with [Pydantic AI](https://ai.pydantic.dev/) but it can be replaced with other implementations if desired.|
| **Session persistence**| | Group sessions are saved, so they can be resumed after a server restart. This includes all messages and the states of agents and background reasoners. Messages added by users in Slack or GitHub while the server is down are synchronized when sessions are resumed.|
