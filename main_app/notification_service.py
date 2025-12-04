# main_app/notification_service.py
import logging
from django.apps import apps
from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


# ---------- helpers ----------
def get_model(model_name: str):
    """Fetch a main_app model without circular imports."""
    return apps.get_model("main_app", model_name)


# ---------- service ----------
class NotificationService:
    """Central place to create / query dashboard notifications."""

    # –––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
    # CRUD helpers
    # –––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
    @staticmethod
    def create_notification(
        recipient, notification_type, title, message, sender=None, related_id=None
    ):
        """Create and return a DashboardNotification row."""
        try:
            DashboardNotification = get_model("DashboardNotification")
            return DashboardNotification.objects.create(
                recipient=recipient,
                sender=sender,
                notification_type=notification_type,
                title=title,
                message=message,
                related_id=related_id,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("create_notification failed: %s", exc)
            return None

    @staticmethod
    def get_unread_notifications(user):
        """Return QS with unread notifications for user (newest first)."""
        try:
            DashboardNotification = get_model("DashboardNotification")
            return DashboardNotification.objects.filter(
                recipient=user, is_read=False
            ).order_by("-created_at")
        except Exception as exc:  # noqa: BLE001
            logger.exception("get_unread_notifications failed: %s", exc)
            return []

    @staticmethod
    def get_notification_count(user):
        """Unread count for user."""
        try:
            DashboardNotification = get_model("DashboardNotification")
            return DashboardNotification.objects.filter(
                recipient=user, is_read=False
            ).count()
        except Exception as exc:  # noqa: BLE001
            logger.exception("get_notification_count failed: %s", exc)
            return 0

    @staticmethod
    def mark_all_as_read(user):
        """Mark every unread notification for user as read."""
        try:
            DashboardNotification = get_model("DashboardNotification")
            return DashboardNotification.objects.filter(
                recipient=user, is_read=False
            ).update(is_read=True)
        except Exception as exc:  # noqa: BLE001
            logger.exception("mark_all_as_read failed: %s", exc)
            return 0


# ---------- signals (auto-register) ----------
# We import models lazily inside each receiver so the code works even when
# this file is loaded before the apps registry is fully ready.

# 1. student leave request --------------------------------------------------
@receiver(post_save, sender="main_app.LeaveReportStudent")
def notify_student_leave(sender, instance, created, **kwargs):
    if not created:
        return
    NotificationService.create_notification(
        recipient=instance.student.admin,
        notification_type="leave_student",
        title="Leave Request Submitted",
        message=f"Your leave request for {instance.date} has been submitted.",
        related_id=instance.id,
    )


# 2. staff leave request ----------------------------------------------------
@receiver(post_save, sender="main_app.LeaveReportStaff")
def notify_staff_leave(sender, instance, created, **kwargs):
    if not created:
        return
    NotificationService.create_notification(
        recipient=instance.staff.admin,
        notification_type="leave_staff",
        title="Leave Request Submitted",
        message=f"Your leave request for {instance.date} has been submitted.",
        related_id=instance.id,
    )


# 3. student feedback -------------------------------------------------------
@receiver(post_save, sender="main_app.FeedbackStudent")
def notify_student_feedback(sender, instance, created, **kwargs):
    if not created:
        return
    NotificationService.create_notification(
        recipient=instance.student.admin,
        notification_type="feedback_student",
        title="Feedback Sent",
        message="Your feedback has been sent to the administration.",
        related_id=instance.id,
    )


# 4. staff feedback ---------------------------------------------------------
@receiver(post_save, sender="main_app.FeedbackStaff")
def notify_staff_feedback(sender, instance, created, **kwargs):
    if not created:
        return
    NotificationService.create_notification(
        recipient=instance.staff.admin,
        notification_type="feedback_staff",
        title="Feedback Sent",
        message="Your feedback has been sent to the administration.",
        related_id=instance.id,
    )


# 5. result update ----------------------------------------------------------
@receiver(post_save, sender="main_app.StudentResult")
def notify_result_update(sender, instance, created, **kwargs):
    if created:  # we only notify on *update*
        return
    subject_staff = instance.subject.staff
    NotificationService.create_notification(
        recipient=instance.student.admin,
        notification_type="result_update",
        title="Result Updated",
        message=f"Your result for {instance.subject.name} has been updated.",
        sender=subject_staff.admin if subject_staff else None,
        related_id=instance.id,
    )