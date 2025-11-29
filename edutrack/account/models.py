from django.db import models
from django.contrib.auth.models import AbstractUser
from django.contrib.auth import get_user_model

# ------------------------
# User model
# ------------------------
class User(AbstractUser):
    is_admin = models.BooleanField('Is admin', default=False)
    is_student = models.BooleanField('Is student', default=False)
    is_faculty = models.BooleanField('Is faculty', default=False)
    department = models.CharField(max_length=100, blank=True, null=True)
    course = models.CharField(max_length=100, blank=True, null=True)
    section = models.CharField(max_length=50, blank=True, null=True)
    status = models.CharField(max_length=20, default="Active")  # Active, Inactive, Pending
    ROLE_CHOICES = (
        ('admin', 'Admin'),
        ('faculty', 'Faculty'),
        ('student', 'Student'),
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)

# ------------------------
# Subject model
# ------------------------
class Subject(models.Model):
    code = models.CharField(max_length=20, default='DEFAULT_CODE')
    name = models.CharField(max_length=100)
    department = models.CharField(max_length=100)

    status = models.CharField(max_length=10, choices=[('Active','Active'),('Inactive','Inactive')])

    def __str__(self):
        return f"{self.code} - {self.name}"

# ------------------------
# Faculty model
# ------------------------
class Faculty(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    department = models.CharField(max_length=100)
    subjects = models.ManyToManyField(Subject, blank=True)
    status = models.CharField(max_length=20, default="Active")

    def full_name(self):
        return f"{self.user.first_name} {self.user.last_name}"

    def __str__(self):
        return self.full_name()

# ------------------------
# FacultyAssignment model
# ------------------------
class FacultyAssignment(models.Model):
    faculty = models.ForeignKey(User, limit_choices_to={'is_faculty': True}, on_delete=models.CASCADE)
    subjects = models.ManyToManyField(Subject, blank=True, related_name='assignments')
    status = models.CharField(max_length=10, choices=[('Active','Active'),('Inactive','Inactive')])

    def __str__(self):
        return f"{self.faculty.username} - {self.subjects.count()} subjects"

# ------------------------
# Student model
# ------------------------
class Student(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    year_level = models.IntegerField()
    section = models.CharField(max_length=50)
    course = models.CharField(max_length=100)
    status = models.CharField(max_length=20, default="Active")

# ------------------------
# Section model
# ------------------------
class Section(models.Model):
    grade = models.CharField(max_length=10, choices=[
        ('Grade 7','Grade 7'),
        ('Grade 8','Grade 8'),
        ('Grade 9','Grade 9'),
        ('Grade 10','Grade 10')
    ])
    name = models.CharField(max_length=10)
    adviser = models.CharField(max_length=100)
    number_of_students = models.IntegerField()
    status = models.CharField(max_length=10, choices=[('Active','Active'),('Inactive','Inactive')])

    def __str__(self):
        return f"{self.grade} {self.name}"

# ------------------------
# SchoolYear model
# ------------------------
class SchoolYear(models.Model):
    year = models.CharField(max_length=20, unique=True)
    status = models.CharField(max_length=20, choices=[('Active','Active'),('Inactive','Inactive')])

    def __str__(self):
        return self.year

# ------------------------
# AssignedSubject model
# ------------------------
class AssignedSubject(models.Model):
    grade_level = models.CharField(max_length=10, choices=[
        ('Grade 7','Grade 7'),
        ('Grade 8','Grade 8'),
        ('Grade 9','Grade 9'),
        ('Grade 10','Grade 10')
    ])
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    status = models.CharField(max_length=10, choices=[('Active','Active'),('Inactive','Inactive')])

    def __str__(self):
        return f"{self.grade_level} - {self.subject.name} ({self.status})"

# ------------------------
# StudentRecord model
# ------------------------
class StudentRecord(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('graduated', 'Graduated'),
        ('transferred', 'Transferred'),
    ]
    SECTION_CHOICES = [
        ('Grade 7', 'Grade 7'),
        ('Grade 8', 'Grade 8'),
        ('Grade 9', 'Grade 9'),
        ('Grade 10', 'Grade 10'),
    ]
    GENDER_CHOICES = [
        ('Male', 'Male'),
        ('Female', 'Female'),

    ]
    student_id = models.PositiveIntegerField()
    fullname = models.CharField(max_length=100)
    grade_and_section = models.CharField(max_length=20, choices=SECTION_CHOICES, default='active')
    gender = models.CharField(max_length=20, choices=GENDER_CHOICES, default='active')
    age = models.PositiveIntegerField()
    address = models.CharField(max_length=200)
    parent = models.CharField(max_length=100)
    parent_contact = models.PositiveIntegerField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')

    def __str__(self):
        return self.fullname

# ------------------------
# GradingComponent model
# ------------------------
class GradingComponent(models.Model):
    component = models.CharField(max_length=100)
    weight = models.FloatField()
    status = models.CharField(max_length=10, choices=[('Active','Active'),('Inactive','Inactive')])

    def __str__(self):
        return f"{self.component} ({self.weight}%)"

# ------------------------
# AuditTrail model
# ------------------------
class AuditTrail(models.Model):
    action = models.CharField(max_length=200)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    timestamp = models.DateTimeField(auto_now_add=True)

class Score(models.Model):
    student = models.ForeignKey(StudentRecord, on_delete=models.CASCADE)
    quiz = models.IntegerField(default=0)
    exam = models.IntegerField(default=0)
    project = models.IntegerField(default=0)
    attendance = models.IntegerField(default=0)

    def __str__(self):
        return f"{self.student.fullname} Score"


from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender=StudentRecord)
def create_student_score(sender, instance, created, **kwargs):
    if created:
        Score.objects.get_or_create(student=instance)

