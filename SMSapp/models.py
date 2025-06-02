from django.db import models, transaction  # Add transaction here
from django.utils import timezone
import datetime
from django.core.exceptions import ValidationError  # Import ValidationError


class Course(models.Model):
    course_abv = models.CharField(max_length=10, primary_key=True)
    course_name = models.CharField(max_length=100)

    def __str__(self):
        return self.course_name


class StudentManager(models.Manager):
    def update_student_id(self, old_id, new_data):
        student = self.get(student_id=old_id)
        new_id = new_data.get('student_id', old_id)
        
        # If ID is changing and new ID doesn't exist
        if new_id != old_id:
            # Create new student with new ID
            self.create(
                student_id=new_id,
                last_name=new_data.get('last_name', student.last_name),
                first_name=new_data.get('first_name', student.first_name),
                middle_name=new_data.get('middle_name', student.middle_name),
                course=new_data.get('course', student.course),
                year_level=new_data.get('year_level', student.year_level),
                section=new_data.get('section', student.section)
            )
            # Delete old student record
            student.delete()
            # Get and return the new student record
            return self.get(student_id=new_id)
        
        # If no ID change, just update fields
        for key, value in new_data.items():
            setattr(student, key, value)
        student.save()
        return student


class Student(models.Model):
    STATUS_CHOICES = [
        ('R', 'Regular'),
        ('I', 'Irregular')
    ]
    
    student_id = models.CharField(max_length=20, primary_key=True)
    last_name = models.CharField(max_length=50)
    first_name = models.CharField(max_length=50)
    middle_name = models.CharField(max_length=50, blank=True, null=True)
    course = models.ForeignKey(Course, on_delete=models.SET_NULL, null=True)
    year_level = models.PositiveSmallIntegerField()
    section = models.CharField(max_length=20)
    date_added = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=1, choices=STATUS_CHOICES, default='R')

    objects = StudentManager()

    def __str__(self):
        return f"{self.student_id} - {self.last_name}, {self.first_name}"


class Subject(models.Model):
    SEMESTER_CHOICES = [
        (1, '1st Semester'),
        (2, '2nd Semester'),
        (3, 'Summer'),
    ]

    subject_code = models.CharField(max_length=20, primary_key=True)
    subject_title = models.CharField(max_length=100)
    course = models.ForeignKey(Course, on_delete=models.CASCADE, null=True, blank=True)  # Make course optional
    school_year = models.CharField(max_length=20)
    semester = models.PositiveSmallIntegerField(choices=SEMESTER_CHOICES)
    year_level = models.PositiveSmallIntegerField()
    section = models.CharField(max_length=20)
    archive = models.BooleanField(default=False)
    archived = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    archived_date = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['subject_code']

    def __str__(self):
        return f"{self.subject_code} - {self.subject_title}"

    def update_subject_code(self, new_code):
        """Update subject code safely"""
        if new_code != self.subject_code:
            self.subject_code = new_code
        self.save()
        return self

    def save(self, *args, **kwargs):
        # Ensure code is uppercase but don't modify any other fields
        if self.subject_code:
            self.subject_code = self.subject_code.upper()
        super().save(*args, **kwargs)

    def update_details(self, **data):
        """Safe update that doesn't create duplicates"""
        with transaction.atomic():
            original_code = self.subject_code
            
            # First update all non-code fields
            for key, value in data.items():
                if key != 'subject_code':
                    setattr(self, key, value)
            
            # Handle subject code change if needed
            new_code = data.get('subject_code')
            if new_code and new_code.upper() != original_code:
                # Use raw SQL to update the primary key directly
                from django.db import connection
                with connection.cursor() as cursor:
                    cursor.execute(
                        "UPDATE SMSapp_subject SET subject_code = %s WHERE subject_code = %s",
                        [new_code.upper(), original_code]
                    )
                self.subject_code = new_code.upper()
            else:
                self.save()
            
        return self


class StudentSubjectEnrollment(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.student} enrolled in {self.subject}"


class Activity(models.Model):
    activity_id = models.AutoField(primary_key=True)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    activity_name = models.CharField(max_length=100)
    activity_type = models.CharField(max_length=50)
    total_items = models.IntegerField()

    def __str__(self):
        return f"{self.activity_name} ({self.subject.subject_code})"

    def pending_grades(self):
        """Returns number of students without grades for this activity"""
        total_students = self.subject.studentsubjectenrollment_set.count()
        graded_students = self.grade_set.count()
        return total_students - graded_students

    def needs_grading(self):
        """Returns True if there are enrolled students without grades"""
        enrolled_count = self.subject.studentsubjectenrollment_set.count()
        graded_count = Grade.objects.filter(activity=self).count()
        return enrolled_count > graded_count

    def pending_grades_count(self):
        """Returns number of students that need grading"""
        enrolled_count = self.subject.studentsubjectenrollment_set.count()
        graded_count = Grade.objects.filter(activity=self).count()
        return enrolled_count - graded_count


class Grade(models.Model):
    grade_id = models.AutoField(primary_key=True)
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    activity = models.ForeignKey(Activity, on_delete=models.CASCADE)
    student_grade = models.CharField(max_length=50, default='N/A')

    def __str__(self):
        return f"{self.student} - {self.activity}: {self.student_grade}"


class Section(models.Model):
    YEAR_CHOICES = [(i, f'Year {i}') for i in range(1, 5)]
    
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='sections')
    year_level = models.IntegerField(choices=YEAR_CHOICES)
    section_name = models.CharField(max_length=50)  # Changed from max_length=1
    max_students = models.IntegerField(default=40)
    
    class Meta:
        unique_together = ('course', 'year_level', 'section_name')
        ordering = ['course', 'year_level', 'section_name']

    def save(self, *args, **kwargs):
        self.section_name = self.section_name.upper()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.course.course_abv} {self.year_level}-{self.section_name}"

    def is_full(self):
        from .models import Student
        current_count = Student.objects.filter(
            course=self.course,
            year_level=self.year_level,
            section=self.section_name
        ).count()
        return current_count >= self.max_students

    def validate_unique(self, exclude=None):
        if Section.objects.exclude(id=self.id).filter(
            course=self.course,
            year_level=self.year_level,
            section_name=self.section_name
        ).exists():
            raise ValidationError('Section already exists for this course and year level')
        super().validate_unique(exclude)
