from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from rest_framework.decorators import api_view
from django.db import models, transaction
import json  # Add json import here

from .models import Subject, Activity, Grade, Student, Course, Section

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db import models  # Add this import
from .models import Subject, Activity, StudentSubjectEnrollment, Course, Student, Grade
from .serializers import (
    SubjectSerializer, ActivitySerializer, 
    StudentSubjectEnrollmentSerializer, CourseSerializer, StudentSerializer,SectionSerializer, GradeSerializer
)
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from datetime import datetime
from django.utils import timezone
from django.db.models import Count, Q, OuterRef, Exists

def index(request):
    # Summary statistics
    total_students = Student.objects.count()
    total_courses = Course.objects.count()
    total_subjects = Subject.objects.filter(is_active=True).count()
    archived_subjects = Subject.objects.filter(is_active=False).count()
    
    # Calculate new students this month
    this_month = timezone.now().replace(day=1)
    new_students = Student.objects.filter(date_added__gte=this_month).count()

    # Course statistics with student counts
    course_stats = Course.objects.annotate(
        student_count=Count('student')
    ).values('course_abv', 'course_name', 'student_count')

    # Year level distribution with percentages
    total_count = Student.objects.count()
    year_stats = Student.objects.values('year_level').annotate(
        student_count=Count('student_id')
    ).order_by('year_level')
    
    for year in year_stats:
        year['percentage'] = (year['student_count'] / total_count * 100) if total_count > 0 else 0

    # Activity type distribution
    activity_stats = []
    for activity_type in ['Quiz', 'Exam', 'Project', 'Activities']:
        count = Activity.objects.filter(activity_type=activity_type).count()
        pending = Activity.objects.filter(
            activity_type=activity_type
        ).exclude(
            activity_id__in=Grade.objects.values('activity')
        ).count()
        
        activity_stats.append({
            'type': activity_type,
            'count': count,
            'pending': pending
        })

    # Recent activities with pending grades count
    recent_activities = Activity.objects.select_related('subject').order_by('-activity_id')[:5]
    for activity in recent_activities:
        total_students = StudentSubjectEnrollment.objects.filter(subject=activity.subject).count()
        graded_count = Grade.objects.filter(activity=activity).count()
        activity.pending_count = total_students - graded_count

    context = {
        'total_students': total_students,
        'total_courses': total_courses,
        'total_subjects': total_subjects,
        'archived_subjects': archived_subjects,
        'new_students': new_students,
        'pending_activities': Activity.objects.filter(
            activity_id__in=StudentSubjectEnrollment.objects.values('subject__activity')
        ).exclude(
            activity_id__in=Grade.objects.values('activity')
        ).count(),
        'course_stats': course_stats,
        'year_stats': year_stats,
        'activity_stats': activity_stats,
        'recent_students': Student.objects.select_related('course').order_by('-date_added')[:5],
        'recent_activities': recent_activities,
    }
    
    return render(request, 'index.html', context)

# default view for subjects
def subjects(request):
    subjects = Subject.objects.filter(is_active=True)  # Only show non-archived subjects
    courses = Course.objects.all()
    context = {
        'subjects': subjects,
        'courses': courses,
    }
    return render(request, 'subjects.html', context)

# view for subject details including activities and enrolled students
def subject_info(request, subject_code):
    subject = get_object_or_404(Subject, subject_code=subject_code)
    enrollments = StudentSubjectEnrollment.objects.filter(student__course__subject=subject)
    enrolled_count = enrollments.count()
    
    # Get all activities with their grading status
    activities = Activity.objects.filter(subject=subject).annotate(
        graded_count=Count('grade'),
        is_pending=models.Case(
            models.When(graded_count__lt=enrolled_count, then=True),
            default=False,
            output_field=models.BooleanField(),
        )
    )

    # Count pending activities
    pending_activities = activities.filter(is_pending=True).count()

    context = {
        'subject': subject,
        'activities': activities,
        'enrolled_students': enrollments,
        'pending_activities': pending_activities,
        'total_students': enrolled_count,
    }
    
    return render(request, 'subjectinfo.html', context)

def student_info(request, student_id):
    student = get_object_or_404(Student, student_id=student_id)
    enrollments = StudentSubjectEnrollment.objects.filter(
        student=student,
        subject__is_active=True  # Only show active (non-archived) subjects
    ).select_related('subject')
    
    context = {
        'student': student,
        'enrollments': enrollments,
    }
    return render(request, 'studentinfo.html', context)

def student_subject_info(request, student_id, subject_code):
    student = get_object_or_404(Student, student_id=student_id)
    subject = get_object_or_404(Subject, subject_code=subject_code)
    activities = Activity.objects.filter(subject=subject)
    
    # Get grades for each activity
    grades = {}
    for activity in activities:
        grade = Grade.objects.filter(
            student=student,
            activity=activity
        ).first()
        grades[activity.activity_id] = grade.student_grade if grade else 'N/A'
    
    context = {
        'student': student,
        'subject': subject,
        'activities': activities,
        'grades': grades,
    }
    return render(request, 'studentsubinfo.html', context)

class SubjectViewSet(viewsets.ModelViewSet):
    permission_classes = [AllowAny]
    queryset = Subject.objects.filter(archive=False)
    serializer_class = SubjectSerializer
    lookup_field = 'subject_code'

    def create(self, request, *args, **kwargs):
        try:
            print("Received data:", request.data)  # Debug print
            serializer = self.get_serializer(data=request.data)
            if serializer.is_valid():
                self.perform_create(serializer)
                return JsonResponse({
                    'status': 'success',
                    'message': 'Subject created successfully',
                    'data': serializer.data
                })
            print("Validation errors:", serializer.errors)  # Debug print
            return JsonResponse({
                'status': 'error',
                'message': serializer.errors
            }, status=400)
        except Exception as e:
            import traceback
            print("Exception:", str(e))  # Debug print
            print("Traceback:", traceback.format_exc())  # Debug print
            return JsonResponse({
                'status': 'error',
                'message': f"Server error: {str(e)}"
            }, status=500)
            
    def update(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            data = request.data.copy()
            
            # Convert numeric fields
            for field in ['year_level', 'semester']:
                if field in data:
                    data[field] = int(data[field])
            
            with transaction.atomic():
                # If subject code is changing and there are related records
                if 'subject_code' in data and data['subject_code'] != instance.subject_code:
                    new_code = data['subject_code'].upper()
                    
                    # Create new subject with new code and all updated data
                    new_subject = Subject.objects.create(
                        subject_code=new_code,
                        subject_title=data.get('subject_title', instance.subject_title),
                        course=instance.course if not data.get('course') else Course.objects.get(course_abv=data['course']),
                        school_year=data.get('school_year', instance.school_year),
                        semester=data.get('semester', instance.semester),
                        year_level=data.get('year_level', instance.year_level),
                        section=data.get('section', instance.section),
                        archive=instance.archive,
                        is_active=instance.is_active
                    )
                    
                    # Update foreign key references from related models
                    Activity.objects.filter(subject=instance).update(subject=new_subject)
                    StudentSubjectEnrollment.objects.filter(subject=instance).update(subject=new_subject)
                    
                    # Delete old subject after moving all relations
                    instance.delete()
                    updated_instance = new_subject
                else:
                    # Regular update without changing subject code
                    serializer = self.get_serializer(instance, data=data, partial=True)
                    if serializer.is_valid():
                        updated_instance = serializer.save()
                
                return JsonResponse({
                    'status': 'success',
                    'message': 'Subject updated successfully',
                    'data': self.get_serializer(updated_instance).data
                })
                
        except Exception as e:
            print(f"Error updating subject: {str(e)}")
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=400)
    
    def destroy(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            instance.delete()  # Perform actual deletion
            return JsonResponse({
                'status': 'success',
                'message': 'Subject deleted successfully'
            })
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=400)

    @action(detail=True, methods=['get'])
    def info(self, request, subject_code=None):
        try:
            subject = self.get_object()
            activities = Activity.objects.filter(subject=subject)
            enrollments = StudentSubjectEnrollment.objects.filter(subject=subject).select_related('student')
            
            return JsonResponse({
                'status': 'success',
                'data': {
                    'subject': SubjectSerializer(subject).data,
                    'activities': ActivitySerializer(activities, many=True).data,
                    'enrollments': StudentSubjectEnrollmentSerializer(enrollments, many=True).data
                }
            })
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=400)

class ActivityViewSet(viewsets.ModelViewSet):
    permission_classes = [AllowAny]
    queryset = Activity.objects.all()
    serializer_class = ActivitySerializer
    lookup_field = 'activity_id'

    def retrieve(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            return JsonResponse({
                'status': 'success',
                'data': {
                    'activity_id': instance.activity_id,
                    'activity_type': instance.activity_type,
                    'activity_name': instance.activity_name,
                    'total_items': instance.total_items,
                    'subject': instance.subject.subject_code
                }
            })
        except Activity.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': 'Activity not found'
            }, status=404)
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=500)
    
    def create(self, request, *args, **kwargs):
        try:
            serializer = self.get_serializer(data=request.data)
            if serializer.is_valid():
                self.perform_create(serializer)
                return JsonResponse({
                    'status': 'success',
                    'data': serializer.data
                })
            return JsonResponse({
                'status': 'error',
                'message': serializer.errors
            }, status=400)
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=400)

    def update(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            serializer = self.get_serializer(instance, data=request.data, partial=True)
            if serializer.is_valid():
                self.perform_update(serializer)
                return Response({
                    'status': 'success',
                    'message': 'Activity updated successfully!',
                    'data': serializer.data
                })
            return Response({
                'status': 'error',
                'message': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({
                'status': 'error',
                'message': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)

    def destroy(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            instance.delete()
            return JsonResponse({
                'status': 'success',
                'message': 'Activity deleted successfully'
            })
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=400)

    def get_queryset(self):
        queryset = Activity.objects.all()
        subject_code = self.request.query_params.get('subject', None)
        if subject_code:
            queryset = queryset.filter(subject__subject_code=subject_code)
        return queryset

class EnrollmentViewSet(viewsets.ModelViewSet):
    permission_classes = [AllowAny]
    queryset = StudentSubjectEnrollment.objects.all()
    serializer_class = StudentSubjectEnrollmentSerializer

    def get_queryset(self):
        queryset = StudentSubjectEnrollment.objects.all()
        subject_code = self.request.query_params.get('subject', None)
        if subject_code:
            queryset = queryset.filter(subject__subject_code=subject_code)
        return queryset

    @action(detail=False, methods=['post'])
    def bulk_enroll(self, request):
        try:
            print("Received enrollment data:", request.data)  # Debug log
            subject_code = request.data.get('subject_code')
            student_ids = request.data.get('student_ids', [])
            
            if not subject_code:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Subject code is required'
                }, status=400)
                
            if not student_ids:
                return JsonResponse({
                    'status': 'error',
                    'message': 'No students selected for enrollment'
                }, status=400)

            subject = Subject.objects.get(subject_code=subject_code)
            enrolled_count = 0
            
            for student_id in student_ids:
                try:
                    # Check if student exists
                    student = Student.objects.get(student_id=student_id)
                    
                    # Skip if already enrolled
                    if not StudentSubjectEnrollment.objects.filter(
                        subject=subject,
                        student=student
                    ).exists():
                        StudentSubjectEnrollment.objects.create(
                            subject=subject,
                            student=student
                        )
                        enrolled_count += 1
                except Student.DoesNotExist:
                    print(f"Student {student_id} not found")  # Debug log
                    continue
            
            print(f"Successfully enrolled {enrolled_count} students")  # Debug log
            return JsonResponse({
                'status': 'success',
                'message': f'Successfully enrolled {enrolled_count} students'
            })
            
        except Subject.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': 'Subject not found'
            }, status=404)
        except Exception as e:
            print(f"Error in bulk_enroll: {str(e)}")  # Debug log
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=400)

    @action(detail=False, methods=['post'])
    def remove_student(self, request):
        try:
            subject_code = request.data.get('subject_code')
            student_id = request.data.get('student_id')
            
            enrollment = StudentSubjectEnrollment.objects.filter(
                subject__subject_code=subject_code,
                student__student_id=student_id
            )
            
            if enrollment.exists():
                enrollment.delete()
                return JsonResponse({
                    'status': 'success',
                    'message': 'Student removed successfully'
                })
            return JsonResponse({
                'status': 'error',
                'message': 'Student enrollment not found'
            }, status=404)
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=400)

class CourseViewSet(viewsets.ModelViewSet):
    permission_classes = [AllowAny]
    queryset = Course.objects.all()
    serializer_class = CourseSerializer
    lookup_field = 'course_abv'

    def create(self, request, *args, **kwargs):
        try:
            print(f"Creating course with data:", request.data)  # Debug log
            
            serializer = self.get_serializer(data=request.data)
            if serializer.is_valid():
                self.perform_create(serializer)
                return Response({
                    'status': 'success',
                    'message': 'Course created successfully',
                    'data': serializer.data
                })
            
            print(f"Validation errors:", serializer.errors)  # Debug log
            return Response({
                'status': 'error',
                'message': serializer.errors
            }, status=400)
            
        except Exception as e:
            print(f"Error creating course: {str(e)}")  # Debug log
            return Response({
                'status': 'error',
                'message': str(e)
            }, status=400)

    def update(self, request, *args, **kwargs):
        try:
            old_course = self.get_object()
            new_data = request.data
            
            with transaction.atomic():
                # If the course code is changing, we need to handle related records
                if new_data['course_abv'] != old_course.course_abv:
                    # Create new course first
                    new_course = Course.objects.create(
                        course_abv=new_data['course_abv'],
                        course_name=new_data['course_name']
                    )
                    
                    # Update all related records to point to the new course
                    Student.objects.filter(course=old_course).update(course=new_course)
                    Subject.objects.filter(course=old_course).update(course=new_course)
                    Section.objects.filter(course=old_course).update(course=new_course)
                    
                    # Delete old course after moving all relations
                    old_course.delete()
                    serializer = self.get_serializer(new_course)
                else:
                    # If only the name is changing, use normal update
                    serializer = self.get_serializer(old_course, data=new_data)
                    if serializer.is_valid():
                        serializer.save()
                
                return Response({
                    'status': 'success',
                    'data': serializer.data,
                    'message': 'Course updated successfully'
                })
        except Exception as e:
            return Response({
                'status': 'error',
                'message': str(e)
            }, status=400)

    def destroy(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            self.perform_destroy(instance)
            return Response({'status': 'success'})
        except Exception as e:
            return Response({'status': 'error', 'message': str(e)}, status=400)

    def retrieve(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            serializer = self.get_serializer(instance)
            return Response({
                'status': 'success',
                'data': serializer.data
            })
        except Course.DoesNotExist:
            return Response({
                'status': 'error',
                'message': 'Course not found'
            }, status=404)
        except Exception as e:
            return Response({
                'status': 'error',
                'message': str(e)
            }, status=500)

class StudentViewSet(viewsets.ModelViewSet):
    permission_classes = [AllowAny]
    queryset = Student.objects.all()
    serializer_class = StudentSerializer
    lookup_field = 'student_id'

    def create(self, request, *args, **kwargs):
        try:
            print("Received data:", request.data)  # Debug log
            serializer = self.get_serializer(data=request.data)
            if serializer.is_valid():
                student = serializer.save()
                response_serializer = self.get_serializer(student)
                return Response({
                    'status': 'success',
                    'message': 'Student created successfully',
                    'data': response_serializer.data
                }, status=status.HTTP_201_CREATED)
            
            print("Validation errors:", serializer.errors)  # Debug log
            return Response({
                'status': 'error',
                'message': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            print("Exception:", str(e))  # Debug log
            return Response({
                'status': 'error',
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return JsonResponse({
            'status': 'success',
            'data': serializer.data
        })

    def update(self, request, *args, **kwargs):
        try:
            old_instance = self.get_object()
            new_id = request.data.get('student_id')
            data = request.data.copy()

            # Check if new ID already exists (but ignore if it's the same as current ID)
            if new_id and new_id != old_instance.student_id:
                if Student.objects.filter(student_id=new_id).exists():
                    return Response({
                        'status': 'error',
                        'message': f'Student ID {new_id} already exists'
                    }, status=status.HTTP_400_BAD_REQUEST)

            serializer = self.get_serializer(old_instance, data=data, partial=True)
            if serializer.is_valid():
                try:
                    # Use the custom manager method to handle ID changes
                    updated_student = Student.objects.update_student_id(
                        old_instance.student_id, 
                        serializer.validated_data
                    )
                    return Response({
                        'status': 'success',
                        'data': self.get_serializer(updated_student).data,
                        'message': 'Student updated successfully'
                    })
                except Student.DoesNotExist:
                    return Response({
                        'status': 'error',
                        'message': 'Student not found'
                    }, status=status.HTTP_404_NOT_FOUND)
                except Exception as e:
                    return Response({
                        'status': 'error',
                        'message': str(e)
                    }, status=status.HTTP_400_BAD_REQUEST)

            return Response({
                'status': 'error',
                'message': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            print("Error updating student:", str(e))
            return Response({
                'status': 'error',
                'message': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)

    def destroy(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            instance.delete()
            return JsonResponse({
                'status': 'success',
                'message': 'Student deleted successfully'
            })
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=400)

class StudentAPIView(APIView):
    permission_classes = [AllowAny]
    def get(self, request):
        students = Student.objects.all()
        serializer = StudentSerializer(students, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = StudentSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({
                'status': 'success',
                'data': serializer.data
            }, status=status.HTTP_201_CREATED)
        return Response({
            'status': 'error',
            'message': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)

class StudentDetailAPIView(APIView):
    permission_classes = [AllowAny]
    def get_object(self, student_id):
        return get_object_or_404(Student, student_id=student_id)

    def get(self, request, student_id):
        student = self.get_object(student_id)
        serializer = StudentSerializer(student)
        return Response({
            'status': 'success',
            'data': serializer.data
        })

    def put(self, request, student_id):
        student = self.get_object(student_id)
        serializer = StudentSerializer(student, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({
                'status': 'success',
                'data': serializer.data
            })
        return Response({
            'status': 'error',
            'message': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, student_id):
        student = self.get_object(student_id)
        student.delete()
        return Response({
            'status': 'success',
            'message': 'Student deleted successfully'
        })

def courses(request):
    courses = Course.objects.all()
    sections = Section.objects.select_related('course').all()
    context = {
        'courses': courses,
        'sections': sections,
    }
    return render(request, 'courses.html', context)

def students(request):
    students = Student.objects.all().select_related('course')
    courses = Course.objects.all()
    return render(request, 'students.html', {'students': students, 'courses': courses})

def grades(request, activity_id):
    activity = Activity.objects.select_related('subject').get(activity_id=activity_id)
    enrollments = StudentSubjectEnrollment.objects.filter(
        subject=activity.subject
    ).select_related('student').annotate(
        grade=models.Subquery(
            Grade.objects.filter(
                student=models.OuterRef('student'),
                activity=activity
            ).values('student_grade')[:1]
        )
    ).order_by('student__last_name', 'student__first_name')  # Order by last name, then first name

    context = {
        'activity': activity,
        'enrollments': enrollments,
    }
    return render(request, 'grades.html', context)

class GradeViewSet(viewsets.ModelViewSet):
    permission_classes = [AllowAny]
    queryset = Grade.objects.all()
    serializer_class = GradeSerializer

    @action(detail=False, methods=['post'])
    def save_grades(self, request, activity_id=None):
        try:
            grades_data = request.data.get('grades', [])
            activity = get_object_or_404(Activity, activity_id=activity_id)
            
            with transaction.atomic():
                for grade_item in grades_data:
                    student_id = grade_item['student_id']
                    grade_value = grade_item['grade']
                    
                    if grade_value == 'N/A':
                        # Delete the grade if it exists
                        Grade.objects.filter(
                            student_id=student_id,
                            activity=activity
                        ).delete()
                    else:
                        # Update or create the grade
                        Grade.objects.update_or_create(
                            student_id=student_id,
                            activity=activity,
                            defaults={'student_grade': grade_value}
                        )

            return Response({'status': 'success'}, status=status.HTTP_200_OK)
            
        except Activity.DoesNotExist:
            return Response({
                'status': 'error',
                'message': 'Activity not found'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({
                'status': 'error',
                'message': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET', 'POST', 'PUT', 'DELETE'])
def activities_api(request, activity_id=None):
    if request.method == 'POST':
        try:
            activity_data = {
                'subject': Subject.objects.get(subject_code=request.data.get('subject')),
                'activity_type': request.data.get('activity_type'),
                'activity_name': request.data.get('activity_name'),
                'total_items': request.data.get('total_items')
            }
            activity = Activity.objects.create(**activity_data)
            return JsonResponse({
                'status': 'success',
                'message': 'Activity created successfully',
                'data': ActivitySerializer(activity).data
            })
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    
    elif request.method == 'GET':
        if activity_id:
            activity = get_object_or_404(Activity, activity_id=activity_id)
            return JsonResponse({
                'status': 'success',
                'data': {
                    'activity_id': activity.activity_id,
                    'activity_type': activity.activity_type,
                    'activity_name': activity.activity_name,
                    'total_items': activity.total_items
                }
            })
        else:
            activities = Activity.objects.all()
            return JsonResponse({'status': 'success', 'data': ActivitySerializer(activities, many=True).data})

    elif request.method == 'PUT':
        try:
            activity = get_object_or_404(Activity, activity_id=activity_id)
            activity.activity_type = request.data.get('activity_type')
            activity.activity_name = request.data.get('activity_name')
            activity.total_items = request.data.get('total_items')
            activity.save()
            
            return JsonResponse({'status': 'success'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

    elif request.method == 'DELETE':
        try:
            activity = get_object_or_404(Activity, activity_id=activity_id)
            activity.delete()
            return JsonResponse({'status': 'success', 'message': 'Activity deleted successfully'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

@api_view(['POST'])
def archive_subject(request, subject_code):
    try:
        subject = get_object_or_404(Subject, subject_code=subject_code)
        subject.is_active = False
        subject.archived_date = timezone.now()
        subject.save()
        return JsonResponse({'status': 'success'})
    except Subject.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Subject not found'}, status=404)

@api_view(['DELETE'])
def delete_subject(request, subject_code):
    try:
        subject = Subject.objects.get(subject_code=subject_code)
        subject.delete()
        return JsonResponse({'status': 'success'})
    except Subject.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Subject not found'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

@api_view(['POST'])
def unarchive_subject(request, subject_code):
    try:
        subject = Subject.objects.get(subject_code=subject_code)
        subject.is_active = True
        subject.archived_date = None
        subject.save()
        return JsonResponse({'status': 'success'})
    except Subject.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Subject not found'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

def archived_subjects(request):
    subjects = Subject.objects.filter(is_active=False)
    return render(request, 'archived_subjects.html', {'subjects': subjects})

@api_view(['GET'])
def get_available_students(request, subject_code):
    """Get students who match the subject's year and section"""
    try:
        subject = get_object_or_404(Subject, subject_code=subject_code)
        print(f"Found subject: {subject.subject_code}")  # Debug log
        
        enrolled_student_ids = StudentSubjectEnrollment.objects.filter(
            subject=subject
        ).values_list('student__student_id', flat=True)
        
        # Create a Q object for the filter conditions
        regular_students = Q(
            year_level=subject.year_level,
            section=subject.section,
            course=subject.course,
            status='R'  # Regular students
        )
        
        # Include all irregular students
        irregular_students = Q(status='I')  # Irregular students
        
        # Combine the conditions with OR operator
        available_students = Student.objects.filter(
            regular_students | irregular_students
        ).exclude(
            student_id__in=enrolled_student_ids
        ).select_related('course')
        
        print(f"Found {available_students.count()} available students")  # Debug log
        
        students_list = []
        for student in available_students:
            students_list.append({
                'student_id': student.student_id,
                'first_name': student.first_name,
                'last_name': student.last_name,
                'middle_name': student.middle_name,
                'year_level': student.year_level,
                'section': student.section,
                'course': student.course.course_abv,
                'status': student.status  # Add status to display
            })
        
        return Response({
            'status': 'success',
            'data': students_list
        }, status=200)
        
    except Exception as e:
        print(f"Error: {str(e)}")  # Debug log
        return Response({
            'status': 'error',
            'message': str(e)
        }, status=500)

@require_http_methods(["GET"])
def get_enrolled_students(request):
    """Get students enrolled in a specific subject"""
    subject_code = request.GET.get('subject')
    if not subject_code:
        return JsonResponse({'status': 'error', 'message': 'Subject code is required'})
    
    enrollments = StudentSubjectEnrollment.objects.filter(
        subject__subject_code=subject_code
    ).select_related('student', 'student__course')
    
    enrolled_students = []
    for enrollment in enrollments:
        student = enrollment.student
        enrolled_students.append({
            'student': {
                'student_id': student.student_id,
                'first_name': student.first_name,
                'last_name': student.last_name,
                'middle_name': student.middle_name,
                'year_level': student.year_level,
                'section': student.section,
                'course': {
                    'course_abv': student.course.course_abv
                }
            }
        })
    
    return JsonResponse(enrolled_students, safe=False)

@require_http_methods(["GET"])
def get_available_sections(request):
    course_id = request.GET.get('course')
    year_level = request.GET.get('year')
    
    sections = Section.objects.all()
    if course_id:
        sections = sections.filter(course_id=course_id)
    if year_level:
        sections = sections.filter(year_level=year_level)
    
    data = [{
        'id': section.id,
        'year_level': section.year_level,
        'section_name': section.section_name,
        'course': section.course.course_abv,
        'is_full': section.is_full()
    } for section in sections]
    
    return JsonResponse({'status': 'success', 'data': data})

@require_http_methods(["POST"])
def create_section(request):
    data = json.loads(request.body)
    try:
        section = Section.objects.create(
            year_level=data['year_level'],
            section_name=data['section_name'],
            course_id=data['course'],
            max_students=data.get('max_students', 40)
        )
        return JsonResponse({
            'status': 'success',
            'data': {
                'id': section.id,
                'year_level': section.year_level,
                'section_name': section.section_name
            }
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)})

@require_http_methods(["GET"])
def get_sections(request):
    course = request.GET.get('course')
    year_level = request.GET.get('year')
    
    query = Section.objects.all()
    if course:
        query = query.filter(course__course_abv=course)
    if year_level:
        query = query.filter(year_level=year_level)
        
    sections = [{
        'id': section.id,
        'name': section.section_name,
        'year_level': section.year_level,
        'course': section.course.course_abv
    } for section in query]
    
    return JsonResponse({'status': 'success', 'data': sections})

@require_http_methods(["POST"])
def add_section(request):
    data = json.loads(request.body)
    try:
        course = Course.objects.get(course_abv=data['course'])
        section = Section.objects.create(
            course=course,
            year_level=data['year_level'],
            section_name=data['section_name']
        )
        return JsonResponse({
            'status': 'success',
            'data': {
                'id': section.id,
                'name': section.section_name
            }
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)})

class SectionViewSet(viewsets.ModelViewSet):
    permission_classes = [AllowAny]
    queryset = Section.objects.all()
    serializer_class = SectionSerializer
    lookup_field = 'id'

    def create(self, request, *args, **kwargs):
        try:
            data = {
                'course': request.data.get('course'),
                'year_level': request.data.get('year_level'),
                'section_name': request.data.get('section_name', '').upper()
            }
            
            # Validate data presence
            if not all(data.values()):
                return Response({
                    'status': 'error',
                    'message': 'All fields are required'
                }, status=400)

            print(f"Creating section with data:", data)  # Debug log
            serializer = self.get_serializer(data=data)
            
            if serializer.is_valid():
                section = serializer.save()
                return Response({
                    'status': 'success',
                    'data': self.get_serializer(section).data,
                    'message': 'Section created successfully'
                })
            
            print(f"Validation errors:", serializer.errors)  # Debug log
            return Response({
                'status': 'error',
                'message': serializer.errors
            }, status=400)

        except Exception as e:
            print(f"Error creating section: {str(e)}")  # Debug log
            import traceback
            traceback.print_exc()
            return Response({
                'status': 'error',
                'message': str(e)
            }, status=400)

    def update(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            
            # Prepare the data
            data = {
                'course': request.data.get('course'),
                'year_level': request.data.get('year_level'),
                'section_name': request.data.get('section_name', '').upper()
            }
            
            # Remove None values
            data = {k: v for k, v in data.items() if v is not None}

            print(f"Updating section {instance.id} with data:", data)  # Debug log
            
            serializer = self.get_serializer(instance, data=data, partial=True)
            if serializer.is_valid():
                updated_instance = serializer.save()
                return Response({
                    'status': 'success',
                    'data': self.get_serializer(updated_instance).data,
                    'message': 'Section updated successfully'
                })
            
            print(f"Validation errors:", serializer.errors)  # Debug log
            return Response({
                'status': 'error',
                'message': serializer.errors
            }, status=400)
            
        except Exception as e:
            print(f"Error updating section: {str(e)}")  # Debug log
            return Response({
                'status': 'error',
                'message': str(e)
            }, status=400)

    def destroy(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            self.perform_destroy(instance)
            return Response({
                'status': 'success',
                'message': 'Section deleted successfully'
            })
        except Exception as e:
            return Response({
                'status': 'error',
                'message': str(e)
            }, status=400)

    def retrieve(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            serializer = self.get_serializer(instance)
            return Response({
                'status': 'success',
                'data': serializer.data
            })
        except Exception as e:
            return Response({
                'status': 'error',
                'message': str(e)
            }, status=404)

    def get_queryset(self):
        queryset = Section.objects.all()
        course = self.request.query_params.get('course', None)
        year_level = self.request.query_params.get('year_level', None)

        if course:
            queryset = queryset.filter(course__course_abv=course)
        if year_level:
            queryset = queryset.filter(year_level=year_level)
        
        return queryset.select_related('course')

@api_view(['GET'])
def get_student_sections(request):
    course = request.GET.get('course')
    year_level = request.GET.get('year_level')
    
    if not course or not year_level:
        return JsonResponse({
            'status': 'error',
            'message': 'Course and year level are required'
        })
    
    sections = Section.objects.filter(
        course__course_abv=course,
        year_level=year_level
    ).values('section_name')
    
    return JsonResponse({
        'status': 'success',
        'data': list(sections)
    })