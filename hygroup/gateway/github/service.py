from github import Github

from hygroup.utils import arun


class GithubService:
    def __init__(self, github_client: Github):
        self._github_client = github_client

    async def create_issue_comment(
        self,
        repository_name: str,
        issue_number: int,
        text: str,
    ) -> dict:
        return await arun(
            self._create_issue_comment_blocking,
            self._github_client,
            repository_name,
            issue_number,
            text,
        )

    @staticmethod
    def _create_issue_comment_blocking(
        github_client: Github,
        repository_name: str,
        issue_number: int,
        text: str,
    ) -> dict:
        repo = github_client.get_repo(repository_name)
        issue = repo.get_issue(issue_number)
        comment = issue.create_comment(text)

        return {
            "id": comment.id,
            "body": comment.body,
            "created_at": comment.created_at,
            "user": comment.user.login,
        }

    async def add_reaction_to_issue_description(
        self,
        repository_name: str,
        issue_number: int,
        reaction: str,
    ) -> dict:
        return await arun(
            self._add_reaction_to_issue_blocking,
            self._github_client,
            repository_name,
            issue_number,
            reaction,
            None,
        )

    async def add_reaction_to_issue_comment(
        self,
        repository_name: str,
        issue_number: int,
        reaction: str,
        comment_id: int,
    ) -> dict:
        return await arun(
            self._add_reaction_to_issue_blocking,
            self._github_client,
            repository_name,
            issue_number,
            reaction,
            comment_id,
        )

    @staticmethod
    def _add_reaction_to_issue_blocking(
        github_client: Github,
        repository_name: str,
        issue_number: int,
        reaction: str,
        comment_id: int | None = None,
    ) -> dict:
        repo = github_client.get_repo(repository_name)
        issue = repo.get_issue(issue_number)

        if comment_id is not None:
            comment = issue.get_comment(comment_id)
            reaction_obj = comment.create_reaction(reaction)
        else:
            reaction_obj = issue.create_reaction(reaction)

        return {
            "id": reaction_obj.id,
            "content": reaction_obj.content,
            "created_at": reaction_obj.created_at,
            "user": reaction_obj.user.login,
        }
