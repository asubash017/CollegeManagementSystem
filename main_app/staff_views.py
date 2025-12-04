import json

from django.contrib import messages
from django.core.files.storage import FileSystemStorage
from django.http import HttpResponse, JsonResponse
from django.shortcuts import (HttpResponseRedirect, get_object_or_404,redirect, render)
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt

from .forms import *
from .models import *


def staff_home(request):
    staff = get_object_or_404(Staff, admin=request.user)
    total_students = Student.objects.filter(course=staff.course).count()
    total_leave = LeaveReportStaff.objects.filter(staff=staff).count()
    subjects = Subject.objects.filter(staff=staff)
    total_subject = subjects.count()
    attendance_list = Attendance.objects.filter(subject__in=subjects)
    total_attendance = attendance_list.count()
    attendance_list = []
    subject_list = []
    for subject in subjects:
        attendance_count = Attendance.objects.filter(subject=subject).count()
        subject_list.append(subject.name)
        attendance_list.append(attendance_count)
    context = {
        'page_title': 'Staff Panel - ' + str(staff.admin.last_name) + ' (' + str(staff.course) + ')',
        'total_students': total_students,
        'total_attendance': total_attendance,
        'total_leave': total_leave,
        'total_subject': total_subject,
        'subject_list': subject_list,
        'attendance_list': attendance_list
    }
    return render(request, 'staff_template/home_content.html', context)


def staff_take_attendance(request):
    staff = get_object_or_404(Staff, admin=request.user)
    subjects = Subject.objects.filter(staff_id=staff)
    sessions = Session.objects.all()
    context = {
        'subjects': subjects,
        'sessions': sessions,
        'page_title': 'Take Attendance'
    }

    return render(request, 'staff_template/staff_take_attendance.html', context)


@csrf_exempt
def get_students(request):
    subject_id = request.POST.get('subject')
    session_id = request.POST.get('session')
    try:
        subject = get_object_or_404(Subject, id=subject_id)
        session = get_object_or_404(Session, id=session_id)
        students = Student.objects.filter(
            course_id=subject.course.id, session=session)
        student_data = []
        for student in students:
            data = {
                    "id": student.id,
                    "name": f"{student.admin.last_name} {student.admin.first_name}, {student.registration_number}"
                    }
            student_data.append(data)
        return JsonResponse(json.dumps(student_data), content_type='application/json', safe=False)
    except Exception as e:
        return e


@csrf_exempt
def save_attendance(request):
    student_data = request.POST.get('student_ids')
    date       = request.POST.get('date')
    subject_id = request.POST.get('subject')
    session_id = request.POST.get('session')
    students   = json.loads(student_data)

    try:
        session = get_object_or_404(Session, id=session_id)
        subject = get_object_or_404(Subject, id=subject_id)

        # --- basic validation ---
        from datetime import datetime as dt
        parsed_date = dt.strptime(date, "%Y-%m-%d").date()
        today = dt.utcnow().date()
        if parsed_date > today:
            return HttpResponse("Future date not allowed", status=200)   # 200 so ajax shows it

        if Attendance.objects.filter(session=session, subject=subject, date=date).exists():
            return HttpResponse("Attendance already taken for this date", status=200)
        # --- end validation ---

        attendance = Attendance(session=session, subject=subject, date=date)
        attendance.save()

        for student_dict in students:
            student = get_object_or_404(Student, id=student_dict.get('id'))
            AttendanceReport.objects.create(
                student=student,
                attendance=attendance,
                status=student_dict.get('status')
            )
    except Exception as e:
        return HttpResponse(str(e), status=200)   # real error text

    return HttpResponse("OK")


def staff_update_attendance(request):
    staff = get_object_or_404(Staff, admin=request.user)
    subjects = Subject.objects.filter(staff_id=staff)
    sessions = Session.objects.all()
    context = {
        'subjects': subjects,
        'sessions': sessions,
        'page_title': 'Update Attendance'
    }

    return render(request, 'staff_template/staff_update_attendance.html', context)


@csrf_exempt
def get_student_attendance(request):
    attendance_date_id = request.POST.get('attendance_date_id')
    try:
        date = get_object_or_404(Attendance, id=attendance_date_id)
        attendance_data = AttendanceReport.objects.filter(attendance=date)
        student_data = []
        for attendance in attendance_data:
            data = {"id": attendance.student.admin.id,
                    "reg_no": attendance.student.registration_number,
                    "name": attendance.student.admin.last_name + " " + attendance.student.admin.first_name,
                    "status": attendance.status}
            student_data.append(data)
        return JsonResponse(json.dumps(student_data), content_type='application/json', safe=False)
    except Exception as e:
        import traceback
        traceback.print_exc()               # print full error to console
        return HttpResponse(str(e), status=500)

@csrf_exempt
def update_attendance(request):
    student_data = request.POST.get('student_ids')
    date = request.POST.get('date')
    students = json.loads(student_data)
    try:
        attendance = get_object_or_404(Attendance, id=date)

        for student_dict in students:
            student = get_object_or_404(
                Student, admin_id=student_dict.get('id'))
            attendance_report = get_object_or_404(AttendanceReport, student=student, attendance=attendance)
            attendance_report.status = student_dict.get('status')
            attendance_report.save()
    except Exception as e:
        return None

    return HttpResponse("OK")


def staff_apply_leave(request):
    form = LeaveReportStaffForm(request.POST or None)
    staff = get_object_or_404(Staff, admin_id=request.user.id)
    context = {
        'form': form,
        'leave_history': LeaveReportStaff.objects.filter(staff=staff),
        'page_title': 'Apply for Leave'
    }
    if request.method == 'POST':
        if form.is_valid():
            try:
                obj = form.save(commit=False)
                obj.staff = staff
                obj.save()
                            # ===== NOTIFY ALL ADMINS  =====
                from main_app.notification_service import NotificationService
                for admin_user in CustomUser.objects.filter(user_type=1):
                    NotificationService.create_notification(
                        recipient=admin_user,
                        notification_type='leave_staff',
                        title="New Staff Leave Request",
                        message=f"{staff.admin.get_full_name()} applied for leave on {obj.date}.",
                        sender=staff.admin,
                        related_id=obj.id
                    )
                messages.success(
                    request, "Application for leave has been submitted for review")
                return redirect(reverse('staff_apply_leave'))
            except Exception:
                messages.error(request, "Could not apply!")
        else:
            messages.error(request, "Form has errors!")
    return render(request, "staff_template/staff_apply_leave.html", context)


def staff_feedback(request):
    form = FeedbackStaffForm(request.POST or None)
    staff = get_object_or_404(Staff, admin_id=request.user.id)
    context = {
        'form': form,
        'feedbacks': FeedbackStaff.objects.filter(staff=staff),
        'page_title': 'Add Feedback'
    }
    if request.method == 'POST':
        if form.is_valid():
            try:
                obj = form.save(commit=False)
                obj.staff = staff
                obj.save()
                            # ===== NOTIFY ALL ADMINS  =====
                from main_app.notification_service import NotificationService
                for admin_user in CustomUser.objects.filter(user_type=1):
                    NotificationService.create_notification(
                        recipient=admin_user,
                        notification_type='feedback_staff',
                        title="New Staff Feedback",
                        message=f"{staff.admin.get_full_name()} submitted feedback.",
                        sender=staff.admin,
                        related_id=obj.id
                    )
                
                messages.success(request, "Feedback submitted for review")
                return redirect(reverse('staff_feedback'))
            except Exception:
                messages.error(request, "Could not Submit!")
        else:
            messages.error(request, "Form has errors!")
    return render(request, "staff_template/staff_feedback.html", context)


def staff_view_profile(request):
    staff = get_object_or_404(Staff, admin=request.user)
    form = StaffEditForm(request.POST or None, request.FILES or None, instance=staff)
    context = {
        'form': form,
        'staff': staff,                     # ← NEW
        'page_title': 'View/Update Profile'
    }
    if request.method == 'POST':
        try:
            if form.is_valid():
                first_name = form.cleaned_data.get('first_name')
                last_name = form.cleaned_data.get('last_name')
                password = form.cleaned_data.get('password') or None
                address = form.cleaned_data.get('address')
                gender = form.cleaned_data.get('gender')
                passport = request.FILES.get('profile_pic') or None
                admin = staff.admin
                if password != None:
                    admin.set_password(password)
                    admin.save() 
                if passport != None:
                    admin.profile_pic = passport
                admin.first_name = first_name
                admin.last_name = last_name
                admin.address = address
                admin.gender = gender
                admin.save()
                staff.phone = form.cleaned_data.get('phone', '')  # ← NEW
                staff.save()
                messages.success(request, "Profile Updated!")
                return redirect(reverse('staff_view_profile'))
            else:
                messages.error(request, "Invalid Data Provided")
                return render(request, "staff_template/staff_view_profile.html", context)
        except Exception as e:
            messages.error(request, "Error Occured While Updating Profile " + str(e))
            return render(request, "staff_template/staff_view_profile.html", context)

    return render(request, "staff_template/staff_view_profile.html", context)


@csrf_exempt
def staff_fcmtoken(request):
    token = request.POST.get('token')
    try:
        staff_user = get_object_or_404(CustomUser, id=request.user.id)
        staff_user.fcm_token = token
        staff_user.save()
        return HttpResponse("True")
    except Exception as e:
        return HttpResponse("False")


def staff_view_notification(request):
    staff = get_object_or_404(Staff, admin=request.user)
    notifications = NotificationStaff.objects.filter(staff=staff)
    context = {
        'notifications': notifications,
        'page_title': "View Notifications"
    }
    return render(request, "staff_template/staff_view_notification.html", context)


def staff_add_result(request):
    staff = get_object_or_404(Staff, admin=request.user)
    subjects = Subject.objects.filter(staff=staff)
    sessions   = Session.objects.all()

    # ----  NEW : send students to template  ----
    students = Student.objects.filter(
        course__in=subjects.values_list('course', flat=True)
    ).select_related('admin').order_by('admin__first_name', 'admin__last_name')

    context = {
        'page_title': 'Result Upload',
        'subjects'  : subjects,
        'sessions'  : sessions,
        'students'  : students,          # <-- added
    }

    if request.method == 'POST':
        try:
            student_id = request.POST.get('student_list')
            subject_id = request.POST.get('subject')
            test_raw   = request.POST.get('test')
            exam_raw   = request.POST.get('exam')

            # ----  NEW : 0-100 & numeric guard  ----
            def _clean_mark(val):
                try:
                    v = float(val)
                    if 0 <= v <= 100:
                        return v
                except (ValueError, TypeError):
                    pass
                return None

            test = _clean_mark(test_raw)
            exam = _clean_mark(exam_raw)
            if test is None or exam is None:
                messages.warning(request, "Test & Exam must be numbers between 0 and 100.")
                return render(request, "staff_template/staff_add_result.html", context)
            # ----------------------------------------

            student = get_object_or_404(Student, id=student_id)
            subject = get_object_or_404(Subject, id=subject_id)

            result, created = StudentResult.objects.update_or_create(
                student=student, subject=subject,
                defaults={'test': test, 'exam': exam}
            )
            msg = "Scores Saved" if created else "Scores Updated"
            messages.success(request, msg)

            # ===== DASHBOARD NOTIFICATION =====
            from .notification_service import NotificationService
            # ===== NOTIFY STAFF ITSELF  =====
            NotificationService.create_notification(
                recipient=request.user,
                notification_type='admin_notification',   # generic type for staff
                title="Result Saved" if created else "Result Updated",
                message=f"Result for {student.admin.get_full_name()} in {subject.name} has been saved.",
                sender=request.user,
                related_id=result.id
            )

        except Exception as e:
            messages.warning(request, "Error Occured While Processing Form")

    return render(request, "staff_template/staff_add_result.html", context)


@csrf_exempt
def fetch_student_result(request):
    """UNCHANGED – keep your original code exactly as it was"""
    try:
        subject_id = request.POST.get('subject')
        student_id = request.POST.get('student')
        student = get_object_or_404(Student, id=student_id)
        subject = get_object_or_404(Subject, id=subject_id)
        result = StudentResult.objects.get(student=student, subject=subject)
        result_data = {
            'exam': result.exam,
            'test': result.test
        }
        return HttpResponse(json.dumps(result_data))
    except Exception as e:
        return HttpResponse('False')