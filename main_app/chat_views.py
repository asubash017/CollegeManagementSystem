import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views import View
from .models import Student, Staff, Attendance, NotificationStudent, NotificationStaff, Subject, Course, Session, SystemSettings
from django.db.models import Q
try:
    import google.generativeai as genai
    HAS_GEMINI = True
except ImportError:
    HAS_GEMINI = False

class ChatService:
    def process_message(self, user, message):
        message = message.lower()
        settings = SystemSettings.objects.first()
        default_response = settings.chat_default_response if settings else "I didn't understand that."
        
        # Intent: Get Presets
        if message == "get_presets":
            presets = settings.preset_questions if settings else "Show my profile, Check attendance, Any notifications?"
            preset_list = [q.strip() for q in presets.split(',') if q.strip()]
            return {"presets": preset_list}

        if not user.is_authenticated:
            return {"message": "Please login to use the chat feature."}

        # Intent: Profile
        if "profile" in message or "who am i" in message:
            return self.get_profile_info(user)

        # Intent: Attendance
        elif "attendance" in message:
            return self.get_attendance_info(user)

        # Intent: Notifications
        elif "notification" in message or "alert" in message:
            return self.get_notifications(user)

        # Intent: Subjects / Courses
        elif "subject" in message or "course" in message:
            return self.get_academic_info(user)

        # Intent: Sessions
        elif "session" in message:
            return self.get_session_info()

        # Intent: Greeting
        elif "hello" in message or "hi" in message or "hey" in message:
             return {"message": f"Hello {user.first_name}! How can I assist you today?"}

        # Fallback: Gemini AI
        if settings and settings.gemini_api_key and HAS_GEMINI:
            try:
                genai.configure(api_key=settings.gemini_api_key)
                model = genai.GenerativeModel('gemini-pro')
                # Add context about the user
                context = f"You are a helpful assistant for a College Management System. The user is {user.first_name} {user.last_name} ({user.get_user_type_display()}). Answer the following question concisely: {message}"
                response = model.generate_content(context)
                return {"message": response.text}
            except Exception as e:
                print(f"Gemini Error: {e}")
                pass # Fallback to default

        return {"message": default_response}

    def get_profile_info(self, user):
        try:
            if str(user.user_type) == '3': # Student
                student = Student.objects.get(admin=user)
                return {
                    "message": f"**Name:** {user.first_name} {user.last_name}<br>**Role:** Student<br>**Course:** {student.course.name}<br>**Session:** {student.session.start_year} - {student.session.end_year}"
                }
            elif str(user.user_type) == '2': # Staff
                staff = Staff.objects.get(admin=user)
                return {
                    "message": f"**Name:** {user.first_name} {user.last_name}<br>**Role:** Staff<br>**Email:** {user.email}"
                }
            elif str(user.user_type) == '1': # HOD
                 return {
                    "message": f"**Name:** {user.first_name} {user.last_name}<br>**Role:** Administrator"
                }
        except Exception as e:
            return {"message": "Could not retrieve profile information."}
        return {"message": "Profile not found."}

    def get_attendance_info(self, user):
        if str(user.user_type) == '3': # Student
            try:
                student = Student.objects.get(admin=user)
                return {"message": "Please visit the **View Attendance** page for your detailed report."}
            except:
                pass
        return {"message": "Attendance data is only available for students via chat currently."}

    def get_notifications(self, user):
        notifications = []
        if str(user.user_type) == '3': # Student
            student = Student.objects.get(admin=user)
            notifs = NotificationStudent.objects.filter(student=student).order_by('-created_at')[:5]
            for n in notifs:
                notifications.append(f"- {n.message}")
        elif str(user.user_type) == '2': # Staff
            staff = Staff.objects.get(admin=user)
            notifs = NotificationStaff.objects.filter(staff=staff).order_by('-created_at')[:5]
            for n in notifs:
                notifications.append(f"- {n.message}")
        
        if notifications:
            return {"message": "<strong>Recent Notifications:</strong><br>" + "<br>".join(notifications)}
        else:
            return {"message": "No recent notifications."}

    def get_academic_info(self, user):
        if str(user.user_type) == '3': # Student
            try:
                student = Student.objects.get(admin=user)
                subjects = Subject.objects.filter(course=student.course)
                sub_list = [s.name for s in subjects]
                return {"message": f"<strong>Course:</strong> {student.course.name}<br><strong>Subjects:</strong><br>" + "<br>".join(sub_list)}
            except:
                pass
        elif str(user.user_type) == '2': # Staff
            try:
                staff = Staff.objects.get(admin=user)
                subjects = Subject.objects.filter(staff=staff)
                sub_list = [s.name for s in subjects]
                return {"message": f"<strong>Subjects you teach:</strong><br>" + "<br>".join(sub_list)}
            except:
                pass
        return {"message": "Academic info not found."}

    def get_session_info(self):
        sessions = Session.objects.all().order_by('-start_year')[:3]
        sess_list = [f"{s.start_year} to {s.end_year}" for s in sessions]
        return {"message": "<strong>Recent Sessions:</strong><br>" + "<br>".join(sess_list)}


@csrf_exempt
def chat_api(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            message = data.get('message', '')
            
            service = ChatService()
            response = service.process_message(request.user, message)
            
            return JsonResponse(response)
        except Exception as e:
            return JsonResponse({"message": "An error occurred."}, status=500)
    return JsonResponse({"message": "Invalid request method."}, status=400)
