import csv
import io
import json
import requests
from django.conf import settings
from django.contrib import messages
from django.core.files.storage import FileSystemStorage
from django.http import HttpResponse, JsonResponse
from django.shortcuts import (HttpResponse, HttpResponseRedirect,
                              get_object_or_404, redirect, render)
from django.templatetags.static import static
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import UpdateView


import qrcode
from io import BytesIO
import base64


from .forms import *
from .models import *


ADMIN_ROLE = '1'
STAFF_ROLE = '2'
STUDENT_ROLE = '3'
ROLE_LABELS = {
    ADMIN_ROLE: 'HOD / Admin',
    STAFF_ROLE: 'Staff',
    STUDENT_ROLE: 'Student'
}
INSTITUTION_NAME = getattr(settings, 'ID_CARD_INSTITUTION_NAME', 'College Management System')
DEFAULT_PROFILE_PIC = static('dist/img/default-150x150.png')
CSV_REQUIRED_FIELDS = {'first_name', 'last_name', 'email', 'gender', 'address'}
CSV_HEADER_ALIASES = {
    'first_name': {'first_name', 'firstname', 'first name'},
    'last_name': {'last_name', 'lastname', 'last name'},
    'email': {'email', 'email address', 'email_address'},
    'gender': {'gender', 'sex'},
    'address': {'address', 'home_address', 'home address'},
    'course': {'course', 'course_name', 'course name', 'courseid', 'course id'},
    'session': {'session', 'session_year', 'session year', 'sessionid', 'session id'},
    'password': {'password', 'pass', 'temp_password'},
    'profile_pic': {'profile_pic', 'profile picture', 'avatar', 'photo', 'profilepic'},
}


def _profile_photo_url(user):
    profile_pic = getattr(user, 'profile_pic', '')
    if not profile_pic:
        return DEFAULT_PROFILE_PIC

    try:
        if getattr(profile_pic, 'url', None):
            return profile_pic.url
    except ValueError:
        return DEFAULT_PROFILE_PIC

    return profile_pic


def _session_label(session):
    if not session:
        return None
    start_part = session.start_year.strftime("%Y") if session.start_year else ""
    end_part = session.end_year.strftime("%Y") if session.end_year else ""
    if start_part and end_part:
        return f"{start_part} - {end_part}"
    return start_part or end_part


def _build_id_card_payload(user):
    role_code = str(user.user_type)
    profile_data = {
        'full_name': f"{user.first_name} {user.last_name}".strip(),
        'role': user.get_user_type_display() if hasattr(user, 'get_user_type_display') else ROLE_LABELS.get(role_code, 'User'),
        'email': user.email,
        'gender': user.get_gender_display() if hasattr(user, 'get_user_type_display') else '',
        'address': user.address,
        'profile_pic': _profile_photo_url(user),
        'id_code': '',
        'course': None,
        'session': None,
        'extra_meta': None,
        'issued_on': timezone.now().strftime("%d %b %Y"),
        'institution': INSTITUTION_NAME,
    }

    if role_code == STUDENT_ROLE:
        student_profile = getattr(user, 'student', None)
        if student_profile:
            profile_data['course'] = getattr(student_profile.course, 'name', None)
            profile_data['session'] = _session_label(getattr(student_profile, 'session', None))
            profile_data['extra_meta'] = f"Reg. No: {student_profile.registration_number}"
        profile_data['id_code'] = f"CMP-S-{user.id:05d}"
    elif role_code == STAFF_ROLE:
        staff_profile = getattr(user, 'staff', None)
        if staff_profile:
            profile_data['course'] = getattr(staff_profile.course, 'name', None)
            profile_data['extra_meta'] = f"Staff ID: {staff_profile.staff_id_number}"
        profile_data['id_code'] = f"CMP-T-{user.id:05d}"
    else:
        admin_profile = getattr(user, 'admin', None)
        if admin_profile:
            profile_data['extra_meta'] = f"Admin ID: {admin_profile.admin_id_number}"
        profile_data['id_code'] = f"CMP-A-{user.id:05d}"

    return profile_data


def _filter_users_for_role(role_code, course_id=None, session_id=None):
    role_code = str(role_code)
    base_queryset = CustomUser.objects.filter(user_type=role_code).select_related(
        'staff__course', 'student__course', 'student__session'
    ).order_by('first_name', 'last_name')

    if role_code == STAFF_ROLE and course_id:
        base_queryset = base_queryset.filter(staff__course_id=course_id)
    if role_code == STUDENT_ROLE:
        if course_id:
            base_queryset = base_queryset.filter(student__course_id=course_id)
        if session_id:
            base_queryset = base_queryset.filter(student__session_id=session_id)

    return base_queryset


def _resolve_course(course_value):
    if not course_value:
        return None
    course_value = course_value.strip()
    if course_value.isdigit():
        return Course.objects.filter(id=int(course_value)).first()
    return Course.objects.filter(name__iexact=course_value).first()


def _resolve_session(session_value):
    if not session_value:
        return None
    value = session_value.strip()
    if not value:
        return None
    if value.isdigit():
        return Session.objects.filter(id=int(value)).first()
    parts = [part.strip() for part in value.replace('/', '-').split('-') if part.strip()]
    session_qs = Session.objects.all()
    if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
        session_qs = session_qs.filter(
            start_year__year=int(parts[0]),
            end_year__year=int(parts[1])
        )
    elif len(parts) == 1 and parts[0].isdigit():
        session_qs = session_qs.filter(start_year__year=int(parts[0]))
    else:
        session_qs = session_qs.none()
    return session_qs.first()


def _normalize_gender(value):
    if not value:
        return None
    normalized = value.strip().upper()
    if normalized.startswith('M'):
        return 'M'
    if normalized.startswith('F'):
        return 'F'
    return None


def _canonicalize_header(name):
    key = (name or '').strip().lower()
    if not key:
        return key
    for canonical, aliases in CSV_HEADER_ALIASES.items():
        if key == canonical or key in aliases:
            return canonical
    return key


def admin_home(request):
    total_staff = Staff.objects.all().count()
    total_students = Student.objects.all().count()
    subjects = Subject.objects.all()
    total_subject = subjects.count()
    total_course = Course.objects.all().count()
    attendance_list = Attendance.objects.filter(subject__in=subjects)
    total_attendance = attendance_list.count()
    attendance_list = []
    subject_list = []
    for subject in subjects:
        attendance_count = Attendance.objects.filter(subject=subject).count()
        subject_list.append(subject.name[:7])
        attendance_list.append(attendance_count)

    # Total Subjects and students in Each Course
    course_all = Course.objects.all()
    course_name_list = []
    subject_count_list = []
    student_count_list_in_course = []

    for course in course_all:
        subjects = Subject.objects.filter(course_id=course.id).count()
        students = Student.objects.filter(course_id=course.id).count()
        course_name_list.append(course.name)
        subject_count_list.append(subjects)
        student_count_list_in_course.append(students)
    
    subject_all = Subject.objects.all()
    subject_list = []
    student_count_list_in_subject = []
    for subject in subject_all:
        course = Course.objects.get(id=subject.course.id)
        student_count = Student.objects.filter(course_id=course.id).count()
        subject_list.append(subject.name)
        student_count_list_in_subject.append(student_count)


    # For Students
    student_attendance_present_list=[]
    student_attendance_leave_list=[]
    student_name_list=[]

    students = Student.objects.all()
    for student in students:
        
        attendance = AttendanceReport.objects.filter(student_id=student.id, status=True).count()
        absent = AttendanceReport.objects.filter(student_id=student.id, status=False).count()
        leave = LeaveReportStudent.objects.filter(student_id=student.id, status=1).count()
        student_attendance_present_list.append(attendance)
        student_attendance_leave_list.append(leave+absent)
        student_name_list.append(student.admin.first_name)

    context = {
        'page_title': "Administrative Dashboard",
        'total_students': total_students,
        'total_staff': total_staff,
        'total_course': total_course,
        'total_subject': total_subject,
        'subject_list': subject_list,
        'attendance_list': attendance_list,
        'student_attendance_present_list': student_attendance_present_list,
        'student_attendance_leave_list': student_attendance_leave_list,
        "student_name_list": student_name_list,
        "student_count_list_in_subject": student_count_list_in_subject,
        "student_count_list_in_course": student_count_list_in_course,
        "course_name_list": course_name_list,

    }
    return render(request, 'hod_template/home_content.html', context)



def _build_id_card_payload(user):
    """
    Build payload for ID card including QR code
    """
    payload = {
        'full_name': f"{user.first_name} {user.last_name}",
        'id_code': user.id,
        'email': user.email,
        'gender': user.gender,
        'address': user.address,
        'profile_pic': user.avatar_url,
        'course': getattr(user.student, 'course.name', '') if hasattr(user, 'student') else getattr(user.staff, 'course.name', ''),
        'session': f"{user.student.session.start_year}-{user.student.session.end_year}" if hasattr(user, 'student') and user.student.session else '',
        'institution': "College Management System",
        'issued_on': timezone.now().strftime("%d %b %Y"),
    }

    # QR code with user details
    qr_data = {
        "Name": payload['full_name'],
        "ID": payload['id_code'],
        "Email": payload['email'],
        "Role": ROLE_LABELS.get(str(user.user_type), "User"),
        "Course": payload['course'],
        "Session": payload['session']
    }
    payload['qr_code'] = generate_qr_code(qr_data)

    return payload


def id_card_generator(request):
    """
    Generate individual or bulk ID cards
    Excludes HOD/Admin roles
    """
    # Only staff and students
    staff_profiles = Staff.objects.select_related('admin', 'course').order_by('admin__first_name', 'admin__last_name')
    student_profiles = Student.objects.select_related('admin', 'course', 'session').order_by('admin__first_name', 'admin__last_name')
    courses = Course.objects.all().order_by('name')
    sessions = Session.objects.all().order_by('-start_year')

    if request.method == 'POST':
        generation_type = request.POST.get('generation_type', 'individual')
        role = request.POST.get('role')
        course_id = request.POST.get('course_id') or None
        session_id = request.POST.get('session_id') or None

        # Exclude HOD/Admin
        if role not in ROLE_LABELS or role == str(ADMIN_ROLE):
            messages.error(request, "HOD/Admin ID cards cannot be generated.")
            return redirect(reverse('id_card_generator'))

        if generation_type == 'individual':
            user_id = request.POST.get('user_id')
            if not user_id:
                messages.error(request, "Select a user to generate an ID card.")
                return redirect(reverse('id_card_generator'))
            selected_users = CustomUser.objects.filter(id=user_id, user_type=role)
        else:
            selected_users = _filter_users_for_role(role, course_id, session_id)

        selected_users = list(selected_users)
        if not selected_users:
            messages.error(request, "No records found for the selected filters.")
            return redirect(reverse('id_card_generator'))

        cards = [_build_id_card_payload(user) for user in selected_users]

        # Prepare summary of applied filters
        filter_summary = []
        if generation_type == 'bulk':
            if course_id:
                course_obj = next((course for course in courses if str(course.id) == str(course_id)), None)
                if course_obj:
                    filter_summary.append(f"Course: {course_obj.name}")
            if session_id and role == STUDENT_ROLE:
                session_obj = next((session for session in sessions if str(session.id) == str(session_id)), None)
                if session_obj:
                    filter_summary.append(f"Session: {_session_label(session_obj)}")

        preview_context = {
            'page_title': 'ID Card Preview',
            'cards': cards,
            'meta': {
                'mode': 'Individual' if generation_type == 'individual' else 'Bulk',
                'role': ROLE_LABELS.get(role, 'User'),
                'filter_summary': ", ".join(filter_summary) if filter_summary else "No additional filters",
                'total': len(cards),
                'generated_on': timezone.now().strftime("%d %b %Y, %I:%M %p"),
            },
        }
        return render(request, 'hod_template/id_card_preview.html', preview_context)

    # GET request: display generator page
    context = {
        'page_title': 'ID Card Generator',
        'role_labels': {k: v for k, v in ROLE_LABELS.items() if k != ADMIN_ROLE},  # Exclude HOD/Admin
        'staff_profiles': staff_profiles,
        'student_profiles': student_profiles,
        'courses': courses,
        'sessions': sessions,
    }
    return render(request, 'hod_template/id_card_generator.html', context)

def generate_qr_code(data_dict):
    """
    Generate a QR code as base64 string from a dictionary
    """
    qr = qrcode.QRCode(
        version=1,
        box_size=4,
        border=2
    )
    qr.add_data(data_dict)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    
    buffered = BytesIO()
    img.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue()).decode()
    return f"data:image/png;base64,{img_str}"



def data_tools(request):
    context = {
        'page_title': 'CSV Import / Export',
        'role_labels': ROLE_LABELS,
        'courses': Course.objects.all().order_by('name'),
        'sessions': Session.objects.all().order_by('-start_year'),
        'required_headers': [
            'first_name', 'last_name', 'email', 'gender', 'address',
            'phone',  # New field
            'course (staff & students)',
            'session (students only)',
            'registration_number (students only)',
            'staff_id_number (staff only)',
            'password (optional)'
        ]
    }
    return render(request, 'hod_template/data_tools.html', context)


def export_users_csv(request):
    role = request.GET.get('role')
    if role not in ROLE_LABELS:
        messages.error(request, "Select a valid role before exporting.")
        return redirect(reverse('data_tools'))

    course_id = request.GET.get('course_id') or None
    session_id = request.GET.get('session_id') or None
    queryset = _filter_users_for_role(role, course_id, session_id)
    if not queryset.exists():
        messages.error(request, "No records found for the selected filters.")
        return redirect(reverse('data_tools'))

    timestamp = timezone.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{ROLE_LABELS[role].lower().replace(' ', '_')}_export_{timestamp}.csv"
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    writer = csv.writer(response)
    # Headers with new fields
    writer.writerow([
        'Role', 'First Name', 'Last Name', 'Email', 'Gender', 'Address',
        'Phone', 'Course', 'Session', 'Registration Number', 'Staff ID', 'Extra Info', 'ID Code'
    ])

    for user in queryset:
        payload = _build_id_card_payload(user)
        phone = ''
        reg_no = ''
        staff_no = ''

        if user.user_type == STUDENT_ROLE:
            phone = getattr(user.student, 'phone', '')
            reg_no = getattr(user.student, 'registration_number', '')
        elif user.user_type == STAFF_ROLE:
            phone = getattr(user.staff, 'phone', '')
            staff_no = getattr(user.staff, 'staff_id_number', '')

        writer.writerow([
            payload['role'],
            user.first_name,
            user.last_name,
            user.email,
            payload['gender'],
            payload['address'],
            phone,
            payload['course'] or '',
            payload['session'] or '',
            reg_no,
            staff_no,
            payload['extra_meta'] or '',
            payload['id_code']
        ])

    return response


def import_users_csv(request):
    if request.method != 'POST':
        messages.error(request, "Invalid request method for CSV import.")
        return redirect(reverse('data_tools'))

    role = request.POST.get('role')
    if role not in ROLE_LABELS:
        messages.error(request, "Select a valid role before importing.")
        return redirect(reverse('data_tools'))

    csv_file = request.FILES.get('csv_file')
    if not csv_file:
        messages.error(request, "Please attach a CSV file to import.")
        return redirect(reverse('data_tools'))

    try:
        decoded_file = csv_file.read().decode('utf-8-sig')
    except UnicodeDecodeError:
        messages.error(request, "Unable to decode file. Please upload UTF-8 encoded CSV.")
        return redirect(reverse('data_tools'))

    reader = csv.DictReader(io.StringIO(decoded_file))
    if reader.fieldnames:
        reader.fieldnames = [_canonicalize_header(name) for name in reader.fieldnames]
    header_set = set(reader.fieldnames or [])
    if not header_set or not CSV_REQUIRED_FIELDS.issubset(header_set):
        messages.error(
            request,
            "CSV header must include first_name,last_name,email,gender,address (plus course/session/password/profile_pic where needed)."
        )
        return redirect(reverse('data_tools'))

    created = 0
    skipped = 0
    errors = []

    for line_number, row in enumerate(reader, start=2):
        if not row or not any(row.values()):
            continue

        try:
            email = (row.get('email') or '').strip().lower()
            first_name = (row.get('first_name') or '').strip()
            last_name = (row.get('last_name') or '').strip()
            gender = _normalize_gender(row.get('gender'))
            address = (row.get('address') or '').strip()
            phone = (row.get('phone') or '').strip()
            course_value = (row.get('course') or '').strip()
            session_value = (row.get('session') or '').strip()
            password = (row.get('password') or '').strip()
            profile_path = (row.get('profile_pic') or '').strip()
            registration_number = (row.get('registration_number') or '').strip()
            staff_id_number = (row.get('staff_id_number') or '').strip()

            if not email or not first_name or not last_name or not gender or not address:
                raise ValueError("Missing one of the required fields (first_name,last_name,email,gender,address).")

            if CustomUser.objects.filter(email=email).exists():
                skipped += 1
                continue

            course = None
            session = None
            if role in (STAFF_ROLE, STUDENT_ROLE):
                course = _resolve_course(course_value)
                if not course:
                    raise ValueError("Course column is required for this role and must match an existing course.")
            if role == STUDENT_ROLE:
                session = _resolve_session(session_value)
                if not session:
                    raise ValueError(
                        "Session column is required for students and must match an existing session (e.g. 2022-2023)."
                    )
                if not registration_number:
                    raise ValueError("Registration number is required for students.")

            if role == STAFF_ROLE and not staff_id_number:
                raise ValueError("Staff ID number is required for staff.")

            if not password:
                password = CustomUser.objects.make_random_password()

            user_kwargs = dict(
                email=email,
                password=password,
                user_type=int(role),
                first_name=first_name,
                last_name=last_name,
            )
            if profile_path:
                user_kwargs['profile_pic'] = profile_path
            user = CustomUser.objects.create_user(**user_kwargs)
            user.gender = gender
            user.address = address
            user.save()

            if role == STAFF_ROLE:
                user.staff.phone = phone
                user.staff.staff_id_number = staff_id_number
                if course:
                    user.staff.course = course
                user.staff.save()

            elif role == STUDENT_ROLE:
                user.student.phone = phone
                user.student.registration_number = registration_number
                if course:
                    user.student.course = course
                if session:
                    user.student.session = session
                user.student.save()

            created += 1

        except Exception as exc:
            errors.append(f"Line {line_number}: {exc}")

    if created:
        messages.success(request, f"Successfully imported {created} record(s).")
    if skipped:
        messages.warning(request, f"Skipped {skipped} duplicate email(s).")
    if errors:
        preview_errors = errors[:5]
        messages.error(request, "Some rows failed to import:\n" + "\n".join(preview_errors))

    return redirect(reverse('data_tools'))



def add_staff(request):
    form = StaffForm(request.POST or None, request.FILES or None)
    context = {'form': form, 'page_title': 'Add Staff'}
    if request.method == 'POST':
        if form.is_valid():
            first_name = form.cleaned_data.get('first_name')
            last_name = form.cleaned_data.get('last_name')
            address = form.cleaned_data.get('address')
            email = form.cleaned_data.get('email')
            gender = form.cleaned_data.get('gender')
            password = form.cleaned_data.get('password')
            course = form.cleaned_data.get('course')
            passport = request.FILES.get('profile_pic')
            passport_url = None
            if passport:
                fs = FileSystemStorage()
                filename = fs.save(passport.name, passport)
                passport_url = fs.url(filename)
            try:
                user_kwargs = dict(
                    email=email,
                    password=password,
                    user_type=2,
                    first_name=first_name,
                    last_name=last_name,
                )
                if passport_url:
                    user_kwargs['profile_pic'] = passport_url
                user = CustomUser.objects.create_user(**user_kwargs)
                user.gender = gender
                user.address = address
                user.staff.course = course
                user.save()
                messages.success(request, "Successfully Added")
                return redirect(reverse('add_staff'))

            except Exception as e:
                messages.error(request, "Could Not Add " + str(e))
        else:
            messages.error(request, "Please fulfil all requirements")

    return render(request, 'hod_template/add_staff_template.html', context)


def add_student(request):
    student_form = StudentForm(request.POST or None, request.FILES or None)
    context = {'form': student_form, 'page_title': 'Add Student'}
    if request.method == 'POST':
        if student_form.is_valid():
            first_name = student_form.cleaned_data.get('first_name')
            last_name = student_form.cleaned_data.get('last_name')
            address = student_form.cleaned_data.get('address')
            email = student_form.cleaned_data.get('email')
            gender = student_form.cleaned_data.get('gender')
            password = student_form.cleaned_data.get('password')
            course = student_form.cleaned_data.get('course')
            session = student_form.cleaned_data.get('session')
            passport = request.FILES.get('profile_pic')
            passport_url = None
            if passport:
                fs = FileSystemStorage()
                filename = fs.save(passport.name, passport)
                passport_url = fs.url(filename)
            try:
                user_kwargs = dict(
                    email=email,
                    password=password,
                    user_type=3,
                    first_name=first_name,
                    last_name=last_name,
                )
                if passport_url:
                    user_kwargs['profile_pic'] = passport_url
                user = CustomUser.objects.create_user(**user_kwargs)
                user.gender = gender
                user.address = address
                user.student.session = session
                user.student.course = course
                user.save()
                messages.success(request, "Successfully Added")
                return redirect(reverse('add_student'))
            except Exception as e:
                messages.error(request, "Could Not Add: " + str(e))
        else:
            messages.error(request, "Could Not Add: ")
    return render(request, 'hod_template/add_student_template.html', context)


def add_course(request):
    form = CourseForm(request.POST or None)
    context = {
        'form': form,
        'page_title': 'Add Course'
    }
    if request.method == 'POST':
        if form.is_valid():
            name = form.cleaned_data.get('name')
            try:
                course = Course()
                course.name = name
                course.save()
                messages.success(request, "Successfully Added")
                return redirect(reverse('add_course'))
            except:
                messages.error(request, "Could Not Add")
        else:
            messages.error(request, "Could Not Add")
    return render(request, 'hod_template/add_course_template.html', context)


def add_subject(request):
    form = SubjectForm(request.POST or None)
    context = {
        'form': form,
        'page_title': 'Add Subject'
    }
    if request.method == 'POST':
        if form.is_valid():
            name = form.cleaned_data.get('name')
            course = form.cleaned_data.get('course')
            staff = form.cleaned_data.get('staff')
            try:
                subject = Subject()
                subject.name = name
                subject.staff = staff
                subject.course = course
                subject.save()
                messages.success(request, "Successfully Added")
                return redirect(reverse('add_subject'))

            except Exception as e:
                messages.error(request, "Could Not Add " + str(e))
        else:
            messages.error(request, "Fill Form Properly")

    return render(request, 'hod_template/add_subject_template.html', context)


def manage_staff(request):
    allStaff = CustomUser.objects.filter(user_type=2)
    form = StaffForm(request.POST or None, request.FILES or None)
    context = {
        'allStaff': allStaff,
        'form': form,
        'page_title': 'Manage Staff'
    }
    if request.method == 'POST':
        if form.is_valid():
            first_name = form.cleaned_data.get('first_name')
            last_name = form.cleaned_data.get('last_name')
            address = form.cleaned_data.get('address')
            email = form.cleaned_data.get('email')
            gender = form.cleaned_data.get('gender')
            password = form.cleaned_data.get('password')
            course = form.cleaned_data.get('course')
            passport = request.FILES.get('profile_pic')
            passport_url = None
            if passport:
                fs = FileSystemStorage()
                filename = fs.save(passport.name, passport)
                passport_url = fs.url(filename)
            try:
                user_kwargs = dict(
                    email=email,
                    password=password,
                    user_type=2,
                    first_name=first_name,
                    last_name=last_name,
                )
                if passport_url:
                    user_kwargs['profile_pic'] = passport_url
                user = CustomUser.objects.create_user(**user_kwargs)
                user.gender = gender
                user.address = address
                user.staff.course = course
                user.save()
                messages.success(request, "Successfully Added")
                return redirect(reverse('manage_staff'))

            except Exception as e:
                messages.error(request, "Could Not Add " + str(e))
        else:
            messages.error(request, "Please fulfil all requirements")
    return render(request, "hod_template/manage_staff.html", context)


def manage_student(request):
    students = CustomUser.objects.filter(user_type=3)
    form = StudentForm(request.POST or None, request.FILES or None)
    context = {
        'students': students,
        'form': form,
        'page_title': 'Manage Students'
    }
    if request.method == 'POST':
        if form.is_valid():
            first_name = form.cleaned_data.get('first_name')
            last_name = form.cleaned_data.get('last_name')
            address = form.cleaned_data.get('address')
            email = form.cleaned_data.get('email')
            gender = form.cleaned_data.get('gender')
            password = form.cleaned_data.get('password')
            course = form.cleaned_data.get('course')
            session = form.cleaned_data.get('session')
            passport = request.FILES.get('profile_pic')
            passport_url = None
            if passport:
                fs = FileSystemStorage()
                filename = fs.save(passport.name, passport)
                passport_url = fs.url(filename)
            try:
                user_kwargs = dict(
                    email=email,
                    password=password,
                    user_type=3,
                    first_name=first_name,
                    last_name=last_name,
                )
                if passport_url:
                    user_kwargs['profile_pic'] = passport_url
                user = CustomUser.objects.create_user(**user_kwargs)
                user.gender = gender
                user.address = address
                user.student.session = session
                user.student.course = course
                user.save()
                messages.success(request, "Successfully Added")
                return redirect(reverse('manage_student'))
            except Exception as e:
                messages.error(request, "Could Not Add: " + str(e))
        else:
            messages.error(request, "Could Not Add: ")
    return render(request, "hod_template/manage_student.html", context)


def manage_course(request):
    courses = Course.objects.all()
    context = {
        'courses': courses,
        'page_title': 'Manage Courses'
    }
    return render(request, "hod_template/manage_course.html", context)


def manage_subject(request):
    subjects = Subject.objects.all()
    context = {
        'subjects': subjects,
        'page_title': 'Manage Subjects'
    }
    return render(request, "hod_template/manage_subject.html", context)


def edit_staff(request, staff_id):
    staff = get_object_or_404(Staff, id=staff_id)
    form = StaffForm(request.POST or None, instance=staff)
    context = {
        'form': form,
        'staff_id': staff_id,
        'page_title': 'Edit Staff'
    }
    if request.method == 'POST':
        if form.is_valid():
            first_name = form.cleaned_data.get('first_name')
            last_name = form.cleaned_data.get('last_name')
            address = form.cleaned_data.get('address')
            username = form.cleaned_data.get('username')
            email = form.cleaned_data.get('email')
            gender = form.cleaned_data.get('gender')
            password = form.cleaned_data.get('password') or None
            course = form.cleaned_data.get('course')
            passport = request.FILES.get('profile_pic') or None
            try:
                user = CustomUser.objects.get(id=staff.admin.id)
                user.username = username
                user.email = email
                if password != None:
                    user.set_password(password)
                if passport != None:
                    fs = FileSystemStorage()
                    filename = fs.save(passport.name, passport)
                    passport_url = fs.url(filename)
                    user.profile_pic = passport_url
                user.first_name = first_name
                user.last_name = last_name
                user.gender = gender
                user.address = address
                staff.course = course
                user.save()
                staff.save()
                messages.success(request, "Successfully Updated")
                return redirect(reverse('edit_staff', args=[staff_id]))
            except Exception as e:
                messages.error(request, "Could Not Update " + str(e))
        else:
            messages.error(request, "Please fil form properly")
    else:
        user = CustomUser.objects.get(id=staff_id)
        staff = Staff.objects.get(id=user.id)
        return render(request, "hod_template/edit_staff_template.html", context)


def edit_student(request, student_id):
    student = get_object_or_404(Student, id=student_id)
    form = StudentForm(request.POST or None, instance=student)
    context = {
        'form': form,
        'student_id': student_id,
        'page_title': 'Edit Student'
    }
    if request.method == 'POST':
        if form.is_valid():
            first_name = form.cleaned_data.get('first_name')
            last_name = form.cleaned_data.get('last_name')
            address = form.cleaned_data.get('address')
            username = form.cleaned_data.get('username')
            email = form.cleaned_data.get('email')
            gender = form.cleaned_data.get('gender')
            password = form.cleaned_data.get('password') or None
            course = form.cleaned_data.get('course')
            session = form.cleaned_data.get('session')
            passport = request.FILES.get('profile_pic') or None
            try:
                user = CustomUser.objects.get(id=student.admin.id)
                if passport != None:
                    fs = FileSystemStorage()
                    filename = fs.save(passport.name, passport)
                    passport_url = fs.url(filename)
                    user.profile_pic = passport_url
                user.username = username
                user.email = email
                if password != None:
                    user.set_password(password)
                user.first_name = first_name
                user.last_name = last_name
                student.session = session
                user.gender = gender
                user.address = address
                student.course = course
                user.save()
                student.save()
                messages.success(request, "Successfully Updated")
                return redirect(reverse('edit_student', args=[student_id]))
            except Exception as e:
                messages.error(request, "Could Not Update " + str(e))
        else:
            messages.error(request, "Please Fill Form Properly!")
    else:
        return render(request, "hod_template/edit_student_template.html", context)



def edit_course(request, course_id):
    instance = get_object_or_404(Course, id=course_id)
    form = CourseForm(request.POST or None, instance=instance)
    context = {
        'form': form,
        'course_id': course_id,
        'page_title': 'Edit Course'
    }
    if request.method == 'POST':
        if form.is_valid():
            name = form.cleaned_data.get('name')
            try:
                course = Course.objects.get(id=course_id)
                course.name = name
                course.save()
                messages.success(request, "Successfully Updated")
            except:
                messages.error(request, "Could Not Update")
        else:
            messages.error(request, "Could Not Update")

    return render(request, 'hod_template/edit_course_template.html', context)


def edit_subject(request, subject_id):
    instance = get_object_or_404(Subject, id=subject_id)
    form = SubjectForm(request.POST or None, instance=instance)
    context = {
        'form': form,
        'subject_id': subject_id,
        'page_title': 'Edit Subject'
    }
    if request.method == 'POST':
        if form.is_valid():
            name = form.cleaned_data.get('name')
            course = form.cleaned_data.get('course')
            staff = form.cleaned_data.get('staff')
            try:
                subject = Subject.objects.get(id=subject_id)
                subject.name = name
                subject.staff = staff
                subject.course = course
                subject.save()
                messages.success(request, "Successfully Updated")
                return redirect(reverse('edit_subject', args=[subject_id]))
            except Exception as e:
                messages.error(request, "Could Not Add " + str(e))
        else:
            messages.error(request, "Fill Form Properly")
    return render(request, 'hod_template/edit_subject_template.html', context)


def add_session(request):
    form = SessionForm(request.POST or None)
    context = {'form': form, 'page_title': 'Add Session'}
    if request.method == 'POST':
        if form.is_valid():
            try:
                form.save()
                messages.success(request, "Session Created")
                return redirect(reverse('add_session'))
            except Exception as e:
                messages.error(request, 'Could Not Add ' + str(e))
        else:
            messages.error(request, 'Fill Form Properly ')
    return render(request, "hod_template/add_session_template.html", context)


def manage_session(request):
    sessions = Session.objects.all()
    context = {'sessions': sessions, 'page_title': 'Manage Sessions'}
    return render(request, "hod_template/manage_session.html", context)


def edit_session(request, session_id):
    instance = get_object_or_404(Session, id=session_id)
    form = SessionForm(request.POST or None, instance=instance)
    context = {'form': form, 'session_id': session_id,
               'page_title': 'Edit Session'}
    if request.method == 'POST':
        if form.is_valid():
            try:
                form.save()
                messages.success(request, "Session Updated")
                return redirect(reverse('edit_session', args=[session_id]))
            except Exception as e:
                messages.error(
                    request, "Session Could Not Be Updated " + str(e))
                return render(request, "hod_template/edit_session_template.html", context)
        else:
            messages.error(request, "Invalid Form Submitted ")
            return render(request, "hod_template/edit_session_template.html", context)

    else:
        return render(request, "hod_template/edit_session_template.html", context)


@csrf_exempt
def check_email_availability(request):
    email = request.POST.get("email")
    try:
        user = CustomUser.objects.filter(email=email).exists()
        if user:
            return HttpResponse(True)
        return HttpResponse(False)
    except Exception as e:
        return HttpResponse(False)


@csrf_exempt
def manage_feedback(request):
    if request.method != 'POST':
        student_feedbacks = FeedbackStudent.objects.all()
        staff_feedbacks = FeedbackStaff.objects.all()
        context = {
            'student_feedbacks': student_feedbacks,
            'staff_feedbacks': staff_feedbacks,
            'page_title': 'Manage Feedback'
        }
        return render(request, 'hod_template/manage_feedback.html', context)
    else:
        feedback_id = request.POST.get('id')
        reply = request.POST.get('reply')
        type = request.POST.get('type')
        try:
            if type == 'student':
                feedback = get_object_or_404(FeedbackStudent, id=feedback_id)
            else:
                feedback = get_object_or_404(FeedbackStaff, id=feedback_id)
            feedback.reply = reply
            feedback.save()
            # ===== DASHBOARD NOTIFICATION =====
            from .notification_service import NotificationService
            NotificationService.create_notification(
                recipient=feedback.student.admin if type == 'student' else feedback.staff.admin,
                notification_type='feedback_reply',
                title="Feedback Reply",
                message=f"Admin replied to your feedback: {reply[:50]}...",
                sender=request.user,
                related_id=feedback.id
            )
            return HttpResponse(True)
        except Exception as e:
            return HttpResponse(False)

@csrf_exempt
def manage_leave(request):
    if request.method != 'POST':
        student_leave = LeaveReportStudent.objects.all()
        staff_leave = LeaveReportStaff.objects.all()
        context = {
            'student_leave': student_leave,
            'staff_leave': staff_leave,
            'page_title': 'Manage Leave Applications'
        }
        return render(request, "hod_template/manage_leave.html", context)
    else:
        id = request.POST.get('id')
        status = request.POST.get('status')
        type = request.POST.get('type')
        if (status == '1'):
            status = 1
        else:
            status = -1
        try:
            if type == 'student':
                leave = get_object_or_404(LeaveReportStudent, id=id)
            else:
                leave = get_object_or_404(LeaveReportStaff, id=id)
            leave.status = status
            leave.save()
            # ===== DASHBOARD NOTIFICATION =====
            from .notification_service import NotificationService
            NotificationService.create_notification(
                recipient=leave.student.admin if type == 'student' else leave.staff.admin,
                notification_type='leave_reply',
                title="Leave Request " + ("Approved" if status == 1 else "Rejected"),
                message=f"Your leave request has been {('approved' if status == 1 else 'rejected')}.",
                sender=request.user,
                related_id=leave.id
            )
            return HttpResponse(True)
        except Exception as e:
            return False


def admin_view_attendance(request):
    subjects = Subject.objects.all()
    sessions = Session.objects.all()
    context = {
        'subjects': subjects,
        'sessions': sessions,
        'page_title': 'View Attendance'
    }

    return render(request, "hod_template/admin_view_attendance.html", context)


@csrf_exempt
def get_admin_attendance(request):
    subject_id = request.POST.get('subject')
    session_id = request.POST.get('session')
    attendance_date_id = request.POST.get('attendance_date_id')
    try:
        subject = get_object_or_404(Subject, id=subject_id)
        session = get_object_or_404(Session, id=session_id)
        attendance = get_object_or_404(
            Attendance, id=attendance_date_id, session=session)
        attendance_reports = AttendanceReport.objects.filter(
            attendance=attendance)
        json_data = []
        for report in attendance_reports:
            data = {
                "reg_no": report.student.registration_number,
                "status": str(report.status),
                "name": str(report.student)
            }
            json_data.append(data)
        return JsonResponse(json.dumps(json_data), safe=False)
    except Exception as e:
        return None


def admin_view_profile(request):
    admin = get_object_or_404(Admin, admin=request.user)
    form = AdminForm(request.POST or None, request.FILES or None, instance=admin)
    context = {
        'form': form,
        'admin': admin,                     # ← NEW
        'page_title': 'View/Edit Profile'
    }
    if request.method == 'POST':
        try:
            if form.is_valid():
                first_name = form.cleaned_data.get('first_name')
                last_name = form.cleaned_data.get('last_name')
                password = form.cleaned_data.get('password') or None
                passport = request.FILES.get('profile_pic') or None
                custom_user = admin.admin
                if password != None:
                    custom_user.set_password(password)
                if passport != None:
                    custom_user.profile_pic = passport
                custom_user.first_name = first_name
                custom_user.last_name = last_name
                custom_user.address = form.cleaned_data.get('address', '')
                custom_user.save()
                admin.phone = form.cleaned_data.get('phone', '')  # ← NEW
                admin.save()
                messages.success(request, "Profile Updated!")
                return redirect(reverse('admin_view_profile'))
            else:
                messages.error(request, "Invalid Data Provided")
        except Exception as e:
            messages.error(request, "Error Occured While Updating Profile " + str(e))
    return render(request, "hod_template/admin_view_profile.html", context)

def admin_notify_users(request):
    staff = CustomUser.objects.filter(user_type=STAFF_ROLE).select_related('staff__course')
    students = CustomUser.objects.filter(user_type=STUDENT_ROLE).select_related('student__course', 'student__session')
    context = {
        'page_title': "Send Notifications",
        'allStaff': staff,
        'students': students,
    }
    return render(request, "hod_template/notify_users.html", context)


def admin_notify_staff(request):
    return redirect(reverse('admin_notify_users'))


def admin_notify_student(request):
    return redirect(reverse('admin_notify_users'))


@csrf_exempt
def send_student_notification(request):
    id = request.POST.get('id')
    message = request.POST.get('message')
    student = get_object_or_404(Student, admin_id=id)
    try:
        url = "https://fcm.googleapis.com/fcm/send "
        body = {
            'notification': {
                'title': "Student Management System",
                'body': message,
                'click_action': reverse('student_view_notification'),
                'icon': static('dist/img/AdminLTELogo.png')
            },
            'to': student.admin.fcm_token
        }
        headers = {'Authorization':
                   'key=AAAA3Bm8j_M:APA91bElZlOLetwV696SoEtgzpJr2qbxBfxVBfDWFiopBWzfCfzQp2nRyC7_A2mlukZEHV4g1AmyC6P_HonvSkY2YyliKt5tT3fe_1lrKod2Daigzhb2xnYQMxUWjCAIQcUexAMPZePB',
                   'Content-Type': 'application/json'}
        data = requests.post(url, data=json.dumps(body), headers=headers)
        notification = NotificationStudent(student=student, message=message)
        notification.save()
        # ===== DASHBOARD NOTIFICATION =====
        from .notification_service import NotificationService
        NotificationService.create_notification(
            recipient=student.admin,
            notification_type='admin_notification',
            title="Admin Notification",
            message=message,
            sender=request.user
        )
        return HttpResponse("True")
    except Exception as e:
        return HttpResponse("False")


@csrf_exempt
def send_staff_notification(request):
    id = request.POST.get('id')
    message = request.POST.get('message')
    staff = get_object_or_404(Staff, admin_id=id)
    try:
        url = "https://fcm.googleapis.com/fcm/send"
        body = {
            'notification': {
                'title': "Student Management System",
                'body': message,
                'click_action': reverse('staff_view_notification'),
                'icon': static('dist/img/AdminLTELogo.png')
            },
            'to': staff.admin.fcm_token
        }
        headers = {'Authorization':
                   'key=AAAA3Bm8j_M:APA91bElZlOLetwV696SoEtgzpJr2qbxBfxVBfDWFiopBWzfCfzQp2nRyC7_A2mlukZEHV4g1AmyC6P_HonvSkY2YyliKt5tT3fe_1lrKod2Daigzhb2xnYQMxUWjCAIQcUexAMPZePB',
                   'Content-Type': 'application/json'}
        data = requests.post(url, data=json.dumps(body), headers=headers)
        notification = NotificationStaff(staff=staff, message=message)
        notification.save()
                # ----  DASHBOARD NOTIFICATION  ----
        from .notification_service import NotificationService
        NotificationService.create_notification(
            recipient=staff.admin,
            notification_type='admin_notification',
            title="Admin Notification",
            message=message,
            sender=request.user
        )
        return HttpResponse("True")
    except Exception as e:
        return HttpResponse("False")


def delete_staff(request, staff_id):
    staff = get_object_or_404(CustomUser, staff__id=staff_id)
    staff.delete()
    messages.success(request, "Staff deleted successfully!")
    return redirect(reverse('manage_staff'))


def delete_student(request, student_id):
    student = get_object_or_404(CustomUser, student__id=student_id)
    student.delete()
    messages.success(request, "Student deleted successfully!")
    return redirect(reverse('manage_student'))


def delete_course(request, course_id):
    course = get_object_or_404(Course, id=course_id)
    try:
        course.delete()
        messages.success(request, "Course deleted successfully!")
    except Exception:
        messages.error(
            request, "Sorry, some students are assigned to this course already. Kindly change the affected student course and try again")
    return redirect(reverse('manage_course'))


def delete_subject(request, subject_id):
    subject = get_object_or_404(Subject, id=subject_id)
    subject.delete()
    messages.success(request, "Subject deleted successfully!")
    return redirect(reverse('manage_subject'))


def delete_session(request, session_id):
    session = get_object_or_404(Session, id=session_id)
    try:
        session.delete()
        messages.success(request, "Session deleted successfully!")
    except Exception:
        messages.error(
            request, "There are students assigned to this session. Please move them to another session.")
    return redirect(reverse('manage_session'))
