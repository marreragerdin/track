from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import User, Student, Faculty, Subject, StudentRecord


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


class StudentForm(forms.ModelForm):
    first_name = forms.CharField()
    last_name = forms.CharField()
    username = forms.CharField()
    password = forms.CharField(widget=forms.PasswordInput)

    class Meta:
        model = Student
        fields = ['first_name', 'last_name', 'username', 'password', 'year_level', 'section', 'course', 'status']



class FacultyForm(forms.ModelForm):
    first_name = forms.CharField()
    last_name = forms.CharField()
    email = forms.EmailField()
    username = forms.CharField()
    password = forms.CharField(widget=forms.PasswordInput, required=False)
    subjects = forms.ModelMultipleChoiceField(
        queryset=Subject.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False
    )

    class Meta:
        model = Faculty
        fields = ['first_name', 'last_name','email', 'username', 'password', 'department', 'subjects', 'status']




class UserForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput, required=False)
    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'is_admin', 'is_faculty', 'is_student', 'department', 'course', 'section', 'status', 'password']

    def save(self, commit=True):
        user = super().save(commit=False)
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
        fields = ['code', 'name', 'status']

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

class RecordForm(forms.ModelForm):
    class Meta:
        model = StudentRecord
        fields = ['student_id', 'fullname', 'grade_and_section', 'gender', 'age', 'address', 'parent', 'parent_contact', 'status']
        labels = {
            'student_id': 'Student ID',
            'fullname': 'Fullname',
            'grade_and_section': 'Grade & Section',
            'gender': 'Gender',
            'age': 'Age',
            'address': 'Address',
            'parent': 'Parent/Guardian',
            'parent_contact': 'Parent/Guardian Contact',
            'status': 'Status'
        }
        widgets = {
            'student_id': forms.NumberInput(attrs={'class': 'form-control'}),
            'fullname':forms.TextInput(attrs={'class': 'form-control'}),
            'grade_and_section':forms.Select(attrs={'class': 'form-control'}),
            'gender':forms.Select(attrs={'class': 'form-control'}),
            'age':forms.NumberInput(attrs={'class': 'form-control'}),
            'address':forms.TextInput(attrs={'class': 'form-control'}),
            'parent':forms.TextInput(attrs={'class': 'form-control'}),
            'parent_contact':forms.NumberInput(attrs={'class': 'form-control'}),
            'status':forms.Select(attrs={'class': 'form-control'}),
        }