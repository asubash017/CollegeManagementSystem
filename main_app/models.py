from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import AbstractUser, UserManager
from django.db import models
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.templatetags.static import static




class CustomUserManager(UserManager):
    def _create_user(self, email, password, **extra_fields):
        email = self.normalize_email(email)
        user = CustomUser(email=email, **extra_fields)
        user.password = make_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        assert extra_fields["is_staff"]
        assert extra_fields["is_superuser"]
        return self._create_user(email, password, **extra_fields)


class Session(models.Model):
    start_year = models.DateField()
    end_year = models.DateField()

    def __str__(self):
        return "From " + str(self.start_year) + " to " + str(self.end_year)


class CustomUser(AbstractUser):
    USER_TYPE = ((1, "HOD"), (2, "Staff"), (3, "Student"))
    GENDER = [("M", "Male"), ("F", "Female")]
    
    
    username = None  # Removed username, using email instead
    email = models.EmailField(unique=True)
    user_type = models.CharField(default=1, choices=USER_TYPE, max_length=1)
    gender = models.CharField(max_length=1, choices=GENDER)
    profile_pic = models.ImageField(upload_to='profile_pics/', blank=True, null=True)
    address = models.TextField()
    fcm_token = models.TextField(default="")  # For firebase notifications
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []
    objects = CustomUserManager()

    def __str__(self):
        return self.last_name + ", " + self.first_name

    @property
    def avatar_url(self):
        pic = getattr(self, 'profile_pic', None)
        if pic:
            try:
                return pic.url
            except ValueError:
                if isinstance(pic, str) and pic:
                    return pic
                # Fall through to default
        return static('dist/img/default-150x150.png')


class Admin(models.Model):
    admin = models.OneToOneField(CustomUser, on_delete=models.CASCADE)
    admin_id_number = models.CharField(max_length=20, unique=True, blank=True, null=True, help_text="Leave blank to auto-generate ADM-XXXX")
    phone = models.CharField(max_length=10, blank=True, null=True)



class Course(models.Model):
    name = models.CharField(max_length=120)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class Student(models.Model):
    admin = models.OneToOneField(CustomUser, on_delete=models.CASCADE)
    registration_number = models.CharField(max_length=20, unique=True, blank=True, null=True, help_text="Government-issued ID (Admin only)")
    phone = models.CharField(max_length=10, blank=True, null=True)
    course = models.ForeignKey(Course, on_delete=models.DO_NOTHING, null=True, blank=False)
    session = models.ForeignKey(Session, on_delete=models.DO_NOTHING, null=True)

    def __str__(self):
        return self.admin.last_name + ", " + self.admin.first_name


class Staff(models.Model):
    staff_id_number = models.CharField(max_length=20, unique=True, blank=True, null=True, help_text="Leave blank to auto-generate STF-XXXX")
    phone = models.CharField(max_length=10, blank=True, null=True)
    course = models.ForeignKey(Course, on_delete=models.DO_NOTHING, null=True, blank=False)
    admin = models.OneToOneField(CustomUser, on_delete=models.CASCADE)

    def __str__(self):
        return self.admin.last_name + " " + self.admin.first_name


class Subject(models.Model):
    name = models.CharField(max_length=120)
    staff = models.ForeignKey(Staff,on_delete=models.CASCADE,)
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Attendance(models.Model):
    session = models.ForeignKey(Session, on_delete=models.DO_NOTHING)
    subject = models.ForeignKey(Subject, on_delete=models.DO_NOTHING)
    date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class AttendanceReport(models.Model):
    student = models.ForeignKey(Student, on_delete=models.DO_NOTHING)
    attendance = models.ForeignKey(Attendance, on_delete=models.CASCADE)
    status = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class LeaveReportStudent(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    date = models.DateField()          # ← CharField → DateField
    end_date = models.DateField(blank=True, null=True, help_text="Leave end date (optional)")
    message = models.TextField()
    status = models.SmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class LeaveReportStaff(models.Model):
    staff = models.ForeignKey(Staff, on_delete=models.CASCADE)
    date = models.DateField()          # ← CharField → DateField
    end_date = models.DateField(blank=True, null=True, help_text="Leave end date (optional)")
    message = models.TextField()
    status = models.SmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class FeedbackStudent(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    feedback = models.TextField()
    reply = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class FeedbackStaff(models.Model):
    staff = models.ForeignKey(Staff, on_delete=models.CASCADE)
    feedback = models.TextField()
    reply = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class NotificationStaff(models.Model):
    staff = models.ForeignKey(Staff, on_delete=models.CASCADE)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class NotificationStudent(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class StudentResult(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    test = models.FloatField(default=0)
    exam = models.FloatField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


@receiver(post_save, sender=CustomUser)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        if instance.user_type == 1:
            Admin.objects.create(admin=instance)
        if instance.user_type == 2:
            Staff.objects.create(admin=instance)
        if instance.user_type == 3:
            Student.objects.create(admin=instance)


@receiver(post_save, sender=CustomUser)
def save_user_profile(sender, instance, **kwargs):
    if instance.user_type == 1:
        instance.admin.save()
    if instance.user_type == 2:
        instance.staff.save()
    if instance.user_type == 3:
        instance.student.save()


# ---------- auto-generate ID numbers ----------
from django.contrib.auth import get_user_model

def make_id(model, prefix, field='id'):
    """Return next sequential ID with prefix."""
    last = model.objects.filter(**{f"{field}__isnull": False}).order_by(field).last()
    if last:
        raw = getattr(last, field) or ''
        try:
            seq = int(raw.split('-')[1]) + 1
        except Exception:
            seq = 1
    else:
        seq = 1
    return f"{prefix}-{seq:04d}"

@receiver(pre_save, sender=Admin)
def set_admin_id(sender, instance, **kwargs):
    if not instance.admin_id_number:
        instance.admin_id_number = make_id(Admin, 'ADM', 'admin_id_number')

@receiver(pre_save, sender=Staff)
def set_staff_id(sender, instance, **kwargs):
    if not instance.staff_id_number:
        instance.staff_id_number = make_id(Staff, 'STF', 'staff_id_number')

@receiver(pre_save, sender=Student)
def set_reg_num(sender, instance, **kwargs):
    if not instance.registration_number:
        instance.registration_number = make_id(Student, 'REG', 'registration_number')


class SystemSettings(models.Model):
    system_name = models.CharField(max_length=200, default="College Management System")
    email_host = models.CharField(max_length=200, default="smtp.gmail.com")
    email_port = models.IntegerField(default=587)
    email_host_user = models.CharField(max_length=200, blank=True)
    email_host_password = models.CharField(max_length=200, blank=True)
    sms_api_key = models.CharField(max_length=200, blank=True)
    chat_bot_name = models.CharField(max_length=100, default="AI Support")
    chat_default_response = models.TextField(default="I'm sorry, I didn't understand that. You can ask about your profile, attendance, notifications, subjects, or sessions.")
    gemini_api_key = models.CharField(max_length=200, blank=True)
    preset_questions = models.TextField(default="Show my profile, Check attendance, Any notifications?")
    
    def __str__(self):
        return self.system_name

    def save(self, *args, **kwargs):
        if not self.pk and SystemSettings.objects.exists():
            # If you want to ensure only one instance, you can do this check
            # but for simplicity we might just rely on the view to always get the first one.
            pass
        return super(SystemSettings, self).save(*args, **kwargs)



class DashboardNotification(models.Model):
    """Track dashboard notifications and unread status for users"""
    NOTIFICATION_TYPES = (
        ('leave_student', 'Student Leave Request'),
        ('leave_staff', 'Staff Leave Request'),
        ('feedback_student', 'Student Feedback'),
        ('feedback_staff', 'Staff Feedback'),
        ('result_update', 'Result Updated'),
        ('admin_notification', 'Admin Notification'),
        ('leave_reply', 'Leave Reply'),
        ('feedback_reply', 'Feedback Reply'),
    )
    
    recipient = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='dashboard_notifications')
    sender = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='sent_notifications', null=True, blank=True)
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES)
    title = models.CharField(max_length=200)
    message = models.TextField()
    related_id = models.IntegerField(null=True, blank=True)  # ID of related object (leave, feedback, etc.)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['recipient', 'is_read']),
            models.Index(fields=['notification_type']),
        ]
    
    def __str__(self):
        return f"{self.get_notification_type_display()} - {self.title}"
    
    def mark_as_read(self):
        if not self.is_read:
            self.is_read = True
            self.save()
    
    @property
    def sender_name(self):
        if self.sender:
            return f"{self.sender.first_name} {self.sender.last_name}"
        return "System"


class Holiday(models.Model):
    name = models.CharField(max_length=120)
    date = models.DateField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date']

    def __str__(self):
        return f"{self.name} ({self.date})"


class UserActivityLog(models.Model):
    """Track user activities for audit trail"""
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    action = models.CharField(max_length=200)
    details = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.email} - {self.action}"
    
    # main_app/models.py  (LAST line, after UserActivityLog)
    print("✅  main_app/models.py  was  imported  –  DashboardNotification exists :",
          'DashboardNotification' in globals())