from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'subjects', views.SubjectViewSet)
router.register(r'activities', views.ActivityViewSet)
router.register(r'enrollments', views.EnrollmentViewSet, basename='enrollment')
router.register(r'courses', views.CourseViewSet)
router.register(r'students', views.StudentViewSet)
router.register(r'sections', views.SectionViewSet, basename='section')

urlpatterns = [
    path('', views.index, name='index'),
    path('api/', include(router.urls)),
    path('index/', views.index, name='index'),
    path('subjects/', views.subjects, name='subjects'),
    path('subjects/<str:subject_code>/', views.subject_info, name='subject_info'),
    path('students/', views.students, name='students'),
    path('students/<str:student_id>/', views.student_info, name='student_info'),  # Add this line
    path('students/<str:student_id>/subjects/<str:subject_code>/', views.student_subject_info, name='student_subject_info'),
    path('courses/', views.courses, name='courses'),
    path('activities/<int:activity_id>/grades/', views.grades, name='grades'),
    path('api/activities/<int:activity_id>/grades/', views.GradeViewSet.as_view({
        'post': 'save_grades',
    }), name='save_grades'),
    path('archived-subjects/', views.archived_subjects, name='archived_subjects'),
    path('api/subjects/<str:subject_code>/archive/', views.archive_subject, name='archive_subject'),
    path('api/subjects/<str:subject_code>/', views.delete_subject, name='delete_subject'),
    path('api/subjects/<str:subject_code>/unarchive/', views.unarchive_subject, name='unarchive_subject'),
    path('api/sections/', views.get_sections, name='get_sections'),
    path('api/sections/add/', views.add_section, name='add_section'),
    path('api/subjects/<str:subject_code>/available-students/', views.get_available_students, name='get_available_students'),
    path('api/student-sections/', views.get_student_sections, name='student_sections'),  # Use existing view
    path('api/subject-sections/', views.get_student_sections, name='subject_sections'),
]