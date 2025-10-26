from pathlib import Path

from group_genie.agent.base import AgentInfo


def system_prompt(subagent_infos: list[AgentInfo]) -> str:
    system_prompt_path = Path(__file__).parent / "prompt.md"
    system_prompt_template = system_prompt_path.read_text()
    return system_prompt_template.format(subagents=format_subagent_infos(subagent_infos))


def format_subagent_infos(subagent_infos: list[AgentInfo]) -> str:
    return "\n".join([f"- {info.name}: {info.description}" for info in subagent_infos])


def example():
    subagent_infos = [
        AgentInfo(name="weather", description="A subagent that can report the weather for a city."),
        AgentInfo(name="news", description="A subagent that can report the news for a date."),
    ]
    print(system_prompt(subagent_infos))


if __name__ == "__main__":
    example()
