import json
import logging                       # <--- 1.  std-lib imports first
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.apps import apps
from django.shortcuts import render
from django.template.loader import render_to_string

from .notification_service import NotificationService   # <--- 2.  your code

logger = logging.getLogger(__name__)       

# Get models dynamically to avoid circular imports
def get_model(model_name):
    try:
        return apps.get_model('main_app', model_name)
    except Exception as e:
        return None

# ========== NOTIFICATION API VIEWS ==========

@login_required
def get_dashboard_notifications(request):
    """Get dashboard notifications for the current user"""
    try:
        from .notification_service import NotificationService
        
        notifications = NotificationService.get_unread_notifications(request.user)
        
        notification_data = []
        for notification in notifications[:10]:  # Get latest 10
            notification_data.append({
                'id': notification.id,
                'type': notification.notification_type,
                'title': notification.title,
                'message': notification.message,
                'sender': notification.sender_name,
                'created_at': notification.created_at.strftime('%Y-%m-%d %H:%M'),
                'is_read': notification.is_read,
                'related_id': notification.related_id
            })
        
        return JsonResponse({
            'success': True,
            'notifications': notification_data,
            'unread_count': NotificationService.get_notification_count(request.user)
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

@login_required
def mark_notification_read(request, notification_id):
    """Mark a notification as read"""
    try:
        DashboardNotification = apps.get_model('main_app', 'DashboardNotification')
        notification = DashboardNotification.objects.get(
            id=notification_id, 
            recipient=request.user
        )
        notification.mark_as_read()
        return JsonResponse({'success': True})
    except DashboardNotification.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Notification not found'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

@login_required
def mark_all_notifications_read(request):
    """Mark all notifications as read for current user"""
    try:
        from .notification_service import NotificationService
        
        count = NotificationService.mark_all_as_read(request.user)
        return JsonResponse({
            'success': True,
            'marked_count': count
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

@login_required
def get_notification_count(request):
    """Get unread notification count"""
    try:
        from .notification_service import NotificationService
        
        count = NotificationService.get_notification_count(request.user)
        return JsonResponse({
            'success': True,
            'count': count
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

# ========== DASHBOARD NOTIFICATION WIDGET VIEWS ==========

@login_required
def dashboard_notifications_widget(request):
    """Render the notifications widget for dashboard"""
    return render(request, 'main_app/dashboard_notifications_widget.html')


@login_required
def get_user_notifications_html(request):
    try:
        notifications = NotificationService.get_unread_notifications(request.user)[:5]

        if not notifications:
            html = '''
                <div class="text-center p-3 text-muted">
                    <i class="fas fa-bell-slash fa-2x mb-2"></i>
                    <p>No new notifications</p>
                </div>
            '''
        else:
            html = ''
            for n in notifications:
                html += render_to_string(
                    'main_app/notification_dropdown_item.html',
                    {'notification': n, 'notification_icon': get_notification_icon(n.notification_type)}
                )

        return JsonResponse({
            'success': True,
            'html': html,
            'unread_count': NotificationService.get_notification_count(request.user)
        })
    except Exception as e:
        logger.exception('get_user_notifications_html error')
        return JsonResponse({'success': False, 'error': 'Server error'}, status=500)


def get_notification_icon(notification_type):
    """Get icon for notification type"""
    icon_map = {
        'leave_student': '📅',
        'leave_staff': '📅',
        'feedback_student': '💬',
        'feedback_staff': '💬',
        'result_update': '📊',
        'admin_notification': '📢',
        'leave_reply': '↩️',
        'feedback_reply': '↩️'
    }
    return icon_map.get(notification_type, '📢')