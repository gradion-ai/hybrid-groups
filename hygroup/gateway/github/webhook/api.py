import hashlib
import hmac
import logging

from fastapi import APIRouter, Header, HTTPException, Request

from hygroup.gateway.github.webhook.dependencies import GithubWebhookSecretDependency, WebhookHandlerDependency

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/github-webhook")
async def github_webhook(
    request: Request,
    github_webhook_secret: GithubWebhookSecretDependency,
    webhook_handler: WebhookHandlerDependency,
    x_hub_signature_256: str = Header(None),
    x_github_event: str = Header(None),
):
    body_bytes = await request.body()
    digest = "sha256=" + hmac.new(github_webhook_secret, body_bytes, hashlib.sha256).hexdigest()
    if x_hub_signature_256 != digest:
        raise HTTPException(status_code=400, detail="Invalid signature")

    payload = await request.json()
    event_type = x_github_event
    action = payload.get("action")

    logger.info("Received webhook (event_type='%s', action='%s')", event_type, action)

    await webhook_handler(event_type, payload)

    return {"status": "received"}
