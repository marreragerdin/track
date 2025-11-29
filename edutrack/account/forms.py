from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import User, Student, Faculty, Subject, StudentRecord, QuizScore, ExamScore, ProjectScore


class LoginForm(forms.Form):
    username = forms.CharField(
        widget= forms.TextInput(
            attrs={
                "class": "form-control"
            }
        )
    )
    password = forms.CharField(
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control"
            }
        )
    )


class StudentForm(forms.Form):
    first_name = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        label='First Name'
    )
    last_name = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        label='Last Name'
    )
    username = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        label='Username'
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        label='Password'
    )
    grade_level = forms.ChoiceField(
        choices=[
            ('Grade 7', 'Grade 7'),
            ('Grade 8', 'Grade 8'),
            ('Grade 9', 'Grade 9'),
            ('Grade 10', 'Grade 10'),
        ],
        widget=forms.Select(attrs={'class': 'form-control', 'id': 'id_grade_level'}),
        label='Grade Level'
    )
    section = forms.ModelChoiceField(
        queryset=None,  # Will be set dynamically in the view
        widget=forms.Select(attrs={'class': 'form-control', 'id': 'id_section'}),
        label='Section',
        required=True,
        help_text='Select section based on grade level'
    )
    gender = forms.ChoiceField(
        choices=[
            ('Male', 'Male'),
            ('Female', 'Female'),
        ],
        widget=forms.Select(attrs={'class': 'form-control'}),
        label='Gender'
    )
    age = forms.IntegerField(
        widget=forms.NumberInput(attrs={'class': 'form-control'}),
        label='Age',
        min_value=1,
        max_value=100
    )
    address = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        label='Address'
    )
    parent = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        label='Parent/Guardian Name'
    )
    parent_contact = forms.IntegerField(
        widget=forms.NumberInput(attrs={'class': 'form-control'}),
        label='Parent/Guardian Contact',
        help_text='Phone number'
    )
    status = forms.ChoiceField(
        choices=[
            ('active', 'Active'),
            ('inactive', 'Inactive'),
            ('graduated', 'Graduated'),
            ('transferred', 'Transferred'),
        ],
        widget=forms.Select(attrs={'class': 'form-control'}),
        initial='active',
        label='Status'
    )



class FacultyForm(forms.ModelForm):
    first_name = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        label='First Name'
    )
    last_name = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        label='Last Name'
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={'class': 'form-control'}),
        label='Email'
    )
    username = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        label='Username'
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        required=True,
        label='Password'
    )
    department = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        label='Department'
    )
    subjects = forms.ModelMultipleChoiceField(
        queryset=Subject.objects.all(),
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
        required=False,
        label='Subjects'
    )
    status = forms.ChoiceField(
        choices=[
            ('Active', 'Active'),
            ('Inactive', 'Inactive'),
        ],
        widget=forms.Select(attrs={'class': 'form-select'}),
        initial='Active',
        label='Status'
    )

    class Meta:
        model = Faculty
        fields = ['first_name', 'last_name', 'email', 'username', 'password', 'department', 'subjects', 'status']




class UserForm(forms.ModelForm):
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        required=True,
        label='Password'
    )
    first_name = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        label='First Name'
    )
    last_name = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        label='Last Name'
    )
    username = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        label='Username'
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={'class': 'form-control'}),
        label='Email'
    )
    
    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'password']

    def save(self, commit=True):
        user = super().save(commit=False)
        user.is_admin = True
        user.role = 'admin'
        if self.cleaned_data['password']:
            user.set_password(self.cleaned_data['password'])
        if commit:
            user.save()
        return user

from django import forms
from .models import SchoolYear, Subject, Section, FacultyAssignment, GradingComponent
from django.contrib.auth import get_user_model

User = get_user_model()

class SchoolYearForm(forms.ModelForm):
    class Meta:
        model = SchoolYear
        fields = ['year', 'status']

class SubjectForm(forms.ModelForm):
    sections_count = forms.IntegerField(min_value=1, required=False, label="Number of Sections")

    class Meta:
        model = Subject
        fields = ['code', 'name', 'grade_level', 'department', 'status']

class SectionForm(forms.ModelForm):
    class Meta:
        model = Section
        fields = ['grade', 'name', 'adviser', 'number_of_students', 'status']

class FacultyAssignmentForm(forms.ModelForm):
    faculty = forms.ModelMultipleChoiceField(queryset=User.objects.filter(is_faculty=True), widget=forms.CheckboxSelectMultiple)

    class Meta:
        model = FacultyAssignment
        fields = ['subjects', 'faculty', 'status']

class GradingComponentForm(forms.ModelForm):
    class Meta:
        model = GradingComponent
        fields = ['component', 'weight', 'status']

class RecordForm(forms.Form):
    student_id = forms.IntegerField(
        widget=forms.NumberInput(attrs={'class': 'form-control'}),
        label='Student ID',
        required=True
    )
    fullname = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        label='Fullname',
        max_length=100,
        required=True
    )
    grade_level = forms.ChoiceField(
        choices=[
            ('Grade 7', 'Grade 7'),
            ('Grade 8', 'Grade 8'),
            ('Grade 9', 'Grade 9'),
            ('Grade 10', 'Grade 10'),
        ],
        widget=forms.Select(attrs={'class': 'form-control', 'id': 'id_grade_level_record'}),
        label='Grade Level',
        required=True
    )
    section = forms.ModelChoiceField(
        queryset=None,  # Will be set dynamically
        widget=forms.Select(attrs={'class': 'form-control', 'id': 'id_section_record'}),
        label='Section',
        required=True,
        help_text='Select section based on grade level'
    )
    gender = forms.ChoiceField(
        choices=[
            ('Male', 'Male'),
            ('Female', 'Female'),
        ],
        widget=forms.Select(attrs={'class': 'form-control'}),
        label='Gender',
        required=True
    )
    age = forms.IntegerField(
        widget=forms.NumberInput(attrs={'class': 'form-control'}),
        label='Age',
        min_value=1,
        max_value=100,
        required=True
    )
    address = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        label='Address',
        max_length=200,
        required=True
    )
    parent = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        label='Parent/Guardian Name',
        max_length=100,
        required=True
    )
    parent_contact = forms.IntegerField(
        widget=forms.NumberInput(attrs={'class': 'form-control'}),
        label='Parent/Guardian Contact',
        help_text='Phone number',
        required=True
    )
    status = forms.ChoiceField(
        choices=[
            ('active', 'Active'),
            ('inactive', 'Inactive'),
            ('graduated', 'Graduated'),
            ('transferred', 'Transferred'),
        ],
        widget=forms.Select(attrs={'class': 'form-control'}),
        initial='active',
        label='Status',
        required=True
    )

class QuizSetupForm(forms.Form):
    subject = forms.ModelChoiceField(
        queryset=Subject.objects.filter(status='Active'),
        widget=forms.Select(attrs={'class': 'form-control'}),
        label='Subject'
    )
    number_of_quizzes = forms.IntegerField(
        min_value=1,
        max_value=20,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Enter number of quizzes'}),
        label='Number of Quizzes',
        help_text='How many quiz scores will be recorded for this subject?'
    )

class ExamSetupForm(forms.Form):
    subject = forms.ModelChoiceField(
        queryset=Subject.objects.filter(status='Active'),
        widget=forms.Select(attrs={'class': 'form-control'}),
        label='Subject'
    )
    number_of_exams = forms.IntegerField(
        min_value=1,
        max_value=20,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Enter number of exams'}),
        label='Number of Exams',
        help_text='How many exam scores will be recorded for this subject?'
    )

class ProjectSetupForm(forms.Form):
    subject = forms.ModelChoiceField(
        queryset=Subject.objects.filter(status='Active'),
        widget=forms.Select(attrs={'class': 'form-control'}),
        label='Subject'
    )
    number_of_projects = forms.IntegerField(
        min_value=1,
        max_value=20,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Enter number of projects'}),
        label='Number of Projects',
        help_text='How many project scores will be recorded for this subject?'
    )

class WeeklyAttendanceSessionForm(forms.Form):
    subject = forms.ModelChoiceField(
        queryset=Subject.objects.filter(status='Active'),
        widget=forms.Select(attrs={'class': 'form-control'}),
        label='Subject'
    )
    week_number = forms.IntegerField(
        min_value=1,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Enter week number'}),
        label='Week Number',
        help_text='Which week is this? (e.g., 1, 2, 3...)'
    )
    week_start_date = forms.DateField(
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        label='Week Start Date'
    )
    week_end_date = forms.DateField(
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        label='Week End Date'
    )
    sessions_per_week = forms.IntegerField(
        min_value=1,
        max_value=7,
        initial=4,
        widget=forms.NumberInput(attrs={'class': 'form-control'}),
        label='Sessions per Week',
        help_text='Number of sessions in this week (usually 4)'
    )