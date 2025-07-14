# User registry

The [app server](app-server.md) automatically maintains a user registry for storing user secrets. Manual registration of users is optional but can be useful in the following cases:

- Mapping a Slack and GitHub username to a common *Hybrid Groups* username. The backend then uses this common username for message sender and receiver identification.
- Secure login with a common username and a user pasword into a terminal-based [user channel](app-server.md#separate-user-channel) or [chat client](app-server.md#terminal).

To start user registration, run:

```shell
python -m hygroup.scripts.register
```

Then follow the instructions for providing

- a common username and an optional user password
- user secrets in the format `KEY=VALUE` (optional)
- Slack and GitHub usernames (for user mapping)
