import json
import logging
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .models import (
    Student, Staff, Admin, Attendance, AttendanceReport,
    NotificationStudent, NotificationStaff, Subject, Course, 
    Session, SystemSettings, LeaveReportStudent, LeaveReportStaff,
    StudentResult
)

try:
    import google.generativeai as genai
    HAS_GEMINI = True
except ImportError:
    HAS_GEMINI = False

logger = logging.getLogger(__name__)

class EnhancedChatService:
    def __init__(self):
        self.system_settings = SystemSettings.objects.first()
    
    def process_message(self, user, message):
        """Enhanced message processing with strict access control"""
        try:
            message = message.lower().strip()
            
            # Get presets
            if message == "get_presets":
                return self.get_presets()
            
            if not user.is_authenticated:
                return {"message": "🔒 Please login to use the chat feature.", "type": "error"}
            
            user_type = str(user.user_type)
            
            if user_type == '1':  # Admin/HOD
                return self.handle_admin_queries(user, message)
            elif user_type == '2':  # Staff
                return self.handle_staff_queries(user, message)
            elif user_type == '3':  # Student
                return self.handle_student_queries(user, message)
            else:
                return {"message": "❌ Invalid user type.", "type": "error"}
                
        except Exception as e:
            logger.error(f"Chatbot error for user {user.email}: {str(e)}")
            return {"message": "❌ An error occurred processing your message.", "type": "error"}
    
    def get_presets(self):
        """Get preset questions"""
        if not self.system_settings:
            return {"presets": ["Show my profile", "Check attendance", "Any notifications?"]}
        
        base_presets = [q.strip() for q in self.system_settings.preset_questions.split(',') if q.strip()]
        return {"presets": base_presets}
    
    def handle_admin_queries(self, user, message):
        """Handle admin-specific queries"""
        
        # Profile information
        if any(word in message for word in ['profile', 'my info', 'my details', 'who am i']):
            return self.get_enhanced_profile_info(user)
        
        # System overview
        elif any(word in message for word in ['overview', 'dashboard', 'summary', 'system']):
            return self.get_system_overview()
        
        # User management
        elif any(word in message for word in ['students', 'student count', 'total students']):
            count = Student.objects.count()
            return {"message": f"📊 **Total Students:** {count}", "type": "info"}
        
        elif any(word in message for word in ['staff', 'teachers', 'faculty count']):
            count = Staff.objects.count()
            return {"message": f"📊 **Total Staff:** {count}", "type": "info"}
        
        # Session info - FIXED
        elif any(word in message for word in ['session', 'academic year', 'year']):
            return self.get_session_info(user)
        
        # Help
        elif any(word in message for word in ['help', 'assist', 'support']):
            return self.get_help_response(user)
        
        # Greeting
        elif any(word in message for word in ['hello', 'hi', 'hey']):
            return {"message": f"👋 Hello {user.first_name}! As an administrator, you have full system access. How can I assist you?", "type": "greeting"}
        
        # Fallback to AI
        else:
            return self.get_ai_response(user, message)
    
    def handle_staff_queries(self, user, message):
        """Handle staff-specific queries"""
        
        # Profile information
        if any(word in message for word in ['profile', 'my info', 'my details', 'who am i']):
            return self.get_enhanced_profile_info(user)
        
        # Attendance management
        elif any(word in message for word in ['attendance', 'my attendance']):
            return self.get_staff_attendance_info(user)
        
        # Subjects taught
        elif any(word in message for word in ['subjects', 'courses', 'what i teach', 'academic']):
            return self.get_enhanced_academic_info(user)
        
        # Session info - FIXED
        elif any(word in message for word in ['session', 'academic year', 'year']):
            return self.get_session_info(user)
        
        # Notifications
        elif any(word in message for word in ['notification', 'alert', 'message']):
            return self.get_enhanced_notifications(user)
        
        # Leave status
        elif any(word in message for word in ['leave', 'time off']):
            return self.get_staff_leave_status(user)
        
        # Help - FIXED
        elif any(word in message for word in ['help', 'assist', 'support']):
            return self.get_help_response(user)
        
        # Greeting
        elif any(word in message for word in ['hello', 'hi', 'hey']):
            return {"message": f"👋 Hello {user.first_name}! How can I help you with your teaching responsibilities?", "type": "greeting"}
        
        # Fallback to AI
        else:
            return self.get_ai_response(user, message)
    
    def handle_student_queries(self, user, message):
        """Handle student-specific queries with improved patterns"""
        
        # Profile information
        if any(word in message for word in ['profile', 'my info', 'my details', 'who am i']):
            return self.get_enhanced_profile_info(user)
        
        # Attendance
        elif any(word in message for word in ['attendance', 'my attendance']):
            return self.get_enhanced_attendance_info(user)
        
        # Results/Grades
        elif any(word in message for word in ['result', 'grade', 'marks', 'score', 'performance']):
            return self.get_student_results(user)
        
        # Subjects/Academic info - IMPROVED
        elif any(word in message for word in ['subjects', 'courses', 'my subjects', 'academic', 'subject']):
            return self.get_enhanced_academic_info(user)
        
        # Session/Academic year - IMPROVED & FIXED
        elif any(word in message for word in ['session', 'academic year', 'year', 'semester', 'term']):
            return self.get_session_info(user)
        
        # Notifications
        elif any(word in message for word in ['notification', 'alert', 'message']):
            return self.get_enhanced_notifications(user)
        
        # Leave status
        elif any(word in message for word in ['leave', 'time off', 'vacation']):
            return self.get_student_leave_status(user)
        
        # Help - FIXED
        elif any(word in message for word in ['help', 'assist', 'support', 'what can you do']):
            return self.get_help_response(user)
        
        # Greeting
        elif any(word in message for word in ['hello', 'hi', 'hey']):
            return {"message": f"👋 Hello {user.first_name}! How can I help you with your academic information?", "type": "greeting"}
        
        # Fallback to AI
        else:
            return self.get_ai_response(user, message)
    
    def get_enhanced_profile_info(self, user):
        """Get enhanced profile information with new contact fields"""
        try:
            user_type = str(user.user_type)
            
            if user_type == '3':  # Student
                student = Student.objects.select_related('course', 'session').get(admin=user)
                
                phone_display = student.phone if student.phone else "📵 Not provided"
                reg_display = student.registration_number if student.registration_number else "📝 Not assigned"
                
                profile_info = {
                    "message": (
                        f"🎓 **Student Profile**\n\n"
                        f"**Name:** {user.first_name} {user.last_name}\n"
                        f"**Email:** {user.email}\n"
                        f"**Registration No:** {reg_display}\n"
                        f"**Phone:** {phone_display}\n"
                        f"**Gender:** {user.get_gender_display()}\n"
                        f"**Course:** {student.course.name if student.course else '❌ Not assigned'}\n"
                        f"**Session:** {student.session.start_year.year}-{student.session.end_year.year if student.session else '❌ Not assigned'}\n"
                        f"**Role:** Student"
                    ),
                    "type": "profile"
                }
                
            elif user_type == '2':  # Staff
                staff = Staff.objects.select_related('course').get(admin=user)
                
                phone_display = staff.phone if staff.phone else "📵 Not provided"
                staff_id_display = staff.staff_id_number if staff.staff_id_number else "📝 Not assigned"
                
                profile_info = {
                    "message": (
                        f"👨‍🏫 **Staff Profile**\n\n"
                        f"**Name:** {user.first_name} {user.last_name}\n"
                        f"**Email:** {user.email}\n"
                        f"**Staff ID:** {staff_id_display}\n"
                        f"**Phone:** {phone_display}\n"
                        f"**Gender:** {user.get_gender_display()}\n"
                        f"**Course:** {staff.course.name if staff.course else '❌ Not assigned'}\n"
                        f"**Role:** Teaching Staff"
                    ),
                    "type": "profile"
                }
                
            elif user_type == '1':  # Admin
                admin = Admin.objects.get(admin=user)
                
                phone_display = admin.phone if admin.phone else "📵 Not provided"
                admin_id_display = admin.admin_id_number if admin.admin_id_number else "📝 Not assigned"
                
                profile_info = {
                    "message": (
                        f"👤 **Administrator Profile**\n\n"
                        f"**Name:** {user.first_name} {user.last_name}\n"
                        f"**Email:** {user.email}\n"
                        f"**Admin ID:** {admin_id_display}\n"
                        f"**Phone:** {phone_display}\n"
                        f"**Gender:** {user.get_gender_display()}\n"
                        f"**Role:** Head of Department\n"
                        f"**Permissions:** Full system access"
                    ),
                    "type": "profile"
                }
            
            return profile_info
            
        except (Student.DoesNotExist, Staff.DoesNotExist, Admin.DoesNotExist):
            return {"message": "❌ Profile not found. Please contact administrator.", "type": "error"}
        except Exception as e:
            logger.error(f"Error getting enhanced profile for {user.email}: {str(e)}")
            return {"message": "❌ Error retrieving profile information.", "type": "error"}

    def get_session_info(self, user):
        """FIXED: Get session/academic year information"""
        try:
            user_type = str(user.user_type)
            
            if user_type == '3':  # Student
                try:
                    student = Student.objects.select_related('session').get(admin=user)
                    if student.session:
                        return {
                            "message": (
                                f"📅 **Your Academic Session**\n\n"
                                f"**Current Session:** {student.session.start_year.year}-{student.session.end_year.year}\n"
                                f"**Duration:** {student.session.start_year} to {student.session.end_year}"
                            ),
                            "type": "session"
                        }
                    else:
                        return {"message": "📅 **Session Info**\n\nNo session assigned to you yet.", "type": "info"}
                except Student.DoesNotExist:
                    return {"message": "❌ Student profile not found.", "type": "error"}
                    
            elif user_type == '2':  # Staff
                try:
                    staff = Staff.objects.select_related('course').get(admin=user)
                    recent_sessions = Session.objects.order_by('-start_year')[:3]
                    
                    if recent_sessions.exists():
                        session_list = [f"• {s.start_year.year}-{s.end_year.year}" for s in recent_sessions]
                        return {
                            "message": (
                                f"📅 **Recent Academic Sessions**\n\n"
                                f"\n".join(session_list)
                            ),
                            "type": "session"
                        }
                    else:
                        return {"message": "📅 **Session Info**\n\nNo sessions found in the system.", "type": "info"}
                except Staff.DoesNotExist:
                    return {"message": "❌ Staff profile not found.", "type": "error"}
                    
            else:  # Admin
                # Admin can see all sessions
                recent_sessions = Session.objects.order_by('-start_year')[:5]
                
                if recent_sessions.exists():
                    session_list = []
                    for session in recent_sessions:
                        student_count = Student.objects.filter(session=session).count()
                        session_list.append(
                            f"• **{session.start_year.year}-{session.end_year.year}** "
                            f"({student_count} students)"
                        )
                    
                    return {
                        "message": (
                            f"📅 **System Academic Sessions**\n\n"
                            f"\n".join(session_list)
                        ),
                        "type": "session"
                    }
                else:
                    return {"message": "📅 **Session Info**\n\nNo sessions found in the system.", "type": "info"}
                    
        except Exception as e:
            logger.error(f"Error getting session info for {user.email}: {str(e)}")
            return {"message": "❌ Error retrieving session information.", "type": "error"}

    def get_enhanced_attendance_info(self, user):
        """Get enhanced attendance information"""
        try:
            user_type = str(user.user_type)
            
            if user_type == '3':  # Student
                student = Student.objects.get(admin=user)
                attendance_reports = AttendanceReport.objects.filter(student=student)
                total_classes = attendance_reports.count()
                present_classes = attendance_reports.filter(status=True).count()
                
                if total_classes == 0:
                    return {"message": "📊 **Attendance Summary**\n\nNo attendance records found yet.", "type": "info"}
                
                attendance_percentage = (present_classes / total_classes) * 100
                
                return {
                    "message": (
                        f"📊 **Your Attendance Summary**\n\n"
                        f"**Total Classes:** {total_classes}\n"
                        f"**Present:** {present_classes}\n"
                        f"**Absent:** {total_classes - present_classes}\n"
                        f"**Attendance Rate:** {attendance_percentage:.1f}%"
                    ),
                    "type": "attendance"
                }
                
            else:
                return {"message": "📊 Attendance data is currently available for students only.", "type": "info"}
                
        except Student.DoesNotExist:
            return {"message": "❌ Student profile not found.", "type": "error"}
        except Exception as e:
            logger.error(f"Error getting attendance info for {user.email}: {str(e)}")
            return {"message": "❌ Error retrieving attendance information.", "type": "error"}

    def get_enhanced_notifications(self, user):
        """Get enhanced notifications"""
        try:
            user_type = str(user.user_type)
            notifications = []
            
            if user_type == '3':  # Student
                student = Student.objects.get(admin=user)
                notifs = NotificationStudent.objects.filter(student=student).order_by('-created_at')[:5]
                for n in notifs:
                    notifications.append(f"• {n.message}")
                    
            elif user_type == '2':  # Staff
                staff = Staff.objects.get(admin=user)
                notifs = NotificationStaff.objects.filter(staff=staff).order_by('-created_at')[:5]
                for n in notifs:
                    notifications.append(f"• {n.message}")
            
            elif user_type == '1':  # Admin
                recent_students = Student.objects.order_by('-created_at')[:3]
                recent_staff = Staff.objects.order_by('-created_at')[:3]
                
                notifications.append("📊 **Recent System Activity:**")
                if recent_students.exists():
                    notifications.append("**New Students:**")
                    for student in recent_students:
                        notifications.append(f"• {student.admin.get_full_name()}")
                
                if recent_staff.exists():
                    notifications.append("**New Staff:**")
                    for staff in recent_staff:
                        notifications.append(f"• {staff.admin.get_full_name()}")
            
            if notifications:
                return {"message": "🔔 **Recent Notifications:**\n\n" + "\n".join(notifications), "type": "notifications"}
            else:
                return {"message": "🔔 **Notifications**\n\nNo recent notifications.", "type": "info"}
                
        except (Student.DoesNotExist, Staff.DoesNotExist):
            return {"message": "❌ Profile not found.", "type": "error"}
        except Exception as e:
            logger.error(f"Error getting notifications for {user.email}: {str(e)}")
            return {"message": "❌ Error retrieving notifications.", "type": "error"}

    def get_enhanced_academic_info(self, user):
        """Get enhanced academic information"""
        try:
            user_type = str(user.user_type)
            
            if user_type == '3':  # Student
                student = Student.objects.select_related('course').get(admin=user)
                
                if not student.course:
                    return {"message": "📚 **Academic Info**\n\nCourse not assigned.", "type": "info"}
                
                subjects = Subject.objects.filter(course=student.course).select_related('staff__admin')
                
                if not subjects.exists():
                    return {"message": f"📚 **Subjects for {student.course.name}**\n\nNo subjects found for your course.", "type": "info"}
                
                subject_list = []
                for i, subject in enumerate(subjects, 1):
                    teacher_name = subject.staff.admin.get_full_name() if subject.staff else "Not assigned"
                    subject_list.append(f"{i}. **{subject.name}**\n   Teacher: {teacher_name}")
                
                return {
                    "message": (
                        f"📚 **Your Course:** {student.course.name}\n\n"
                        f"**Subjects:**\n" + "\n".join(subject_list)
                    ),
                    "type": "academic"
                }
                
            elif user_type == '2':  # Staff
                staff = Staff.objects.select_related('course').get(admin=user)
                subjects = Subject.objects.filter(staff=staff).select_related('course')
                
                if not subjects.exists():
                    return {"message": "📚 **Your Subjects**\n\nNo subjects assigned to you.", "type": "info"}
                
                subject_list = [f"• **{s.name}** ({s.course.name})" for s in subjects]
                
                return {
                    "message": (
                        f"📚 **Subjects You Teach:**\n\n"
                        f"\n".join(subject_list)
                    ),
                    "type": "academic"
                }
                
            else:  # Admin
                courses = Course.objects.all()
                subjects = Subject.objects.all()
                
                return {
                    "message": (
                        f"📚 **System Academic Overview:**\n\n"
                        f"**Total Courses:** {courses.count()}\n"
                        f"**Total Subjects:** {subjects.count()}\n\n"
                        f"💡 Visit the admin dashboard for detailed management."
                    ),
                    "type": "academic"
                }
                
        except (Student.DoesNotExist, Staff.DoesNotExist):
            return {"message": "❌ Profile not found.", "type": "error"}
        except Exception as e:
            logger.error(f"Error getting academic info for {user.email}: {str(e)}")
            return {"message": "❌ Error retrieving academic information.", "type": "error"}

    def get_student_results(self, user):
        """Get student results"""
        try:
            student = Student.objects.get(admin=user)
            results = StudentResult.objects.filter(student=student).select_related('subject')
            
            if not results.exists():
                return {"message": "📋 **Results**\n\nNo results available yet.", "type": "info"}
            
            result_message = "📋 **Your Results:**\n\n"
            for result in results:
                total = result.test + result.exam
                result_message += (
                    f"**{result.subject.name}:**\n"
                    f"  Test: {result.test}%\n"
                    f"  Exam: {result.exam}%\n"
                    f"  Total: {total}%\n\n"
                )
            
            return {"message": result_message, "type": "results"}
            
        except Student.DoesNotExist:
            return {"message": "❌ Student profile not found.", "type": "error"}
        except Exception as e:
            logger.error(f"Error getting student results for {user.email}: {str(e)}")
            return {"message": "❌ Error retrieving results.", "type": "error"}

    def get_student_leave_status(self, user):
        """Get student leave status"""
        try:
            student = Student.objects.get(admin=user)
            recent_leaves = LeaveReportStudent.objects.filter(student=student).order_by('-created_at')[:3]
            
            if not recent_leaves.exists():
                return {"message": "📅 **Leave Status**\n\nNo leave applications found.", "type": "info"}
            
            leave_info = []
            for leave in recent_leaves:
                status = self.get_leave_status_display(leave.status)
                leave_info.append(
                    f"**Date:** {leave.date}\n"
                    f"**Status:** {status}\n"
                    f"**Message:** {leave.message[:50]}..."
                )
            
            return {"message": "📅 **Recent Leave Applications:**\n\n" + "\n\n".join(leave_info), "type": "leave"}
            
        except Student.DoesNotExist:
            return {"message": "❌ Student profile not found.", "type": "error"}
        except Exception as e:
            logger.error(f"Error getting student leave status for {user.email}: {str(e)}")
            return {"message": "❌ Error retrieving leave status.", "type": "error"}

    def get_staff_leave_status(self, user):
        """Get staff leave status"""
        try:
            staff = Staff.objects.get(admin=user)
            recent_leaves = LeaveReportStaff.objects.filter(staff=staff).order_by('-created_at')[:3]
            
            if not recent_leaves.exists():
                return {"message": "📅 **Leave Status**\n\nNo leave applications found.", "type": "info"}
            
            leave_info = []
            for leave in recent_leaves:
                status = self.get_leave_status_display(leave.status)
                leave_info.append(
                    f"**Date:** {leave.date}\n"
                    f"**Status:** {status}\n"
                    f"**Message:** {leave.message[:50]}..."
                )
            
            return {"message": "📅 **Recent Leave Applications:**\n\n" + "\n\n".join(leave_info), "type": "leave"}
            
        except Staff.DoesNotExist:
            return {"message": "❌ Staff profile not found.", "type": "error"}
        except Exception as e:
            logger.error(f"Error getting staff leave status for {user.email}: {str(e)}")
            return {"message": "❌ Error retrieving leave status.", "type": "error"}

    def get_staff_attendance_info(self, user):
        """Get staff attendance management info"""
        try:
            staff = Staff.objects.get(admin=user)
            subjects = Subject.objects.filter(staff=staff).select_related('course')
            
            if not subjects.exists():
                return {"message": "📚 **Attendance Management**\n\nNo subjects assigned to you.", "type": "info"}
            
            subject_list = "\n".join([f"• {s.name} ({s.course.name})" for s in subjects])
            return {
                "message": (
                    f"👨‍🏫 **Attendance Management**\n\n"
                    f"**Subjects you teach:**\n{subject_list}\n\n"
                    f"💡 Use the attendance module to mark student attendance for your subjects."
                ),
                "type": "attendance"
            }
            
        except Staff.DoesNotExist:
            return {"message": "❌ Staff profile not found.", "type": "error"}
        except Exception as e:
            logger.error(f"Error getting staff attendance info for {user.email}: {str(e)}")
            return {"message": "❌ Error retrieving attendance information.", "type": "error"}

    def get_system_overview(self):
        """Get system overview for admin"""
        try:
            total_students = Student.objects.count()
            total_staff = Staff.objects.count()
            total_courses = Course.objects.count()
            total_subjects = Subject.objects.count()
            
            # Recent activity
            recent_students = Student.objects.select_related('admin').order_by('-created_at')[:3]
            recent_staff = Staff.objects.select_related('admin').order_by('-created_at')[:3]
            
            overview = (
                f"📊 **System Overview**\n\n"
                f"**Total Students:** {total_students}\n"
                f"**Total Staff:** {total_staff}\n"
                f"**Total Courses:** {total_courses}\n"
                f"**Total Subjects:** {total_subjects}\n"
            )
            
            if recent_students.exists():
                overview += "\n**📈 Recent Students:**\n"
                for student in recent_students:
                    overview += f"• {student.admin.get_full_name()}\n"
            
            if recent_staff.exists():
                overview += "\n**📈 Recent Staff:**\n"
                for staff in recent_staff:
                    overview += f"• {staff.admin.get_full_name()}\n"
            
            return {"message": overview, "type": "overview"}
            
        except Exception as e:
            logger.error(f"Error getting system overview: {str(e)}")
            return {"message": "❌ Error retrieving system overview.", "type": "error"}

    def get_help_response(self, user):
        """Get help response with user-specific commands"""
        user_type = str(user.user_type)
        
        if user_type == '3':  # Student
            help_text = (
                f"🤖 **Hello {user.first_name}! Here's what I can help you with:**\n\n"
                f"**📋 Personal Information:**\n"
                f"• \"Show my profile\" - View your complete profile\n"
                f"• \"My details\" - Get your contact and course info\n\n"
                f"**📊 Academic Information:**\n"
                f"• \"Check attendance\" - View your attendance summary\n"
                f"• \"Show results\" - View your exam results\n"
                f"• \"My subjects\" - List your course subjects\n"
                f"• \"Session info\" - View your academic session\n\n"
                f"**📢 Other Features:**\n"
                f"• \"Any notifications?\" - Check recent notifications\n"
                f"• \"Leave status\" - View your leave applications\n\n"
                f"**💡 Tips:**\n"
                f"• You can also say \"hi\" or \"hello\" to start\n"
                f"• Ask about anything else and I'll try to help!"
            )
        elif user_type == '2':  # Staff
            help_text = (
                f"🤖 **Hello {user.first_name}! Here's what I can help you with:**\n\n"
                f"**👨‍🏫 Personal Information:**\n"
                f"• \"Show my profile\" - View your complete profile\n"
                f"• \"My details\" - Get your contact and course info\n\n"
                f"**📚 Teaching Information:**\n"
                f"• \"My subjects\" - View subjects you teach\n"
                f"• \"Attendance\" - Get attendance management info\n\n"
                f"**📢 Communication:**\n"
                f"• \"Notifications\" - Check your notifications\n"
                f"• \"Leave status\" - View your leave applications\n\n"
                f"**💡 Tips:**\n"
                f"• You can also say \"hi\" or \"hello\" to start\n"
                f"• Ask about anything else and I'll try to help!"
            )
        else:  # Admin
            help_text = (
                f"🤖 **Hello {user.first_name}! Here's what I can help you with:**\n\n"
                f"**👤 Personal Information:**\n"
                f"• \"Show my profile\" - View your complete profile\n\n"
                f"**📊 System Overview:**\n"
                f"• \"System overview\" - Get system statistics\n"
                f"• \"Student count\" - View total students\n"
                f"• \"Staff count\" - View total staff\n\n"
                f"**📅 Academic Info:**\n"
                f"• \"Session info\" - View academic sessions\n\n"
                f"**💡 Tips:**\n"
                f"• You can also say \"hi\" or \"hello\" to start\n"
                f"• Ask about anything else and I'll try to help!"
            )
        
        return {"message": help_text, "type": "help"}

    def get_leave_status_display(self, status):
        """Get human-readable leave status"""
        status_map = {
            0: "⏳ Pending",
            1: "✅ Approved",
            2: "❌ Rejected"
        }
        return status_map.get(status, "⏳ Unknown")

    def get_ai_response(self, user, message):
        """Get AI response from Gemini"""
        if self.system_settings and self.system_settings.gemini_api_key and HAS_GEMINI:
            try:
                genai.configure(api_key=self.system_settings.gemini_api_key)
                model = genai.GenerativeModel('gemini-pro')
                
                context = (
                    f"You are a helpful assistant for a College Management System. "
                    f"The user is {user.first_name} {user.last_name} ({user.get_user_type_display()}). "
                    f"Be concise and helpful. If asked about specific college data, "
                    f"politely direct them to use the appropriate system features. "
                    f"Answer the following question: {message}"
                )
                
                response = model.generate_content(context)
                return {"message": response.text, "type": "ai"}
                
            except Exception as e:
                logger.error(f"Gemini AI error: {str(e)}")
                pass
        
        # Default response
        default_response = (
            self.system_settings.chat_default_response if self.system_settings 
            else "I'm sorry, I didn't understand that. You can ask about your profile, attendance, notifications, subjects, or sessions."
        )
        return {"message": default_response, "type": "default"}

# Keep the original ChatService for backward compatibility
class ChatService(EnhancedChatService):
    """Backward compatibility wrapper"""
    pass

@csrf_exempt
def chat_api(request):
    """Enhanced chat API with better error handling"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            message = data.get('message', '').strip()
            
            if not message:
                return JsonResponse({"message": "❌ Please provide a message.", "type": "error"})
            
            service = EnhancedChatService()
            response = service.process_message(request.user, message)
            
            # Ensure response has required fields
            if 'message' not in response:
                response['message'] = "❌ Invalid response format."
            if 'type' not in response:
                response['type'] = 'error'
            
            return JsonResponse(response)
            
        except json.JSONDecodeError:
            return JsonResponse({"message": "❌ Invalid JSON format.", "type": "error"})
        except Exception as e:
            logger.error(f"Chat API error: {str(e)}")
            return JsonResponse({"message": "❌ An error occurred processing your request.", "type": "error"}, status=500)
    
    return JsonResponse({"message": "❌ Invalid request method.", "type": "error"}, status=400)

# Backward compatibility view
def chat_api_legacy(request):
    """Legacy chat API for backward compatibility"""
    return chat_api(request)