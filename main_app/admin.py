from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from main_app.models import CustomUser, Staff, Student, Course, Subject, Session, Holiday

# Custom user admin
@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    ordering = ('email',)

# Register the rest
admin.site.register(Staff)
admin.site.register(Student)
admin.site.register(Course)
admin.site.register(Subject)
admin.site.register(Session)

# Holiday admin
@admin.register(Holiday)
class HolidayAdmin(admin.ModelAdmin):
    list_display = ('name', 'date')
    ordering = ('-date',)