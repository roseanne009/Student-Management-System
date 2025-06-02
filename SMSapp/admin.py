from django.contrib import admin
from .models import Course, Student, Subject, StudentSubjectEnrollment, Activity, Grade

admin.site.register(Course)
admin.site.register(Student)
admin.site.register(Subject)
admin.site.register(StudentSubjectEnrollment)
admin.site.register(Activity)
admin.site.register(Grade)
