# main_app/notification_service.py
import logging
import sys
from django.apps import apps
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.db.models import Q

logger = logging.getLogger(__name__)

# ========== SIGNAL REGISTRATION GUARD ==========
# Track if signals already registered to prevent duplicates
_SIGNALS_REGISTERED = False

def get_admin_users():
    """Get all active HOD/Admin users (user_type=1)"""
    try:
        from .models import CustomUser
        return CustomUser.objects.filter(user_type=1, is_active=True)
    except Exception as exc:
        import logging
        logger = logging.getLogger(__name__)
        logger.exception("get_admin_users failed: %s", exc)
        return []

def register_signals_once():
    """Register all notification signals only once"""
    global _SIGNALS_REGISTERED
    if _SIGNALS_REGISTERED:
        return
    
    logger.info("🔔 Registering notification signals...")
        
    @receiver(post_save, sender="main_app.LeaveReportStudent")
    def notify_student_leave(sender, instance, created, **kwargs):
        if not created:
            return

        # 1. Notify Student (existing)
        NotificationService.create_notification(
            recipient=instance.student.admin,
            notification_type="leave_student",
            title="Leave Request Submitted",
            message=f"Your leave request for {instance.date} has been submitted.",
            related_id=instance.id,
        )

        # 2. Notify All Admins
        admin_users = get_admin_users()  # Use the standalone function

        for admin in admin_users:
            NotificationService.create_notification(
                recipient=admin,
                notification_type="admin_notification",
                title="New Student Leave Request",
                message=f"{instance.student.admin.first_name} {instance.student.admin.last_name} submitted a leave request for {instance.date}.",
                sender=instance.student.admin,
                related_id=instance.id,
            )
    
    # 2. staff leave request ----------------------------------------------------
    @receiver(post_save, sender="main_app.LeaveReportStaff")
    def notify_staff_leave(sender, instance, created, **kwargs):
        if not created:
            return

        # 1. Notify Staff
        NotificationService.create_notification(
            recipient=instance.staff.admin,
            notification_type="leave_staff",
            title="Leave Request Submitted",
            message=f"Your leave request for {instance.date} has been submitted.",
            related_id=instance.id,
        )

        # 2. Notify All Admins
        admin_users = get_admin_users()

        for admin in admin_users:
            NotificationService.create_notification(
                recipient=admin,
                notification_type="admin_notification",
                title="New Staff Leave Request",
                message=f"{instance.staff.admin.first_name} {instance.staff.admin.last_name} submitted a leave request for {instance.date}.",
                sender=instance.staff.admin,
                related_id=instance.id,
            )

    # 3. student feedback -------------------------------------------------------
    @receiver(post_save, sender="main_app.FeedbackStudent")
    def notify_student_feedback(sender, instance, created, **kwargs):
        if not created:
            return
        
        # 1. Notify Student
        NotificationService.create_notification(
            recipient=instance.student.admin,
            notification_type="feedback_student",
            title="Feedback Sent",
            message="Your feedback has been sent to the administration.",
            related_id=instance.id,
        )
        
        # 2. Notify All Admins
        admin_users = get_admin_users()
        
        for admin in admin_users:
            NotificationService.create_notification(
                recipient=admin,
                notification_type="admin_notification",
                title="New Student Feedback",
                message=f"{instance.student.admin.first_name} {instance.student.admin.last_name} submitted feedback.",
                sender=instance.student.admin,
                related_id=instance.id,
            )
    
    # 4. staff feedback ---------------------------------------------------------
    @receiver(post_save, sender="main_app.StudentResult")
    def notify_result_update(sender, instance, created, **kwargs):
        if created:  # Only notify on updates, not creation
            return

        # 1. Notify Student (existing)
        subject_staff = instance.subject.staff
        NotificationService.create_notification(
            recipient=instance.student.admin,
            notification_type="result_update",
            title="Result Updated",
            message=f"Your result for {instance.subject.name} has been updated.",
            sender=subject_staff.admin if subject_staff else None,
            related_id=instance.id,
        )

        # 2. NEW: Notify Staff (success confirmation)
        if subject_staff and subject_staff.admin:
            NotificationService.create_notification(
                recipient=subject_staff.admin,
                notification_type="result_update",
                title="Result Update Successful",
                message=f"You successfully updated result for {instance.student.admin.first_name} {instance.student.admin.last_name} in {instance.subject.name}.",
                related_id=instance.id,
            )
    
    # 5. result update ----------------------------------------------------------
    @receiver(post_save, sender="main_app.StudentResult")
    def notify_result_update(sender, instance, created, **kwargs):
        if created:  # we only notify on *update*
            return
        from .notification_service import NotificationService
        subject_staff = instance.subject.staff
        NotificationService.create_notification(
            recipient=instance.student.admin,
            notification_type="result_update",
            title="Result Updated",
            message=f"Your result for {instance.subject.name} has been updated.",
            sender=subject_staff.admin if subject_staff else None,
            related_id=instance.id,
        )
    
    # 6. holiday added ----------------------------------------------------------
    @receiver(post_save, sender="main_app.Holiday")
    def holiday_added(sender, instance, created, **kwargs):
        if not created:
            return
        from .notification_service import NotificationService
        NotificationService.create_system_notification(
            notification_type='admin_notification',
            title="New Holiday Added",
            message=f"{instance.name} on {instance.date} has been declared."
        )
    
    # 7. holiday removed -------------------------------------------------------
    @receiver(post_delete, sender="main_app.Holiday")
    def holiday_removed(sender, instance, **kwargs):
        from .notification_service import NotificationService
        NotificationService.create_system_notification(
            notification_type='admin_notification',
            title="Holiday Removed",
            message=f"{instance.name} on {instance.date} has been removed."
        )
    
    _SIGNALS_REGISTERED = True
    logger.info("✅ Notification signals registered successfully")

# ========== REST OF YOUR EXISTING CODE ==========
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
        """Return QS with unread notifications for user + system (newest first)."""
        try:
            DashboardNotification = get_model("DashboardNotification")
            from django.contrib.auth import get_user_model
            User = get_user_model()
            system = User.objects.get(email='system@college.edu')
            return DashboardNotification.objects.filter(
                Q(recipient=user) | Q(recipient=system),
                is_read=False
            ).order_by("-created_at")
        except Exception as exc:  # noqa: BLE001
            logger.exception("get_unread_notifications failed: %s", exc)
            return []

    @staticmethod
    def get_notification_count(user):
        """Unread count for user + system."""
        try:
            DashboardNotification = get_model("DashboardNotification")
            from django.contrib.auth import get_user_model
            User = get_user_model()
            system = User.objects.get(email='system@college.edu')
            return DashboardNotification.objects.filter(
                Q(recipient=user) | Q(recipient=system),
                is_read=False
            ).count()
        except Exception as exc:  # noqa: BLE001
            logger.exception("get_notification_count failed: %s", exc)
            return 0

    @staticmethod
    def mark_all_as_read(user):
        """Mark every unread notification for user + system as read."""
        try:
            DashboardNotification = get_model("DashboardNotification")
            from django.contrib.auth import get_user_model
            User = get_user_model()
            system = User.objects.get(email='system@college.edu')
            return DashboardNotification.objects.filter(
                Q(recipient=user) | Q(recipient=system),
                is_read=False
            ).update(is_read=True)
        except Exception as exc:  # noqa: BLE001
            logger.exception("mark_all_as_read failed: %s", exc)
            return 0

    @staticmethod
    def create_system_notification(notification_type, title, message, related_id=None):
        """Create a single notification row attached to sentinel user."""
        from django.contrib.auth import get_user_model
        User = get_user_model()
        system, _ = User.objects.get_or_create(email='system@college.edu', defaults={'first_name': 'System'})
        return NotificationService.create_notification(
            recipient=system,
            notification_type=notification_type,
            title=title,
            message=message,
            sender=None,
            related_id=related_id,
        )

# ========== AUTOMATIC SIGNAL REGISTRATION ==========
# Call this once when module loads
register_signals_once()