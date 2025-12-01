from django.core.management.base import BaseCommand
from main_app.models import CustomUser, Course, Session, Staff, Student, Subject, LeaveReportStudent, LeaveReportStaff, FeedbackStudent, FeedbackStaff
from faker import Faker
import random
from datetime import date, timedelta

class Command(BaseCommand):
    help = 'Populate database with demo data'

    def handle(self, *args, **kwargs):
        fake = Faker()

        self.stdout.write('Creating Courses...')
        courses = []
        for _ in range(20):
            course = Course.objects.create(name=fake.job()[:50])
            courses.append(course)

        self.stdout.write('Creating Sessions...')
        sessions = []
        start_year_base = 2020
        for i in range(20):
            start_year = date(start_year_base + i, 1, 1)
            end_year = date(start_year_base + i + 1, 1, 1)
            session = Session.objects.create(start_year=start_year, end_year=end_year)
            sessions.append(session)

        self.stdout.write('Creating Staff...')
        staff_users = []
        for _ in range(20):
            email = fake.email()
            if not CustomUser.objects.filter(email=email).exists():
                user = CustomUser.objects.create_user(
                    email=email,
                    password='password123',
                    user_type=2,
                    first_name=fake.first_name(),
                    last_name=fake.last_name(),
                    gender=random.choice(['M', 'F']),
                    address=fake.address()
                )
                user.staff.course = random.choice(courses)
                user.save()
                staff_users.append(user)

        self.stdout.write('Creating Students...')
        student_users = []
        for _ in range(20):
            email = fake.email()
            if not CustomUser.objects.filter(email=email).exists():
                user = CustomUser.objects.create_user(
                    email=email,
                    password='password123',
                    user_type=3,
                    first_name=fake.first_name(),
                    last_name=fake.last_name(),
                    gender=random.choice(['M', 'F']),
                    address=fake.address()
                )
                user.student.course = random.choice(courses)
                user.student.session = random.choice(sessions)
                user.save()
                student_users.append(user)

        self.stdout.write('Creating Subjects...')
        for _ in range(20):
            staff = random.choice(staff_users).staff
            course = staff.course
            Subject.objects.create(
                name=fake.bs()[:50],
                course=course,
                staff=staff
            )

        self.stdout.write('Creating Leave Reports for Students...')
        for _ in range(20):
            student = random.choice(student_users).student
            LeaveReportStudent.objects.create(
                student=student,
                date=(date.today() - timedelta(days=random.randint(0, 365))).strftime('%Y-%m-%d'),
                message=fake.sentence(),
                status=random.choice([0, 1, -1])
            )

        self.stdout.write('Creating Leave Reports for Staff...')
        for _ in range(20):
            staff = random.choice(staff_users).staff
            LeaveReportStaff.objects.create(
                staff=staff,
                date=(date.today() - timedelta(days=random.randint(0, 365))).strftime('%Y-%m-%d'),
                message=fake.sentence(),
                status=random.choice([0, 1, -1])
            )

        self.stdout.write('Creating Feedback for Students...')
        for _ in range(20):
            student = random.choice(student_users).student
            FeedbackStudent.objects.create(
                student=student,
                feedback=fake.paragraph(),
                reply=''
            )

        self.stdout.write('Creating Feedback for Staff...')
        for _ in range(20):
            staff = random.choice(staff_users).staff
            FeedbackStaff.objects.create(
                staff=staff,
                feedback=fake.paragraph(),
                reply=''
            )

        self.stdout.write(self.style.SUCCESS('Successfully populated demo data'))
