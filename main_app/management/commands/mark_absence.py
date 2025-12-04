from django.core.management.base import BaseCommand
from django.utils import timezone
from main_app.models import Attendance, AttendanceReport, Student, Holiday

class Command(BaseCommand):
    help = "Mark absence for students not present today (skip holidays)"

    def handle(self, *args, **options):
        today = timezone.now().date()

        # 1. Skip if today is a holiday
        if Holiday.objects.filter(date=today).exists():
            self.stdout.write(self.style.SUCCESS(f"{today} is a holiday – no absence created."))
            return

        # 2. Students who were NOT marked PRESENT today
        absent_students = Student.objects.exclude(
            attendancereport__attendance__date=today,
            attendancereport__status=True
        )

        # 3. Create one “absent” record per absent student
        count = 0
        for student in absent_students:
            # Pick any subject from the student’s course (existing flow)
            subject = student.course.subject_set.first()
            if not subject:
                continue  # no subjects → skip

            # Create / get attendance row for today (any subject)
            attendance, _ = Attendance.objects.get_or_create(
                date=today,
                subject=subject,
                session=student.session
            )

            # Mark absent
            AttendanceReport.objects.get_or_create(
                student=student,
                attendance=attendance,
                defaults={'status': False}
            )
            count += 1

        self.stdout.write(self.style.SUCCESS(f"Marked {count} students absent for {today}"))