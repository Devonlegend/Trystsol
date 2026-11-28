import datetime as dt
import logging

from celery import shared_task
from django.utils import timezone

from apps.chain import rpc
from apps.chain.models import SignedIntent
from apps.milestones.models import Milestone

logger = logging.getLogger(__name__)


@shared_task
def prune_expired_intents(hours: int = 24) -> int:
    """Remove un-consumed intents that have been expired for a while."""
    cutoff = timezone.now() - dt.timedelta(hours=hours)
    queryset = SignedIntent.objects.filter(
        consumed_at__isnull=True, expires_at__lt=cutoff
    )
    count = queryset.count()
    queryset.delete()
    logger.info("pruned_expired_intents", extra={"count": count})
    return count


@shared_task
def check_rpc_health() -> str:
    status = rpc.get_health()
    logger.info("rpc_health", extra={"status": status})
    return status


@shared_task
def reconcile_chain_state(limit: int = 50) -> dict:
    """Spot-check that milestones with a chain PDA still exist on-chain.

    A missing account is a reconciliation mismatch and is logged. The task does not
    mutate records; a human or the indexer resolves the difference.
    """
    milestones = (
        Milestone.objects.exclude(onchain_milestone_pda="")
        .order_by("-updated_at")[:limit]
    )
    checked = 0
    missing = 0
    for milestone in milestones:
        checked += 1
        try:
            account = rpc.get_account_info(milestone.onchain_milestone_pda)
        except rpc.RpcError:
            logger.exception("reconcile_rpc_error", extra={"milestone": str(milestone.id)})
            continue
        if account is None:
            missing += 1
            logger.warning(
                "reconcile_missing_account",
                extra={"milestone": str(milestone.id), "pda": milestone.onchain_milestone_pda},
            )
    result = {"checked": checked, "missing": missing}
    logger.info("reconcile_complete", extra=result)
    return result
