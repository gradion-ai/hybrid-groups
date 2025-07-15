from dataclasses import dataclass


@dataclass
class GithubEvent:
    repository_id: int
    repository_full_name: str
    issue_id: int
    issue_number: int
    user_id: int
    username: str

    @property
    def repository_owner(self) -> str:
        return self.repository_full_name.split("/")[0]

    @property
    def repository_name(self) -> str:
        return self.repository_full_name.split("/")[1]


@dataclass
class IssueOpened(GithubEvent):
    title: str
    description: str | None


@dataclass
class IssueCommentCreated(GithubEvent):
    comment_id: int
    comment: str


@dataclass
class PullRequestOpened(GithubEvent):
    title: str
    description: str
    branch_name: str


@dataclass
class PullRequestCommentCreated(GithubEvent):
    comment_id: int
    comment: str


@dataclass
class PullRequestReviewSubmitted(GithubEvent):
    review_id: int
    review_node_id: str
    comment: str | None


def map_github_event(event_type: str, payload: dict) -> GithubEvent | None:
    match event_type:
        case "issues":
            match payload["action"]:
                case "opened":
                    return IssueOpened(
                        repository_id=payload["repository"]["id"],
                        repository_full_name=payload["repository"]["full_name"],
                        issue_id=payload["issue"]["id"],
                        issue_number=payload["issue"]["number"],
                        user_id=payload["issue"]["user"]["id"],
                        username=payload["issue"]["user"]["login"],
                        title=payload["issue"]["title"],
                        description=payload["issue"]["body"],
                    )
                case _:
                    return None
        case "pull_request":
            match payload["action"]:
                case "opened":
                    return PullRequestOpened(
                        repository_id=payload["repository"]["id"],
                        repository_full_name=payload["repository"]["full_name"],
                        issue_id=payload["pull_request"]["id"],
                        issue_number=payload["pull_request"]["number"],
                        user_id=payload["pull_request"]["user"]["id"],
                        username=payload["pull_request"]["user"]["login"],
                        title=payload["pull_request"]["title"],
                        description=payload["pull_request"]["body"],
                        branch_name=payload["pull_request"]["head"]["ref"],
                    )
                case _:
                    return None
        case "issue_comment":
            match payload["action"]:
                case "created":
                    if "pull_request" in payload["issue"]:
                        return PullRequestCommentCreated(
                            repository_id=payload["repository"]["id"],
                            repository_full_name=payload["repository"]["full_name"],
                            issue_id=payload["issue"]["id"],
                            issue_number=payload["issue"]["number"],
                            comment_id=payload["comment"]["id"],
                            user_id=payload["comment"]["user"]["id"],
                            username=payload["comment"]["user"]["login"],
                            comment=payload["comment"]["body"],
                        )
                    else:
                        return IssueCommentCreated(
                            repository_id=payload["repository"]["id"],
                            repository_full_name=payload["repository"]["full_name"],
                            issue_id=payload["issue"]["id"],
                            issue_number=payload["issue"]["number"],
                            comment_id=payload["comment"]["id"],
                            user_id=payload["comment"]["user"]["id"],
                            username=payload["comment"]["user"]["login"],
                            comment=payload["comment"]["body"],
                        )
                case _:
                    return None
        case "pull_request_review":
            match payload["action"]:
                case "submitted":
                    return PullRequestReviewSubmitted(
                        repository_id=payload["repository"]["id"],
                        repository_full_name=payload["repository"]["full_name"],
                        issue_id=payload["pull_request"]["id"],
                        issue_number=payload["pull_request"]["number"],
                        user_id=payload["review"]["user"]["id"],
                        username=payload["review"]["user"]["login"],
                        comment=payload["review"]["body"],
                        review_id=payload["review"]["id"],
                        review_node_id=payload["review"]["node_id"],
                    )
                case _:
                    return None
        case _:
            return None
