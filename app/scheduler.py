import asyncio
import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.database import SessionLocal
from app.module_incidents.services.offer_service import OfferService

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()


def _check_offer_timeouts():
    """Detect offers that expired without a response (runs every 5s)."""
    db = SessionLocal()
    try:
        offer_service = OfferService(db)
        count = asyncio.run(offer_service.process_timeouts())
        if count > 0:
            logger.info(f"[Scheduler] Processed {count} timeouts")
    except Exception as e:
        logger.error(f"[Scheduler] Error in check_offer_timeouts: {e}")
    finally:
        db.close()


def _cleanup_old_notifications():
    """Delete read notifications older than 30 days (runs daily at 3am)."""
    db = SessionLocal()
    try:
        from datetime import datetime, timedelta, timezone
        from app.module_incidents.models import Notification

        thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
        deleted = db.query(Notification).filter(
            Notification.is_read == True,
            Notification.sent_at < thirty_days_ago,
        ).delete()
        db.commit()
        logger.info(f"[Scheduler] Deleted {deleted} old notifications")
    except Exception as e:
        logger.error(f"[Scheduler] Error in cleanup_old_notifications: {e}")
        db.rollback()
    finally:
        db.close()


def start_scheduler():
    scheduler.add_job(
        func=_check_offer_timeouts,
        trigger=IntervalTrigger(seconds=5),
        id="check_offer_timeouts",
        name="Detect offer timeouts (YANGO REAL)",
        replace_existing=True,
    )
    scheduler.add_job(
        func=_cleanup_old_notifications,
        trigger="cron",
        hour=3,
        minute=0,
        id="cleanup_notifications",
        name="Cleanup old notifications",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("Scheduler started: check_offer_timeouts every 5s")


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown()
        logger.info("Scheduler stopped")
