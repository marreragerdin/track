from django.contrib import admin
from .models import User, Faculty, Student
from .models import User, SchoolYear, Subject, Section, FacultyAssignment, GradingComponent, Student, Faculty, AuditTrail, StudentRecord,AssignedSubject
from .models import Subject, Faculty



@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ('id', 'full_name', 'year_level', 'section', 'status')
    search_fields = ('user__first_name', 'user__last_name')

    def full_name(self, obj):
        return f"{obj.user.first_name} {obj.user.last_name}"

    full_name.short_description = 'Name'


@admin.register(Faculty)
class FacultyAdmin(admin.ModelAdmin):
    list_display = ('id', 'full_name', 'email', 'department', 'subject_list', 'status')

    def full_name(self, obj):
        return f"{obj.user.first_name} {obj.user.last_name}"

    def email(self, obj):
        return obj.user.email

    def subject_list(self, obj):
        return ", ".join([s.name for s in obj.subjects.all()])

    subject_list.short_description = 'Subjects'

@admin.register(User)
class CustomUserAdmin(admin.ModelAdmin):
    list_display = ('role', 'full_name', 'email', 'status')
    search_fields = ('first_name', 'last_name', 'email')

    def full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}"

    full_name.short_description = 'Name'


# Register other models
@admin.register(SchoolYear)
class SchoolYearAdmin(admin.ModelAdmin):
    list_display = ('year','status')
    list_filter = ('status',)
    search_fields = ('year',)

@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ('code','name','status')
    list_filter = ('status',)
    search_fields = ('name','code')

@admin.register(Section)
class SectionAdmin(admin.ModelAdmin):
    list_display = ('grade','name','adviser','number_of_students','status')
    list_filter = ('grade','status')
    search_fields = ('name','adviser')

@admin.register(FacultyAssignment)
class FacultyAssignmentAdmin(admin.ModelAdmin):
    list_display = ('faculty', 'get_subjects')

    def get_subjects(self, obj):
        return ", ".join([sub.name for sub in obj.subjects.all()])
    get_subjects.short_description = "Subjects"


@admin.register(GradingComponent)
class GradingComponentAdmin(admin.ModelAdmin):
    list_display = ('component','weight','status')
    list_filter = ('status',)
    search_fields = ('component',)

admin.site.register(StudentRecord)
admin.site.register(AssignedSubject)