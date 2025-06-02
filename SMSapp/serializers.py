from rest_framework import serializers
from .models import Subject, Activity, StudentSubjectEnrollment, Student, Course, Grade, Section
from datetime import date
from django.db import transaction

class StudentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Student
        fields = ['student_id', 'last_name', 'first_name', 'middle_name', 
                 'course', 'year_level', 'section', 'status']

    def _get_course(self, course_data):
        if isinstance(course_data, str):
            try:
                return Course.objects.get(course_abv=course_data)
            except Course.DoesNotExist:
                raise serializers.ValidationError({'course': 'Invalid course abbreviation'})
        return course_data

    def create(self, validated_data):
        # Handle course
        course = validated_data.get('course')
        validated_data['course'] = self._get_course(course)
        return Student.objects.create(**validated_data)

    def update(self, instance, validated_data):
        # Handle course
        course = validated_data.get('course')
        if isinstance(course, str):
            try:
                validated_data['course'] = Course.objects.get(course_abv=course)
            except Course.DoesNotExist:
                raise serializers.ValidationError({'course': 'Invalid course abbreviation'})

        # Update fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if instance.course:
            data['course'] = instance.course.course_abv
            data['course_name'] = instance.course.course_name
        return data

class SubjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subject
        fields = ['subject_code', 'subject_title', 'course', 'school_year', 
                 'semester', 'year_level', 'section', 'archive']
        read_only_fields = ['archive']

    def validate(self, data):
        # Only check for duplicate subject code if it's being changed
        if self.instance and 'subject_code' in data:
            new_code = data['subject_code'].upper()
            if new_code != self.instance.subject_code:
                if Subject.objects.filter(subject_code=new_code).exists():
                    raise serializers.ValidationError({
                        'subject_code': 'Subject with this code already exists'
                    })
        
        # Validate year level
        if data.get('year_level') and (data['year_level'] < 1 or data['year_level'] > 4):
            raise serializers.ValidationError({"year_level": "Year level must be between 1 and 4"})
        return data

    def update(self, instance, validated_data):
        """Update existing subject without creating new one"""
        try:
            with transaction.atomic():
                # Update the instance directly
                instance.update_details(**validated_data)
                return instance
        except Exception as e:
            raise serializers.ValidationError(str(e))

class ActivitySerializer(serializers.ModelSerializer):
    class Meta:
        model = Activity
        fields = ['activity_id', 'subject', 'activity_type', 'activity_name', 'total_items']

    def to_representation(self, instance):
        data = super().to_representation(instance)
        # Include these fields in every response
        data['activity_id'] = instance.activity_id
        data['activity_type'] = instance.activity_type
        data['activity_name'] = instance.activity_name
        data['total_items'] = instance.total_items
        return data

class StudentSubjectEnrollmentSerializer(serializers.ModelSerializer):
    student = StudentSerializer(read_only=True)
    
    class Meta:
        model = StudentSubjectEnrollment
        fields = '__all__'

class CourseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Course
        fields = ['course_abv', 'course_name']

    def validate(self, data):
        # Convert course_abv to uppercase
        if 'course_abv' in data:
            data['course_abv'] = data['course_abv'].strip().upper()
            
        # Validate course_abv format (alphanumeric)
        if not data['course_abv'].replace('-', '').isalnum():
            raise serializers.ValidationError({
                'course_abv': 'Course code must contain only letters, numbers, and hyphens'
            })

        # Check for duplicates
        if Course.objects.filter(course_abv=data['course_abv']).exists():
            if not self.instance or self.instance.course_abv != data['course_abv']:
                raise serializers.ValidationError({
                    'course_abv': 'A course with this code already exists'
                })

        return data

    def create(self, validated_data):
        try:
            return super().create(validated_data)
        except Exception as e:
            raise serializers.ValidationError(str(e))

class GradeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Grade
        fields = ['grade_id', 'student', 'activity', 'student_grade']

class SectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Section
        fields = ['id', 'course', 'year_level', 'section_name']

    def validate(self, data):
        try:
            # Handle course value if it's a string
            if isinstance(data.get('course'), str):
                try:
                    data['course'] = Course.objects.get(course_abv=data['course'])
                except Course.DoesNotExist:
                    raise serializers.ValidationError({'course': 'Invalid course code'})

            # Validate year_level
            if 'year_level' in data:
                try:
                    year_level = int(data['year_level'])
                    if not 1 <= year_level <= 4:
                        raise serializers.ValidationError({'year_level': 'Year level must be between 1 and 4'})
                    data['year_level'] = year_level
                except (ValueError, TypeError):
                    raise serializers.ValidationError({'year_level': 'Invalid year level format'})

            # Validate section_name - allow alphanumeric characters
            if 'section_name' in data:
                section_name = data['section_name'].strip().upper()
                if not section_name:
                    raise serializers.ValidationError({'section_name': 'Section name cannot be empty'})
                if not section_name.replace('-', '').replace('_', '').isalnum():
                    raise serializers.ValidationError({'section_name': 'Section name must contain only letters, numbers, hyphens and underscores'})
                data['section_name'] = section_name

            # Check for duplicates
            existing = Section.objects.filter(
                course=data.get('course', self.instance.course if self.instance else None),
                year_level=data.get('year_level', self.instance.year_level if self.instance else None),
                section_name=data.get('section_name', self.instance.section_name if self.instance else None)
            )
            if self.instance:
                existing = existing.exclude(id=self.instance.id)
            if existing.exists():
                raise serializers.ValidationError('A section with these details already exists')

            return data
            
        except serializers.ValidationError:
            raise
        except Exception as e:
            print(f"Validation error: {str(e)}")
            raise serializers.ValidationError(str(e))

    def create(self, validated_data):
        try:
            return Section.objects.create(**validated_data)
        except Exception as e:
            print(f"Error creating section: {str(e)}")  # Debug log
            raise serializers.ValidationError(str(e))

    def to_representation(self, instance):
        return {
            'id': instance.id,
            'course': instance.course.course_abv,
            'course_name': instance.course.course_name,
            'year_level': instance.year_level,
            'section_name': instance.section_name
        }
