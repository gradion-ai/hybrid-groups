# Hybrid Groups

<p align="left">
    <a href="https://gradion-ai.github.io/hybrid-groups/"><img alt="Website" src="https://img.shields.io/website?url=https%3A%2F%2Fgradion-ai.github.io%2Fhybrid-groups%2F&up_message=online&down_message=offline&label=docs"></a>
    <a href="https://pypi.org/project/hybrid-groups/"><img alt="PyPI - Version" src="https://img.shields.io/pypi/v/hybrid-groups?color=blue"></a>
    <a href="https://github.com/gradion-ai/hybrid-groups/releases"><img alt="GitHub Release" src="https://img.shields.io/github/v/release/gradion-ai/hybrid-groups"></a>
    <a href="https://github.com/gradion-ai/hybrid-groups/actions"><img alt="GitHub Actions Workflow Status" src="https://img.shields.io/github/actions/workflow/status/gradion-ai/hybrid-groups/test.yml"></a>
    <a href="https://github.com/gradion-ai/hybrid-groups/blob/main/LICENSE"><img alt="GitHub License" src="https://img.shields.io/github/license/gradion-ai/hybrid-groups?color=blueviolet"></a>
</p>

[*Hybrid Groups*](https://gradion-ai.github.io/hybrid-groups/) is a multi-user, multi-agent platform that enables teams to collaborate with proactive and reactive agents in Slack and GitHub. It adds background reasoning to Slack threads and GitHub issues to intelligently activate agents based on chat messages and context. Agents reason, act and respond specific to a user's identity, preferences and history, and can take actions on behalf of a user. In Slack, users can build custom agents with a simple agent builder. More advanced agents or agentic systems can be integrated with the *Hybrid Groups* Python SDK.

<table>
<tr>
<td><a href="https://gradion-ai.github.io/hybrid-groups/images/overview/overview-1.png" target="_blank"><img src="https://gradion-ai.github.io/hybrid-groups/images/overview/overview-1.png" alt="Hybrid Groups" /></a></td>
<td><a href="https://gradion-ai.github.io/hybrid-groups/images/overview/overview-2.png" target="_blank"><img src="https://gradion-ai.github.io/hybrid-groups/images/overview/overview-2.png" alt="Hybrid Groups" /></a></td>
<td><a href="https://gradion-ai.github.io/hybrid-groups/images/overview/overview-3.png" target="_blank"><img src="https://gradion-ai.github.io/hybrid-groups/images/overview/overview-3.png" alt="Hybrid Groups" /></a></td>
</tr>
</table>

## Quickstart

> [!NOTE]
> The full quickstart guide is [here](https://gradion-ai.github.io/hybrid-groups/quickstart).

1. Setup the app (prints the setup URL to follow in the output) - **only required once per app**:
    ```bash
    docker run --rm -it \
        -v "$(pwd)/.data-docker":/app/.data \
        -p 8801:8801 \
        ghcr.io/gradion-ai/hybrid-groups:latest \
        setup <slack | github>
    ```
    **Important**: when running the container on a remote host, supply the hostname or IP address via the `--host` parameter. After setting up the Slack app, add it to any Slack channels you want it to be active in. You can do this from the channel's menu under `Open channel details` -> `Integrations` -> `Add apps`.

2. Run the server:
    ```bash
    docker run --rm -it \
        -v "$(pwd)/.data-docker":/app/.data \
        ghcr.io/gradion-ai/hybrid-groups:latest \
        server <slack | github>
    ```
    To enable [user channels](https://gradion-ai.github.io/hybrid-groups/app-server/#slack) in Slack, append the `--user-channel slack` option.

3. Verify that your installation works. For example, activate the `weather` agent via background reasoning by entering

    ```markdown
    how's the weather in vienna?
    ```

    in the channel where the Slack app was added

    <a href="https://gradion-ai.github.io/hybrid-groups/images/quickstart/quickstart-1.png" target="_blank"><img src="https://gradion-ai.github.io/hybrid-groups/images/quickstart/quickstart-1.png" class="thumbnail"></a>

    or in the description of a new GitHub issue:

    <a href="https://gradion-ai.github.io/hybrid-groups/images/quickstart/quickstart-2.png" target="_blank"><img src="https://gradion-ai.github.io/hybrid-groups/images/quickstart/quickstart-2.png" class="thumbnail"></a>

    For directly mentioning the `weather` agent in Slack, use `@weather` at the beginning of a message, in GitHub use `@hybrid-groups/weather` (and replace `hybrid-groups` with the GitHub app name you've chosen).
