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
