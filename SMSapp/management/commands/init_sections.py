from django.core.management.base import BaseCommand
from SMSapp.models import Course, Section

class Command(BaseCommand):
    help = 'Initialize sections for all courses'

    def handle(self, *args, **kwargs):
        courses = Course.objects.all()
        sections = ['A', 'B', 'C']
        
        for course in courses:
            for year in range(1, 5):  # Years 1-4
                for section in sections:
                    Section.objects.get_or_create(
                        course=course,
                        year_level=year,
                        section_name=section
                    )
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'Created section {section} for {course.course_abv} Year {year}'
                        )
                    )
