# ==================== IMPORTS ====================
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, get_user_model
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.contrib.messages import success
from django.db.models import Q, Avg
from django.http import JsonResponse, HttpResponse
from django.core.paginator import Paginator
from django.utils import timezone
from datetime import datetime, timedelta
from io import BytesIO

# Model imports
from .models import (
    User, Student, Faculty, Subject, AuditTrail, SchoolYear, Section,
    FacultyAssignment, GradingComponent, StudentRecord, QuizScore, ExamScore,
    ProjectScore, AssignedSubject, WeeklyAttendanceSession, WeeklyAttendanceRecord,
    MLPredictionStatus, Score
)

# Form imports
from .forms import (
    LoginForm, UserForm, StudentForm, FacultyForm, SchoolYearForm, SubjectForm,
    SectionForm, FacultyAssignmentForm, GradingComponentForm, QuizSetupForm,
    ExamSetupForm, ProjectSetupForm, WeeklyAttendanceSessionForm, RecordForm
)

# ML imports (optional)
try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False

try:
    from sklearn.linear_model import LinearRegression
    from sklearn.tree import DecisionTreeClassifier
    from sklearn.model_selection import train_test_split
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False




# Create your views here.


def index(request):
    return render(request, 'index.html')




def login_view(request):
    form = LoginForm(request.POST or None)
    msg = None
    if request.method == 'POST' and form.is_valid():
        username = form.cleaned_data.get('username')
        password = form.cleaned_data.get('password')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            # Redirect based on role
            if user.role == 'admin':
                return redirect('adminpage')
            elif user.role == 'student':
                return redirect('student_dashboard')
            elif user.role == 'faculty':
                return redirect('faculty')
        else:
            msg = 'Invalid credentials'
    return render(request, 'login.html', {'form': form, 'msg': msg})




def admin(request):
    """Admin page - redirects to admin dashboard"""
    return admin_dashboard(request)

def get_sections_by_grade(request):
    """API endpoint to get sections by grade level"""
    from django.http import JsonResponse
    grade = request.GET.get('grade', '')
    sections = Section.objects.filter(grade=grade, status='Active').values('id', 'name')
    return JsonResponse({'sections': list(sections)})


def student(request):
    return render(request,'student.html')

@login_required
def student_dashboard(request):
    """Student dashboard showing only their own information"""
    if request.user.role != 'student':
        messages.error(request, 'Access denied. This page is for students only.')
        return redirect('adminpage' if request.user.role == 'admin' else 'faculty')

    # Try to find student record by matching User's name to StudentRecord's fullname
    student_record = None
    try:
        # First, try to match by fullname (most reliable)
        user_fullname = f"{request.user.first_name} {request.user.last_name}".strip()
        if user_fullname:
            student_record = StudentRecord.objects.filter(
                fullname__iexact=user_fullname
            ).first()

        # If not found, try matching by username as student_id (if numeric)
        if not student_record:
            try:
                student_id = int(request.user.username)
                student_record = StudentRecord.objects.filter(
                    student_id=student_id
                ).first()
            except (ValueError, TypeError):
                pass

        # Last resort: try partial name match
        if not student_record and user_fullname:
            student_record = StudentRecord.objects.filter(
                fullname__icontains=request.user.first_name
            ).first()
    except Exception as e:
        pass

    if not student_record:
        messages.warning(request, 'Student record not found. Please contact administrator.')
        return render(request, 'student_dashboard.html', {
            'student_record': None,
            'student_score_data': [],
            'tab': 'student'
        })

    # Get all subjects with scores for this student
    subjects_with_scores = Subject.objects.filter(
        Q(quiz_scores__student=student_record) |
        Q(exam_scores__student=student_record) |
        Q(project_scores__student=student_record) |
        Q(attendance_sessions__attendance_records__student=student_record)
    ).distinct().order_by('name')

    # Calculate averages per subject
    student_subjects = []
    for subject in subjects_with_scores:
        # Calculate quiz average
        quiz_scores = QuizScore.objects.filter(student=student_record, subject=subject)
        avg_quiz = None
        if quiz_scores.exists():
            scores = [float(qs.score) for qs in quiz_scores]
            avg_quiz = sum(scores) / len(scores) if scores else None

        # Calculate exam average
        exam_scores = ExamScore.objects.filter(student=student_record, subject=subject)
        avg_exam = None
        if exam_scores.exists():
            scores = [float(es.score) for es in exam_scores]
            avg_exam = sum(scores) / len(scores) if scores else None

        # Calculate project average
        project_scores = ProjectScore.objects.filter(student=student_record, subject=subject)
        avg_project = None
        if project_scores.exists():
            scores = [float(ps.score) for ps in project_scores]
            avg_project = sum(scores) / len(scores) if scores else None

        # Calculate attendance
        attendance_sessions = WeeklyAttendanceSession.objects.filter(subject=subject)
        avg_attendance = None
        if attendance_sessions.exists():
            overall_present = 0
            overall_total = 0
            for session in attendance_sessions:
                try:
                    record = WeeklyAttendanceRecord.objects.get(session=session, student=student_record)
                    summary = record.get_attendance_summary()
                    sessions_list = summary.split(',')
                    present_count = sum(1 for s in sessions_list if s == 'P')
                    total_count = len([s for s in sessions_list if s != '-'])
                    overall_present += present_count
                    overall_total += total_count
                except WeeklyAttendanceRecord.DoesNotExist:
                    continue
            if overall_total > 0:
                avg_attendance = round((overall_present / overall_total) * 100, 2)

        # Calculate grade from available scores (no need for all)
        available_scores = []
        if avg_quiz is not None:
            available_scores.append(avg_quiz)
        if avg_exam is not None:
            available_scores.append(avg_exam)
        if avg_project is not None:
            available_scores.append(avg_project)
        if avg_attendance is not None:
            available_scores.append(avg_attendance)

        grade = None
        performance_category = None
        if available_scores:
            grade = sum(available_scores) / len(available_scores)
            # Categorize: <70 = At Risk, 70-79 = Average, 80-89 = Good, 90+ = Excellent
            if grade >= 90:
                performance_category = 'Excellent'
            elif grade >= 80:
                performance_category = 'Good'
            elif grade >= 70:
                performance_category = 'Average'
            else:
                performance_category = 'At Risk'

        student_subjects.append({
            'subject': subject,
            'quiz_average': avg_quiz,
            'exam_average': avg_exam,
            'project_average': avg_project,
            'attendance_average': avg_attendance,
            'grade': grade,
            'performance_category': performance_category,
        })

    return render(request, 'student_dashboard.html', {
        'student_record': student_record,
        'student_subjects': student_subjects,
        'tab': 'student'
    })

@login_required
def student_scores(request):
    """Student view of their scores (same as dashboard but focused on scores)"""
    if request.user.role != 'student':
        messages.error(request, 'Access denied.')
        return redirect('adminpage' if request.user.role == 'admin' else 'faculty')

    # Same logic as student_dashboard
    student_record = None
    try:
        student_record = StudentRecord.objects.filter(student_id=request.user.username).first()
        if not student_record:
            student_record = StudentRecord.objects.filter(fullname__icontains=request.user.username).first()
    except:
        pass

    if not student_record:
        messages.warning(request, 'Student record not found.')
        return redirect('student_dashboard')

    # Get subjects with scores
    subjects_with_scores = Subject.objects.filter(
        Q(quiz_scores__student=student_record) |
        Q(exam_scores__student=student_record) |
        Q(project_scores__student=student_record) |
        Q(attendance_sessions__attendance_records__student=student_record)
    ).distinct().order_by('name')

    student_subjects = []
    for subject in subjects_with_scores:
        quiz_scores = QuizScore.objects.filter(student=student_record, subject=subject)
        avg_quiz = None
        if quiz_scores.exists():
            scores = [float(qs.score) for qs in quiz_scores]
            avg_quiz = sum(scores) / len(scores) if scores else None

        exam_scores = ExamScore.objects.filter(student=student_record, subject=subject)
        avg_exam = None
        if exam_scores.exists():
            scores = [float(es.score) for es in exam_scores]
            avg_exam = sum(scores) / len(scores) if scores else None

        project_scores = ProjectScore.objects.filter(student=student_record, subject=subject)
        avg_project = None
        if project_scores.exists():
            scores = [float(ps.score) for ps in project_scores]
            avg_project = sum(scores) / len(scores) if scores else None

        attendance_sessions = WeeklyAttendanceSession.objects.filter(subject=subject)
        avg_attendance = None
        if attendance_sessions.exists():
            overall_present = 0
            overall_total = 0
            for session in attendance_sessions:
                try:
                    record = WeeklyAttendanceRecord.objects.get(session=session, student=student_record)
                    summary = record.get_attendance_summary()
                    sessions_list = summary.split(',')
                    present_count = sum(1 for s in sessions_list if s == 'P')
                    total_count = len([s for s in sessions_list if s != '-'])
                    overall_present += present_count
                    overall_total += total_count
                except WeeklyAttendanceRecord.DoesNotExist:
                    continue
            if overall_total > 0:
                avg_attendance = round((overall_present / overall_total) * 100, 2)

        grade = None
        if avg_quiz is not None and avg_exam is not None and avg_project is not None and avg_attendance is not None:
            grade = (avg_quiz + avg_exam + avg_project + avg_attendance) / 4

        student_subjects.append({
            'subject': subject,
            'quiz_average': avg_quiz,
            'exam_average': avg_exam,
            'project_average': avg_project,
            'attendance_average': avg_attendance,
            'grade': grade,
        })

    return render(request, 'student_scores.html', {
        'student_record': student_record,
        'student_subjects': student_subjects,
        'tab': 'student'
    })


@login_required
def faculty(request):
    """Faculty dashboard - shows assigned subjects and student records"""
    if request.user.role != 'faculty':
        messages.error(request, 'Access denied.')
        return redirect('adminpage' if request.user.role == 'admin' else 'student_dashboard')

    # Get assigned subjects for this faculty
    assignments = FacultyAssignment.objects.filter(
        faculty=request.user,
        status='Active'
    )
    assigned_subjects = []
    assigned_subject_ids = []
    for assignment in assignments:
        assigned_subjects.extend(assignment.subjects.all())
        assigned_subject_ids.extend(assignment.subjects.values_list('id', flat=True))
    assigned_subjects = list(set(assigned_subjects))  # Remove duplicates
    assigned_subject_ids = list(set(assigned_subject_ids))

    # Filter students by grade level of assigned subjects
    if assigned_subject_ids:
        assigned_subjects_objs = Subject.objects.filter(id__in=assigned_subject_ids)
        assigned_grade_levels = AssignedSubject.objects.filter(
            subject__in=assigned_subjects_objs,
            status='Active'
        ).values_list('grade_level', flat=True).distinct()

        # Filter students whose grade_and_section starts with any assigned grade level
        all_students = StudentRecord.objects.filter(status='active')
        filtered_student_ids = []
        for student in all_students:
            if student.grade_and_section:
                # Extract grade level from grade_and_section (format: "Grade 7 - A" or just "Grade 7")
                student_grade = student.grade_and_section.split(' - ')[0].strip()
                if student_grade in assigned_grade_levels:
                    filtered_student_ids.append(student.id)
        student_records = StudentRecord.objects.filter(id__in=filtered_student_ids).order_by('fullname')
    else:
        # No assigned subjects - show empty
        student_records = StudentRecord.objects.none()

    # Get statistics for assigned subjects
    total_students = student_records.count()

    context = {
        'assigned_subjects': assigned_subjects,
        'student_records': student_records,
        'total_students': total_students,
        'tab': 'faculty'
    }
    return render(request, 'faculty.html', context)

@login_required
def admin_dashboard(request):
    # Count users by role
    total_admins = User.objects.filter(role='admin').count()
    total_faculty = User.objects.filter(role='faculty').count()
    total_students = User.objects.filter(role='student').count()
    total_student_records = StudentRecord.objects.count()

    # Get active school year
    active_school_year = "2025-2026"  # Replace with dynamic model if you have one

    # Get grade distribution for visualization - count unique students
    at_risk_students = set()
    excellent_students = set()
    good_students = set()
    average_students = set()

    # Process all active students
    for student in StudentRecord.objects.filter(status='active'):
        subjects_with_scores = Subject.objects.filter(
            Q(quiz_scores__student=student) |
            Q(exam_scores__student=student) |
            Q(project_scores__student=student) |
            Q(attendance_sessions__attendance_records__student=student)
        ).distinct()

        # Track student's worst grade across all subjects
        student_worst_grade = None
        student_best_grade = None

        for subject in subjects_with_scores:
            quiz_scores = QuizScore.objects.filter(student=student, subject=subject)
            exam_scores = ExamScore.objects.filter(student=student, subject=subject)
            project_scores = ProjectScore.objects.filter(student=student, subject=subject)
            attendance_sessions = WeeklyAttendanceSession.objects.filter(subject=subject)

            avg_quiz = None
            if quiz_scores.exists():
                scores = [float(qs.score) for qs in quiz_scores]
                avg_quiz = sum(scores) / len(scores) if scores else None

            avg_exam = None
            if exam_scores.exists():
                scores = [float(es.score) for es in exam_scores]
                avg_exam = sum(scores) / len(scores) if scores else None

            avg_project = None
            if project_scores.exists():
                scores = [float(ps.score) for ps in project_scores]
                avg_project = sum(scores) / len(scores) if scores else None

            avg_attendance = None
            if attendance_sessions.exists():
                overall_present = 0
                overall_total = 0
                for session in attendance_sessions:
                    try:
                        record = WeeklyAttendanceRecord.objects.get(session=session, student=student)
                        summary = record.get_attendance_summary()
                        sessions_list = summary.split(',')
                        present_count = sum(1 for s in sessions_list if s == 'P')
                        total_count = len([s for s in sessions_list if s != '-'])
                        overall_present += present_count
                        overall_total += total_count
                    except WeeklyAttendanceRecord.DoesNotExist:
                        continue
                if overall_total > 0:
                    avg_attendance = round((overall_present / overall_total) * 100, 2)

            # Calculate grade from available scores
            available_scores = []
            if avg_quiz is not None:
                available_scores.append(avg_quiz)
            if avg_exam is not None:
                available_scores.append(avg_exam)
            if avg_project is not None:
                available_scores.append(avg_project)
            if avg_attendance is not None:
                available_scores.append(avg_attendance)

            if available_scores:
                grade = sum(available_scores) / len(available_scores)
                if student_worst_grade is None or grade < student_worst_grade:
                    student_worst_grade = grade
                if student_best_grade is None or grade > student_best_grade:
                    student_best_grade = grade

        # Categorize student based on worst grade (if they have any at-risk subject, they're at risk)
        if student_worst_grade is not None:
            if student_worst_grade < 70:
                at_risk_students.add(student.id)
            elif student_best_grade >= 90:
                excellent_students.add(student.id)
            elif student_best_grade >= 80:
                good_students.add(student.id)
            elif student_best_grade >= 70:
                average_students.add(student.id)

    # Calculate counts (unique students)
    excellent = len(excellent_students)
    good = len(good_students)
    average = len(average_students)
    at_risk = len(at_risk_students)

    context = {
        'total_admins': total_admins,
        'total_faculty': total_faculty,
        'total_students': total_students,
        'total_student_records': total_student_records,
        'active_school_year': active_school_year,
        'excellent_count': excellent,
        'good_count': good,
        'average_count': average,
        'at_risk_count': at_risk,
        'grade_distribution': {
            'Excellent (90+)': excellent,
            'Good (80-89)': good,
            'Average (70-79)': average,
            'At Risk (<70)': at_risk,
        }
    }
    return render(request, 'admin.html', context)

def faculty_dashboard(request):
    faculty = request.user.faculty
    assigned_classes = faculty.subjects.all()
    pending_scores = 0  # Implement logic if you have Score model
    context = {
        'assigned_classes': assigned_classes,
        'pending_scores': pending_scores
    }
    return render(request, 'faculty.html', context)


# ==================== USER MANAGEMENT ====================

@login_required
def manage_user(request):
    tab = request.GET.get('tab', 'students')
    search = request.GET.get('search', '')
    gender_filter = request.GET.get('gender', '')
    dept_filter = request.GET.get('department', '')
    course_filter = request.GET.get('course', '')

    # Students query
    students = Student.objects.all()
    if search:
        students = students.filter(Q(user__first_name__icontains=search) | Q(user__last_name__icontains=search))
    if gender_filter:
        students = students.filter(user__gender=gender_filter)
    if dept_filter:
        students = students.filter(department=dept_filter)
    if course_filter:
        students = students.filter(course=course_filter)

    # Faculty query
    faculty = Faculty.objects.all()
    if search:
        faculty = faculty.filter(Q(user__first_name__icontains=search) | Q(user__last_name__icontains=search))
    if dept_filter:
        faculty = faculty.filter(department=dept_filter)

    # Admin query
    admins = User.objects.filter(is_admin=True)
    if search:
        admins = admins.filter(Q(first_name__icontains=search) | Q(last_name__icontains=search))

    # Pagination
    page = request.GET.get('page', 1)
    per_page = 15  # Increased to reduce pagination when not needed

    if tab == 'students':
        paginator = Paginator(students, per_page)
    elif tab == 'faculty':
        paginator = Paginator(faculty, per_page)
    else:
        paginator = Paginator(admins, per_page)

    try:
        page_obj = paginator.page(page)
    except:
        page_obj = paginator.page(1)

    context = {
        'tab': tab,
        'students': students if tab != 'students' else None,
        'faculty': faculty if tab != 'faculty' else None,
        'admins': admins if tab != 'admins' else None,
        'page_obj': page_obj,
        'search': search,
        'gender_filter': gender_filter,
        'dept_filter': dept_filter,
        'course_filter': course_filter,
    }
    return render(request, 'manage_user.html', context)



@login_required
def add_user(request, role):
    # Assign form class based on role clicked
    if role == "student":
        form_class = StudentForm
    elif role == "faculty":
        form_class = FacultyForm
    elif role == "admin":
        form_class = UserForm
    else:
        return redirect("manage_user")

    if request.method == "POST":
        form = form_class(request.POST)
        # For student form, update section queryset based on selected grade
        if role == "student":
            grade_level = request.POST.get('grade_level', '')
            if grade_level:
                form.fields['section'].queryset = Section.objects.filter(
                    grade=grade_level,
                    status='Active'
                )
            else:
                form.fields['section'].queryset = Section.objects.filter(status='Active')
        if form.is_valid():
            if role == "admin":
                user = form.save(commit=False)
                user.is_admin = True
                user.role = "admin"
                if form.cleaned_data.get('password'):
                    user.set_password(form.cleaned_data['password'])
                user.save()

            elif role == "student":
                # Create User account
                user = User.objects.create_user(
                    username=form.cleaned_data['username'],
                    password=form.cleaned_data['password'],
                    first_name=form.cleaned_data['first_name'],
                    last_name=form.cleaned_data['last_name'],
                )
                user.is_student = True
                user.role = "student"
                user.save()

                # Create Student model entry (for backward compatibility)
                full_name = f"{form.cleaned_data['first_name']} {form.cleaned_data['last_name']}"
                # Extract year level from grade_level (e.g., "Grade 7" -> 7)
                grade_level_str = form.cleaned_data['grade_level']
                year_level = int(grade_level_str.split()[-1]) if grade_level_str.startswith('Grade') else 7

                # Get section name from the selected section object
                section_obj = form.cleaned_data.get('section')
                if section_obj and hasattr(section_obj, 'name'):
                    section_name = section_obj.name
                else:
                    # Fallback if section is a string or None
                    section_name = str(section_obj) if section_obj else 'A'

                Student.objects.create(
                    user=user,
                    year_level=year_level,
                    section=section_name,
                    course='N/A',  # Course removed but field still exists in model
                    status=form.cleaned_data['status']
                )

                # Create StudentRecord entry (main student record)
                # Use username as student_id if it's numeric, otherwise generate one
                try:
                    student_id = int(form.cleaned_data['username'])
                except ValueError:
                    # Generate student_id from last StudentRecord ID + 1
                    last_record = StudentRecord.objects.order_by('-student_id').first()
                    student_id = (last_record.student_id + 1) if last_record else 1000

                grade_and_section = f"{form.cleaned_data['grade_level']} - {section_name}"

                StudentRecord.objects.create(
                    student_id=student_id,
                    fullname=full_name,
                    grade_and_section=grade_and_section,
                    gender=form.cleaned_data['gender'],
                    age=form.cleaned_data['age'],
                    address=form.cleaned_data['address'],
                    parent=form.cleaned_data['parent'],
                    parent_contact=form.cleaned_data['parent_contact'],
                    status=form.cleaned_data['status']
                )

                messages.success(request, f'Student account and record created successfully for {full_name}!')

            elif role == "faculty":
                user = User.objects.create_user(
                    username=form.cleaned_data['username'],
                    password=form.cleaned_data['password'],
                    first_name=form.cleaned_data['first_name'],
                    last_name=form.cleaned_data['last_name'],
                    email=form.cleaned_data.get('email', ''),
                )
                user.is_faculty = True
                user.role = "faculty"
                user.is_active = True  # Ensure user is active
                user.save()

                faculty = Faculty.objects.create(
                    user=user,
                    department=form.cleaned_data['department'],
                    status=form.cleaned_data['status']
                )
                faculty.subjects.set(form.cleaned_data['subjects'])
                messages.success(request, f'Faculty account created successfully for {user.get_full_name()}!')

            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': True, 'message': f'{role.title()} added successfully!'})

            return redirect("manage_user")
    else:
        form = form_class()
        # For student form, set initial section queryset
        if role == "student" and isinstance(form, StudentForm):
            form.fields['section'].queryset = Section.objects.filter(status='Active')

    # Return modal template with form for AJAX requests
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render(request, "modals/add_user_modal.html", {"form": form, "role": role})

    return render(request, "modals/add_user_modal.html", {"form": form, "role": role})




@login_required
def edit_user(request, user_type, pk):
    if user_type == 'student':
        obj = get_object_or_404(Student, pk=pk)
    elif user_type == 'faculty':
        obj = get_object_or_404(Faculty, pk=pk)
    else:
        obj = get_object_or_404(User, pk=pk)

    if request.method == 'POST':
        if user_type == 'student':
            user = obj.user
            user.first_name = request.POST.get('first_name')
            user.last_name = request.POST.get('last_name')
            user.username = request.POST.get('username')
            password = request.POST.get('password')
            if password:
                user.set_password(password)
            user.save()
            obj.year_level = request.POST.get('year_level')
            obj.section = request.POST.get('section')
            obj.status = request.POST.get('status')
            obj.save()
        elif user_type == 'faculty':
            user = obj.user
            user.first_name = request.POST.get('first_name')
            user.last_name = request.POST.get('last_name')
            user.email = request.POST.get('email')
            user.username = request.POST.get('username')
            password = request.POST.get('password')
            if password:
                user.set_password(password)
            user.save()
            obj.department = request.POST.get('department')
            obj.status = request.POST.get('status')
            obj.save()
        else:  # admin
            obj.first_name = request.POST.get('first_name')
            obj.last_name = request.POST.get('last_name')
            obj.email = request.POST.get('email')
            obj.username = request.POST.get('username')
            password = request.POST.get('password')
            if password:
                obj.set_password(password)
            obj.status = request.POST.get('status')
            obj.save()

            AuditTrail.objects.create(user=request.user, action=f"Edited {user_type} {obj}")

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': True, 'message': f'{user_type.title()} updated successfully!'})
        return redirect('manage_user')

    # GET request - return modal template
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render(request, 'modals/edit_user_modal.html', {'user_obj': obj, 'user_type': user_type})

    return render(request, 'edit_user.html', {'user_obj': obj, 'user_type': user_type})


@login_required
def delete_user(request, user_type, pk):
    if user_type == 'student':
        obj = get_object_or_404(Student, pk=pk)
    elif user_type == 'faculty':
        obj = get_object_or_404(Faculty, pk=pk)
    else:
        obj = get_object_or_404(User, pk=pk)
    AuditTrail.objects.create(user=request.user, action=f"Deleted {user_type} {obj}")
    obj.delete()
    return redirect('manage_user')

# inside your account/views.py (replace existing academic_setup)
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth import get_user_model
from .models import SchoolYear, Subject, Section, FacultyAssignment, GradingComponent
from .forms import SchoolYearForm, SubjectForm, SectionForm, FacultyAssignmentForm, GradingComponentForm

User = get_user_model()


@login_required
def academic_setup(request):
    """
    Handles tabbed Academic Setup:
    tabs: school_year, subject, section, faculty, grading
    Modal forms post with hidden 'tab' = name of tab
    """
    tab = request.GET.get('tab', request.POST.get('tab', 'school_year'))
    # Prepare common context entries
    # Years list for School Year modal: from 2020 up to current year + 5
    import datetime
    start = 2020
    current = datetime.date.today().year
    years = list(range(start, current + 6))  # e.g. 2020..2030

    # Get Faculty objects (not User objects) for the modal template
    faculties = Faculty.objects.all()
    subjects_qs = Subject.objects.all()

    # defaults
    form = None
    objects = []

    if request.method == 'POST':
        post_tab = request.POST.get('tab', tab)

        # ---- SCHOOL YEAR ----
        if post_tab == 'school_year':
            form = SchoolYearForm(request.POST)
            if form.is_valid():
                # If marking as Active, deactivate others if needed (optional)
                new_year = form.save(commit=False)
                # prevent duplicate year string
                if SchoolYear.objects.filter(year=new_year.year).exists():
                    messages.error(request, "School year already exists.")
                else:
                    if new_year.status == 'Active':
                        # deactivate other active school years
                        SchoolYear.objects.filter(status='Active').update(status='Inactive')
                    new_year.save()
                    messages.success(request, "School Year added.")
                    return redirect('academic_setup')

        # ---- SUBJECT ----
        elif post_tab == 'subject':
            # We want to accept both the SubjectForm and also accept dynamic "section_x" fields
            form = SubjectForm(request.POST)
            if form.is_valid():
                subject = form.save(commit=False)
                # If SubjectForm has sections_covered as integer or CSV string, ensure consistency.
                # If sections_covered is a number input named 'sections_covered' in form, we leave as-is.
                subject.save()
                # Create FacultyAssignment entries for all faculties if not existing
                faculties_to_assign = User.objects.filter(is_faculty=True)
                to_create = []
                for f in faculties_to_assign:
                    # only create if not exists
                    exists = FacultyAssignment.objects.filter(subject=subject, faculty=f).exists()
                    if not exists:
                        to_create.append(FacultyAssignment(subject=subject, faculty=f, status='Inactive'))
                if to_create:
                    FacultyAssignment.objects.bulk_create(to_create)
                messages.success(request, "Subject saved and faculty assignments created (inactive).")
                return redirect('academic_setup')

        # ---- SECTION ----
        elif post_tab == 'section':
            form = SectionForm(request.POST)
            if form.is_valid():
                form.save()
                messages.success(request, "Section saved.")
                return redirect('academic_setup')

        # ---- FACULTY ASSIGNMENT ----
        elif post_tab == 'faculty':
            # We expect a faculty assignment form which may contain:
            # subject (id) and list of faculty ids (checkboxes named faculty_ids)
            # We'll use FacultyAssignmentForm if it's a form that accepts many-to-many; otherwise handle manually.
            # Try form first:
            form = FacultyAssignmentForm(request.POST)
            if form.is_valid():
                # If FacultyAssignmentForm is simple (subject + faculty + status)
                # But in case you used a multi-select for faculty, handle accordingly:
                faculty_field = form.cleaned_data.get('faculty', None)
                subj = form.cleaned_data.get('subject')
                status = form.cleaned_data.get('status', 'Inactive')
                # Delete existing assignments for subject and recreate from submitted selection
                FacultyAssignment.objects.filter(subject=subj).delete()
                # faculty_field may be a queryset/list if form uses ModelMultipleChoice
                if faculty_field:
                    for f in faculty_field:
                        FacultyAssignment.objects.create(subject=subj, faculty=f, status=status)
                messages.success(request, "Faculty assignments updated.")
                return redirect('academic_setup')
            else:
                # fallback to manual parse (checkboxes named faculty_<id>)
                subject_id = request.POST.get('subject')
                status = request.POST.get('status', 'Inactive')
                if subject_id:
                    try:
                        subj = Subject.objects.get(pk=subject_id)
                        FacultyAssignment.objects.filter(subject=subj).delete()
                        for key in request.POST:
                            if key.startswith('faculty_'):
                                fid = key.split('_', 1)[1]
                                try:
                                    f = User.objects.get(pk=int(fid))
                                    FacultyAssignment.objects.create(subject=subj, faculty=f, status=status)
                                except Exception:
                                    pass
                        messages.success(request, "Faculty assignments updated.")
                        return redirect('academic_setup')
                    except Subject.DoesNotExist:
                        messages.error(request, "Selected subject not found.")
                else:
                    messages.error(request, "No subject selected.")
        # ---- GRADING ----
        elif post_tab == 'grading':
            form = GradingComponentForm(request.POST)
            if form.is_valid():
                new_weight = form.cleaned_data.get('weight') or 0
                status = form.cleaned_data.get('status', 'Active')
                # If adding as active, check total
                existing_active = GradingComponent.objects.filter(status='Active')
                total_existing = sum([g.weight for g in existing_active])
                # If we are saving with status Active, total_existing + new_weight must not exceed 100
                if status == 'Active' and (total_existing + new_weight) > 100:
                    messages.error(request, f"Cannot add: total active grading weight would exceed 100% (current {total_existing}%).")
                else:
                    # Save component
                    component = form.save()
                    # Check total and warn if < 100
                    total_after = total_existing + (new_weight if status == 'Active' else 0)
                    if total_after < 100:
                        messages.info(request, f"Component saved. Total active weight is now {total_after}% (not yet 100%).")
                    elif total_after == 100:
                        messages.success(request, "Component saved. Total active weight is 100%.")
                    else:
                        # This branch shouldn't happen due to earlier check, but safe fallback
                        messages.warning(request, f"Component saved. Total active weight is {total_after}%.")
                    return redirect('academic_setup')
            else:
                messages.error(request, "Invalid grading component data.")
        else:
            messages.error(request, "Unknown action.")
    else:
        # GET - build forms & object lists per tab
        if tab == 'school_year':
            form = SchoolYearForm()
            objects = SchoolYear.objects.all().order_by('-year')
        elif tab == 'subject':
            form = SubjectForm()
            objects = Subject.objects.all()
        elif tab == 'section':
            form = SectionForm()
            objects = Section.objects.all()
        elif tab == 'faculty':
            form = FacultyAssignmentForm()
            objects = FacultyAssignment.objects.all()
        elif tab == 'grading':
            form = GradingComponentForm()
            objects = GradingComponent.objects.all()
        else:
            form = SchoolYearForm()
            objects = SchoolYear.objects.all()

    context = {
        'tab': tab,
        'form': form,
        'objects': objects,
        'years': years,
        'faculties': faculties,
        'subjects_qs': subjects_qs,
    }
    return render(request, 'academic_setup.html', context)

# ==================== ROLE CHECK FUNCTIONS ====================
def admin_required(user):
    return user.is_authenticated and getattr(user, "is_admin", False)

def faculty_required(user):
    return user.is_authenticated and (user.role == 'faculty' or user.role == 'admin')

def student_required(user):
    return user.is_authenticated and user.role == 'student'

# ==================== ADD FUNCTIONS (Modal Support) ====================
@login_required
@user_passes_test(admin_required)
def add_school_year(request):
    if request.method == 'POST':
        year = request.POST.get('year')
        status = request.POST.get('status', 'Active')
        SchoolYear.objects.create(year=year, status=status)
        messages.success(request, 'School Year added successfully!')
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': True, 'message': 'School Year added successfully!'})
        return redirect('/academic_setup/?tab=school_year')

    # Generate years list
    current_year = datetime.now().year
    years = list(range(current_year, current_year+5))
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'years': years})
    return render(request, 'modals/add_school_year_modal.html', {
        'years': years, 'modal_id': 'addSchoolYearModal',
        'modal_title': 'Add School Year', 'form_action': '/academic/school-year/add/'
    })

@login_required
@user_passes_test(admin_required)
def add_subject(request):
    if request.method == 'POST':
        code = request.POST.get('code')
        name = request.POST.get('name')
        status = request.POST.get('status', 'Active')

        Subject.objects.create(
            code=code, name=name,
            department='General',  # Default department
            status=status
        )
        messages.success(request, 'Subject added successfully!')
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': True, 'message': 'Subject added successfully!'})
        return redirect('/academic_setup/?tab=subject')

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'form': 'modal'})
    return render(request, 'modals/add_subject_modal.html', {
        'modal_id': 'addSubjectModal',
        'modal_title': 'Add Subject',
        'form_action': '/academic/subject/add/'
    })

@login_required
@user_passes_test(admin_required)
def add_section(request):
    if request.method == 'POST':
        grade = request.POST.get('grade')
        name = request.POST.get('name')
        adviser = request.POST.get('adviser')
        number_of_students = request.POST.get('number_of_students', 0)
        status = request.POST.get('status', 'Active')

        Section.objects.create(
            grade=grade, name=name, adviser=adviser,
            number_of_students=number_of_students, status=status
        )
        messages.success(request, 'Section added successfully!')
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': True, 'message': 'Section added successfully!'})
        return redirect('/academic_setup/?tab=section')

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'form': 'modal'})
    return render(request, 'modals/add_section_modal.html', {
        'modal_id': 'addSectionModal',
        'modal_title': 'Add Section',
        'form_action': '/academic/section/add/'
    })

@login_required
@user_passes_test(admin_required)
def add_faculty(request):
    subjects_qs = Subject.objects.all()
    faculties = Faculty.objects.all()

    if request.method == 'POST':
        subject_id = request.POST.get('subject')
        status = request.POST.get('status', 'Active')
        subject = get_object_or_404(Subject, id=subject_id)

        faculty_ids = [
            int(key.split('_')[1])
            for key in request.POST
            if key.startswith('faculty_') and key.split('_')[1].isdigit()
        ]
        for faculty_id in faculty_ids:
            faculty = get_object_or_404(Faculty, id=faculty_id)
        assignment, created = FacultyAssignment.objects.update_or_create(
            faculty=faculty.user,
            defaults={'status': status}
        )
        assignment.subjects.add(subject)

        messages.success(request, "Faculty assigned successfully!")
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': True, 'message': 'Faculty assigned successfully!'})
        return redirect('/academic_setup/?tab=faculty')

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'subjects': [{'id': s.id, 'name': s.name} for s in subjects_qs],
            'faculties': [{'id': f.id, 'name': f.user.get_full_name()} for f in faculties]
        })
    return render(request, 'modals/add_faculty_modal.html', {
        'subjects_qs': subjects_qs, 'faculties': faculties,
        'modal_id': 'addFacultyModal', 'modal_title': 'Assign Faculty',
        'form_action': '/academic/faculty/add/'
    })

@login_required
@user_passes_test(admin_required)
def add_grading(request):
    if request.method == 'POST':
        component = request.POST.get('component')
        weight = request.POST.get('weight', 0)
        status = request.POST.get('status', 'Active')

        GradingComponent.objects.create(component=component, weight=weight, status=status)
        messages.success(request, 'Grading Component added successfully!')
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': True, 'message': 'Grading Component added successfully!'})
        return redirect('/academic_setup/?tab=grading')

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'form': 'modal'})
    return render(request, 'modals/add_grading_modal.html', {
        'modal_id': 'addGradingModal',
        'modal_title': 'Add Grading Component',
        'form_action': '/academic/grading/add/'
    })

# REMOVED DUPLICATE role check functions - Using versions above (around line 887)

# ==================== ACADEMIC SETUP ====================
@login_required
@user_passes_test(admin_required)
def academic_setup(request):
    """
    Handles tabbed Academic Setup:
    tabs: school_year, subject, section, faculty, grading
    Modal forms post with hidden 'tab' = name of tab
    """
    tab = request.GET.get('tab', request.POST.get('tab', 'school_year'))
    # Prepare common context entries
    # Years list for School Year modal: from 2020 up to current year + 5
    import datetime
    start = 2020
    current = datetime.date.today().year
    years = list(range(start, current + 6))  # e.g. 2020..2030

    # Get Faculty objects (not User objects) for the modal template
    faculties = Faculty.objects.all()
    subjects_qs = Subject.objects.all()

    # defaults
    form = None
    objects = []

    if request.method == 'POST':
        post_tab = request.POST.get('tab', tab)

        # ---- SCHOOL YEAR ----
        if post_tab == 'school_year':
            form = SchoolYearForm(request.POST)
            if form.is_valid():
                # If marking as Active, deactivate others if needed (optional)
                new_year = form.save(commit=False)
                # prevent duplicate year string
                if SchoolYear.objects.filter(year=new_year.year).exists():
                    messages.error(request, "School year already exists.")
                else:
                    if new_year.status == 'Active':
                        # deactivate other active school years
                        SchoolYear.objects.filter(status='Active').update(status='Inactive')
                    new_year.save()
                    messages.success(request, "School Year added.")
                    return redirect('academic_setup')

        # ---- SUBJECT ----
        elif post_tab == 'subject':
            # We want to accept both the SubjectForm and also accept dynamic "section_x" fields
            form = SubjectForm(request.POST)
            if form.is_valid():
                subject = form.save(commit=False)
                # If SubjectForm has sections_covered as integer or CSV string, ensure consistency.
                # If sections_covered is a number input named 'sections_covered' in form, we leave as-is.
                subject.save()
                # Create FacultyAssignment entries for all faculties if not existing
                faculties_to_assign = User.objects.filter(is_faculty=True)
                to_create = []
                for f in faculties_to_assign:
                    # only create if not exists
                    exists = FacultyAssignment.objects.filter(subject=subject, faculty=f).exists()
                    if not exists:
                        to_create.append(FacultyAssignment(subject=subject, faculty=f, status='Inactive'))
                if to_create:
                    FacultyAssignment.objects.bulk_create(to_create)
                messages.success(request, "Subject saved and faculty assignments created (inactive).")
                return redirect('academic_setup')

        # ---- SECTION ----
        elif post_tab == 'section':
            form = SectionForm(request.POST)
            if form.is_valid():
                form.save()
                messages.success(request, "Section saved.")
                return redirect('academic_setup')

        # ---- FACULTY ASSIGNMENT ----
        elif post_tab == 'faculty':
            # We expect a faculty assignment form which may contain:
            # subject (id) and list of faculty ids (checkboxes named faculty_ids)
            # We'll use FacultyAssignmentForm if it's a form that accepts many-to-many; otherwise handle manually.
            # Try form first:
            form = FacultyAssignmentForm(request.POST)
            if form.is_valid():
                # If FacultyAssignmentForm is simple (subject + faculty + status)
                # But in case you used a multi-select for faculty, handle accordingly:
                faculty_field = form.cleaned_data.get('faculty', None)
                subj = form.cleaned_data.get('subject')
                status = form.cleaned_data.get('status', 'Inactive')
                # Delete existing assignments for subject and recreate from submitted selection
                FacultyAssignment.objects.filter(subject=subj).delete()
                # faculty_field may be a queryset/list if form uses ModelMultipleChoice
                if faculty_field:
                    for f in faculty_field:
                        FacultyAssignment.objects.create(subject=subj, faculty=f, status=status)
                messages.success(request, "Faculty assignments updated.")
                return redirect('academic_setup')
            else:
                # fallback to manual parse (checkboxes named faculty_<id>)
                subject_id = request.POST.get('subject')
                status = request.POST.get('status', 'Inactive')
                if subject_id:
                    try:
                        subj = Subject.objects.get(pk=subject_id)
                        FacultyAssignment.objects.filter(subject=subj).delete()
                        for key in request.POST:
                            if key.startswith('faculty_'):
                                fid = key.split('_', 1)[1]
                                try:
                                    f = User.objects.get(pk=int(fid))
                                    FacultyAssignment.objects.create(subject=subj, faculty=f, status=status)
                                except Exception:
                                    pass
                        messages.success(request, "Faculty assignments updated.")
                        return redirect('academic_setup')
                    except Subject.DoesNotExist:
                        messages.error(request, "Selected subject not found.")
                else:
                    messages.error(request, "No subject selected.")
        # ---- GRADING ----
        elif post_tab == 'grading':
            form = GradingComponentForm(request.POST)
            if form.is_valid():
                new_weight = form.cleaned_data.get('weight') or 0
                status = form.cleaned_data.get('status', 'Active')
                # If adding as active, check total
                existing_active = GradingComponent.objects.filter(status='Active')
                total_existing = sum([g.weight for g in existing_active])
                # If we are saving with status Active, total_existing + new_weight must not exceed 100
                if status == 'Active' and (total_existing + new_weight) > 100:
                    messages.error(request, f"Cannot add: total active grading weight would exceed 100% (current {total_existing}%).")
                else:
                    # Save component
                    component = form.save()
                    # Check total and warn if < 100
                    total_after = total_existing + (new_weight if status == 'Active' else 0)
                    if total_after < 100:
                        messages.info(request, f"Component saved. Total active weight is now {total_after}% (not yet 100%).")
                    elif total_after == 100:
                        messages.success(request, "Component saved. Total active weight is 100%.")
                    else:
                        # This branch shouldn't happen due to earlier check, but safe fallback
                        messages.warning(request, f"Component saved. Total active weight is {total_after}%.")
                    return redirect('academic_setup')
            else:
                messages.error(request, "Invalid grading component data.")
        else:
            messages.error(request, "Unknown action.")
    else:
        # GET - build forms & object lists per tab
        if tab == 'school_year':
            form = SchoolYearForm()
            objects = SchoolYear.objects.all().order_by('-year')
        elif tab == 'subject':
            form = SubjectForm()
            objects = Subject.objects.all()
        elif tab == 'section':
            form = SectionForm()
            objects = Section.objects.all()
        elif tab == 'faculty':
            form = FacultyAssignmentForm()
            objects = FacultyAssignment.objects.all()
        elif tab == 'grading':
            form = GradingComponentForm()
            objects = GradingComponent.objects.all()
        else:
            form = SchoolYearForm()
            objects = SchoolYear.objects.all()

    # Pagination
    page = request.GET.get('page', 1)
    per_page = 15  # Increased to reduce pagination when not needed
    paginator = Paginator(objects, per_page)
    try:
        page_obj = paginator.page(page)
    except:
        page_obj = paginator.page(1)

    context = {
        'tab': tab,
        'form': form,
        'objects': objects,
        'page_obj': page_obj,
        'years': years,
        'faculties': faculties,
        'subjects_qs': subjects_qs,
    }
    return render(request, 'academic_setup.html', context)

# REMOVED DUPLICATE add_school_year - Using modal version above (around line 897)

# ==================== EDIT FUNCTIONS ====================
# All imports already done at top of file

# ---------- School Year ----------
def edit_school_year(request, pk):
    obj = get_object_or_404(SchoolYear, pk=pk)
    if request.method == 'POST':
        year = request.POST.get('year')
        status = request.POST.get('status', 'Active')
        obj.year = year
        obj.status = status
        obj.save()
        messages.success(request, "School Year updated!")
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': True, 'message': 'School Year updated!'})
        return redirect('/academic_setup/?tab=school_year')
    import datetime
    start = 2020
    current = datetime.date.today().year
    years = list(range(start, current + 6))
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render(request, 'modals/edit_school_year_modal.html', {'obj': obj, 'years': years})
    return render(request, 'edit_school_year.html', {'obj': obj, 'years': years})


# ---------- Subject ----------
def edit_subject(request, pk):
    obj = get_object_or_404(Subject, pk=pk)
    if request.method == 'POST':
        obj.code = request.POST.get('code')
        obj.name = request.POST.get('name')
        obj.grade_level = request.POST.get('grade_level') or None
        obj.department = request.POST.get('department', 'General')
        obj.status = request.POST.get('status', 'Active')
        obj.save()
        messages.success(request, "Subject updated!")
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': True, 'message': 'Subject updated!'})
        return redirect('/academic_setup/?tab=subject')
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render(request, 'modals/edit_subject_modal.html', {'obj': obj})
    form = SubjectForm(instance=obj)
    return render(request, 'edit_subject.html', {'form': form, 'obj': obj})


# ---------- Section ----------
def edit_section(request, pk):
    obj = get_object_or_404(Section, pk=pk)
    if request.method == 'POST':
        obj.grade = request.POST.get('grade')
        obj.name = request.POST.get('name')
        obj.adviser = request.POST.get('adviser', '')
        obj.number_of_students = int(request.POST.get('number_of_students', 0))
        obj.status = request.POST.get('status', 'Active')
        obj.save()
        messages.success(request, "Section updated!")
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': True, 'message': 'Section updated!'})
        return redirect('/academic_setup/?tab=section')
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render(request, 'modals/edit_section_modal.html', {'obj': obj})
    form = SectionForm(instance=obj)
    return render(request, 'edit_section.html', {'form': form, 'obj': obj})


# ---------- Faculty Assignment ----------
def edit_faculty(request, pk):
    obj = get_object_or_404(FacultyAssignment, pk=pk)
    if request.method == 'POST':
        faculty_id = request.POST.get('faculty')
        subject_id = request.POST.get('subject')
        status = request.POST.get('status', 'Active')
        if faculty_id:
            obj.faculty = get_object_or_404(User, id=faculty_id)
        if subject_id:
            subject = get_object_or_404(Subject, id=subject_id)
            obj.subjects.clear()
            obj.subjects.add(subject)
        obj.status = status
        obj.save()
        messages.success(request, "Faculty assignment updated!")
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': True, 'message': 'Faculty assignment updated!'})
        return redirect('/academic_setup/?tab=faculty')
    faculties = Faculty.objects.all()
    subjects_qs = Subject.objects.all()
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render(request, 'modals/edit_faculty_assignment_modal.html', {'obj': obj, 'faculties': faculties, 'subjects_qs': subjects_qs})
    form = FacultyAssignmentForm(instance=obj)
    return render(request, 'edit_faculty.html', {'form': form, 'obj': obj})


# ---------- Grading Component ----------
def edit_grading(request, pk):
    obj = get_object_or_404(GradingComponent, pk=pk)
    if request.method == 'POST':
        obj.component = request.POST.get('component')
        obj.weight = float(request.POST.get('weight', 0))
        obj.status = request.POST.get('status', 'Active')
        obj.save()
        messages.success(request, "Grading Component updated!")
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': True, 'message': 'Grading Component updated!'})
        return redirect('/academic_setup/?tab=grading')
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render(request, 'modals/edit_grading_modal.html', {'obj': obj})
    form = GradingComponentForm(instance=obj)
    return render(request, 'edit_grading.html', {'form': form, 'obj': obj})

# ==================== DELETE FUNCTIONS ====================
# All imports already done at top of file

# --- DELETE VIEWS ---

def delete_school_year(request, pk):
    obj = get_object_or_404(SchoolYear, pk=pk)
    obj.delete()
    messages.success(request, "School Year deleted successfully!")
    return redirect('academic_setup')

def delete_subject(request, pk):
    obj = get_object_or_404(Subject, pk=pk)
    obj.delete()
    messages.success(request, "Subject deleted successfully!")
    return redirect('academic_setup')

def delete_section(request, pk):
    obj = get_object_or_404(Section, pk=pk)
    obj.delete()
    messages.success(request, "Section deleted successfully!")
    return redirect('academic_setup')

def delete_faculty(request, pk):
    obj = get_object_or_404(FacultyAssignment, pk=pk)
    obj.delete()
    messages.success(request, "Faculty deleted successfully!")
    return redirect('academic_setup')

def delete_grading(request, pk):
    obj = get_object_or_404(GradingComponent, pk=pk)
    obj.delete()
    messages.success(request, "Grading component deleted successfully!")
    return redirect('academic_setup')

from django.shortcuts import render, get_object_or_404, redirect
from .models import Student, Faculty, User
from .forms import StudentForm, FacultyForm, UserForm

def edit_student(request, student_id):
    student = get_object_or_404(Student, pk=student_id)
    if request.method == "POST":
        # Update related user fields manually
        user = student.user
        user.first_name = request.POST.get('first_name')
        user.last_name = request.POST.get('last_name')
        user.username = request.POST.get('username')
        password = request.POST.get('password')
        if password:
            user.set_password(password)
        user.save()

        # Update Student-specific fields
        student.year_level = request.POST.get('year_level')
        student.section = request.POST.get('section')
        student.status = request.POST.get('status')
        student.save()

        return redirect('manage_user')

    return render(request, 'edit_student.html', {'student': student})




def edit_faculties(request, faculty_id):
    faculty = get_object_or_404(Faculty, id=faculty_id)
    user = faculty.user  # related user

    if request.method == 'POST':
        user.first_name = request.POST['first_name']
        user.last_name = request.POST['last_name']
        user.email = request.POST['email']
        user.username = request.POST['username']

        if request.POST['password']:
            user.set_password(request.POST['password'])

        user.save()

        faculty.department = request.POST['department']
        faculty.status = request.POST['status']
        faculty.save()

        messages.success(request, "Faculty updated successfully!")
        return redirect('manage_user')

    return render(request, 'edit_faculties.html', {'faculty': faculty, 'all_subjects': Subject.objects.all()
})



def edit_admin(request, admin_id):
    admin = get_object_or_404(User, pk=admin_id)

    if request.method == "POST":
        admin.first_name = request.POST.get('first_name')
        admin.last_name = request.POST.get('last_name')
        admin.username = request.POST.get('username')
        admin.email = request.POST.get('email')
        password = request.POST.get('password')
        if password:
            admin.set_password(password)
        admin.status = request.POST.get('status')
        admin.save()

        return redirect('manage_user')

    return render(request, 'edit_admin.html', {'admin': admin})


from django.shortcuts import get_object_or_404, redirect
from .models import Student, Faculty, User

def delete_student(request, student_id):
    student = get_object_or_404(Student, pk=student_id)
    student.delete()
    return redirect('manage_user')


def delete_faculty(request, faculty_id):
    faculty = get_object_or_404(Faculty, pk=faculty_id)
    faculty.delete()
    return redirect('manage_user')


def delete_admin(request, admin_id):
    admin = get_object_or_404(User, pk=admin_id)
    admin.delete()
    return redirect('manage_user')

from.models import StudentRecord
from django.http import HttpResponseRedirect
from django.urls import reverse


@login_required
@user_passes_test(faculty_required)
def record(request):
    """Student record view - accessible by faculty and admin"""
    accounts = StudentRecord.objects.all()

    # Pagination
    page = request.GET.get('page', 1)
    per_page = 15  # Increased to reduce pagination when not needed
    paginator = Paginator(accounts, per_page)
    try:
        page_obj = paginator.page(page)
    except:
        page_obj = paginator.page(1)

    return render(request, 'student_record.html', {'page_obj': page_obj})

def view_student(request, id):
    student = StudentRecord.objects.get(pk=id)

    return HttpResponseRedirect(reverse('index'))

from .forms import RecordForm

@login_required
@user_passes_test(faculty_required)
def add(request):
    """Add student record - optionally create user account"""
    if request.method == 'POST':
        form = RecordForm(request.POST)
        # Update section queryset based on selected grade
        grade_level = request.POST.get('grade_level', '')
        if grade_level:
            form.fields['section'].queryset = Section.objects.filter(
                grade=grade_level,
                status='Active'
            )
        else:
            form.fields['section'].queryset = Section.objects.filter(status='Active')

        if form.is_valid():
            new_student_id = form.cleaned_data['student_id']
            new_fullname = form.cleaned_data['fullname']
            grade_level = form.cleaned_data['grade_level']
            section_obj = form.cleaned_data['section']
            section_name = section_obj.name if section_obj else 'A'
            grade_and_section = f"{grade_level} - {section_name}"
            new_gender = form.cleaned_data['gender']
            new_age = form.cleaned_data['age']
            new_address = form.cleaned_data['address']
            new_parent = form.cleaned_data['parent']
            new_parent_contact = form.cleaned_data['parent_contact']
            new_status = form.cleaned_data['status']

            # Create StudentRecord
            new_student = StudentRecord(
                student_id = new_student_id,
                fullname = new_fullname,
                grade_and_section = grade_and_section,
                gender = new_gender,
                age = new_age,
                address = new_address,
                parent = new_parent,
                parent_contact = new_parent_contact,
                status = new_status,
            )
            new_student.save()

            # Optionally create user account if username and password provided
            create_account = request.POST.get('create_account', False)
            if create_account:
                username = request.POST.get('username', str(new_student_id))
                password = request.POST.get('password', '')

                if username and password:
                    # Check if username already exists
                    if not User.objects.filter(username=username).exists():
                        # Create User account
                        user = User.objects.create_user(
                            username=username,
                            password=password,
                            first_name=new_fullname.split()[0] if new_fullname.split() else '',
                            last_name=' '.join(new_fullname.split()[1:]) if len(new_fullname.split()) > 1 else '',
                        )
                        user.is_student = True
                        user.role = "student"
                        user.save()

                        # Create Student model entry for backward compatibility
                        year_level = int(grade_level.split()[-1]) if grade_level.startswith('Grade') else 7
                        section_name = section_obj.name if section_obj else 'A'

                        Student.objects.create(
                            user=user,
                            year_level=year_level,
                            section=section_name,
                            course='N/A',
                            status=new_status
                        )

                        messages.success(request, f'Student record and account created successfully for {new_fullname}!')
                    else:
                        messages.warning(request, f'Username {username} already exists. Student record created but account not created.')
                else:
                    messages.warning(request, 'Student record created but account not created (missing username or password).')
            else:
                messages.success(request, f'Student record created successfully for {new_fullname}!')

            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': True, 'message': f'Student record created successfully for {new_fullname}!'})
            # Non-AJAX POST: redirect back to student record list so table refreshes

            return redirect('student_record')

    else:
        form = RecordForm()
        # Set initial section queryset
        form.fields['section'].queryset = Section.objects.filter(status='Active')

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return render(request, 'modals/add_student_record_modal.html', {
                'form': form
            })

    return render(request, 'add.html', {
        'form': form
    })

def edit(request, id):
    student = StudentRecord.objects.get(pk=id)

    if request.method == "POST":
        form = RecordForm(request.POST)
        # Update section queryset based on selected grade
        grade_level = request.POST.get('grade_level', '')
        if grade_level:
            form.fields['section'].queryset = Section.objects.filter(
                grade=grade_level,
                status='Active'
            )
        else:
            form.fields['section'].queryset = Section.objects.filter(status='Active')

        if form.is_valid():
            student.student_id = form.cleaned_data['student_id']
            student.fullname = form.cleaned_data['fullname']
            grade_level = form.cleaned_data['grade_level']
            section_obj = form.cleaned_data['section']
            section_name = section_obj.name if section_obj else 'A'
            # Update grade_and_section field
            student.grade_and_section = f"{grade_level} - {section_name}"
            student.gender = form.cleaned_data['gender']
            student.age = form.cleaned_data['age']
            student.address = form.cleaned_data['address']
            student.parent = form.cleaned_data['parent']
            student.parent_contact = form.cleaned_data['parent_contact']
            student.status = form.cleaned_data['status']
            student.save()

            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': True, 'message': 'Student record updated successfully!'})
            return redirect('student_record')
    else:
        # Parse grade_and_section to extract grade_level and section_name
        grade_level = None
        section_name = None
        section_obj = None

        if student.grade_and_section:
            # Format is "Grade 7 - A" or just "Grade 7"
            parts = student.grade_and_section.split(' - ')
            if len(parts) >= 1:
                grade_level = parts[0].strip()
            if len(parts) >= 2:
                section_name = parts[1].strip()
                # Try to find the Section object
                try:
                    section_obj = Section.objects.filter(grade=grade_level, name=section_name, status='Active').first()
                except:
                    pass

        # Create form and set section queryset based on grade_level first
        form = RecordForm()
        if grade_level:
            form.fields['section'].queryset = Section.objects.filter(
                grade=grade_level,
                status='Active'
            )
        else:
            form.fields['section'].queryset = Section.objects.filter(status='Active')

        # Pre-populate form with existing data
        form = RecordForm(initial={
            'student_id': student.student_id,
            'fullname': student.fullname,
            'grade_level': grade_level or 'Grade 7',
            'section': section_obj,
            'gender': student.gender,
            'age': student.age,
            'address': student.address,
            'parent': student.parent,
            'parent_contact': student.parent_contact,
            'status': student.status,
        })
        # Set section queryset again after initial (to ensure it's correct)
        if grade_level:
            form.fields['section'].queryset = Section.objects.filter(
                grade=grade_level,
                status='Active'
            )
        else:
            form.fields['section'].queryset = Section.objects.filter(status='Active')

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render(request, 'modals/edit_student_record_modal.html', {
            'form': form,
            'student': student
        })

    return render(request, 'edit.html',{
        'form': form
    })

def delete(request,id):
    if request.method == "POST":
        student = StudentRecord.objects.get(pk=id)
        student.delete()
    return HttpResponseRedirect(reverse('student_record'))  # or whatever URL name shows the table


def assign(request):
    # Get distinct grades
    grades = Section.objects.values_list('grade', flat=True).distinct()
    subjects = Subject.objects.all()  # get all subjects
    status_choices = ['Active', 'Inactive']

    if request.method == 'POST':
        try:
            subject_id = request.POST.get('subject')
            grade_level = request.POST.get('grade_level')
            status = request.POST.get('status')

            # Get the Subject instance
            subject = Subject.objects.get(id=subject_id)

            # Create AssignedSubject
            AssignedSubject.objects.create(
                subject=subject,
                grade_level=grade_level,
                status=status
            )

            messages.success(request, 'Subject assigned successfully')
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': True, 'message': 'Subject assigned successfully!'})
        except Exception as e:
            messages.error(request, f'Something went wrong: {str(e)}')
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'message': f'Something went wrong: {str(e)}'})
        return redirect('assign_subject')

    context = {
        'grades': grades,
        'subjects': subjects,
        'status_choices': status_choices
    }
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render(request, 'modals/assign_subject_modal.html', context)
    return render(request, 'assign.html', context)



from .models import AssignedSubject

def assign_subject(request):
    assigned_subjects = AssignedSubject.objects.all()

    # Pagination
    page = request.GET.get('page', 1)
    per_page = 15  # Increased to reduce pagination when not needed
    paginator = Paginator(assigned_subjects, per_page)
    try:
        page_obj = paginator.page(page)
    except:
        page_obj = paginator.page(1)

    context = {
        'page_obj': page_obj
    }
    return render(request, 'assign_subject.html', context)

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from .models import AssignedSubject, Subject
from .models import Section

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from .models import AssignedSubject, Subject
from .models import Section

def edit_assigned_subject(request, pk):
    assigned = get_object_or_404(AssignedSubject, pk=pk)
    grades = Section.objects.values_list('grade', flat=True).distinct()
    subjects = Subject.objects.all()
    status_choices = ['Active', 'Inactive']

    if request.method == 'POST':
        try:
            subject_id = request.POST.get('subject')
            grade_level = request.POST.get('grade_level')
            status = request.POST.get('status')

            subject = Subject.objects.get(id=subject_id)

            assigned.subject = subject
            assigned.grade_level = grade_level
            assigned.status = status
            assigned.save()

            messages.success(request, 'Assigned subject updated successfully')
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': True, 'message': 'Assigned subject updated successfully!'})
            return redirect('assign_subject')
        except Exception as e:
            messages.error(request, f'Something went wrong: {str(e)}')
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'message': f'Something went wrong: {str(e)}'})

    context = {
        'assigned': assigned,
        'grades': grades,
        'subjects': subjects,
        'status_choices': status_choices
    }
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render(request, 'modals/edit_assign_subject_modal.html', {'item': assigned})
    return render(request, 'edit_assign.html', context)


def delete_assigned_subject(request, pk):
    assigned = get_object_or_404(AssignedSubject, pk=pk)
    try:
        assigned.delete()
        messages.success(request, 'Assigned subject deleted successfully')
    except Exception as e:
        messages.error(request, f'Something went wrong: {str(e)}')
    return redirect('assign_subject')

from .models import Subject, Faculty
from .models import Faculty, Score


def score_view(request):
    scores = Score.objects.select_related(
        'student', 'subject', 'section'
    ).all()

    return render(request, 'score.html', {'scores': scores})

from django.shortcuts import render


def quiz(request):
    # Get all subjects that have quiz scores
    subjects_with_quizzes = Subject.objects.filter(
        quiz_scores__isnull=False
    ).distinct().order_by('name')

    # Get quiz data grouped by subject and student
    quiz_data = []
    for subject in subjects_with_quizzes:
        # Get assigned grade level for this subject
        assigned_subject = AssignedSubject.objects.filter(
            subject=subject,
            status='Active'
        ).first()

        # Filter students by grade level if subject is assigned
        if assigned_subject:
            students = StudentRecord.objects.filter(
                status='active',
                grade_and_section=assigned_subject.grade_level
            ).order_by('fullname')
        else:
            # If no assignment, show all active students (fallback)
            students = StudentRecord.objects.filter(status='active').order_by('fullname')

        quiz_numbers = QuizScore.objects.filter(subject=subject).values_list('quiz_number', flat=True).distinct().order_by('quiz_number')
        quiz_numbers_list = list(quiz_numbers)

        student_rows = []
        for student in students:
            student_scores = []
            total_score = 0
            count = 0

            for quiz_num in quiz_numbers_list:
                try:
                    quiz_score = QuizScore.objects.get(
                        student=student,
                        subject=subject,
                        quiz_number=quiz_num
                    )
                    score_val = float(quiz_score.score)
                    student_scores.append(score_val)
                    total_score += score_val
                    count += 1
                except QuizScore.DoesNotExist:
                    student_scores.append(None)

            # Calculate average
            average = (total_score / count) if count > 0 else None

            student_rows.append({
                'student': student,
                'scores': student_scores,
                'average': average
            })

        quiz_data.append({
            'subject': subject,
            'quiz_numbers': quiz_numbers_list,
            'student_rows': student_rows
        })

    # Pagination - paginate by subjects (each subject is a section)
    page = request.GET.get('page', 1)
    per_page = 5  # Show 5 subjects per page to avoid screen overflow
    paginator = Paginator(quiz_data, per_page)
    try:
        page_obj = paginator.page(page)
    except:
        page_obj = paginator.page(1)

    return render(request, 'quiz.html', {
        'quiz_data': page_obj,
        'page_obj': page_obj,
        'tab': 'quiz'
    })

def exam(request):
    # Get all subjects that have exam scores
    subjects_with_exams = Subject.objects.filter(
        exam_scores__isnull=False
    ).distinct().order_by('name')

    # Get exam data grouped by subject and student
    exam_data = []
    for subject in subjects_with_exams:
        # Get assigned grade level for this subject
        assigned_subject = AssignedSubject.objects.filter(
            subject=subject,
            status='Active'
        ).first()

        # Filter students by grade level if subject is assigned
        if assigned_subject:
            students = StudentRecord.objects.filter(
                status='active',
                grade_and_section=assigned_subject.grade_level
            ).order_by('fullname')
        else:
            # If no assignment, show all active students (fallback)
            students = StudentRecord.objects.filter(status='active').order_by('fullname')

        exam_numbers = ExamScore.objects.filter(subject=subject).values_list('exam_number', flat=True).distinct().order_by('exam_number')
        exam_numbers_list = list(exam_numbers)

        student_rows = []
        for student in students:
            student_scores = []
            total_score = 0
            count = 0

            for exam_num in exam_numbers_list:
                try:
                    exam_score = ExamScore.objects.get(
                        student=student,
                        subject=subject,
                        exam_number=exam_num
                    )
                    score_val = float(exam_score.score)
                    student_scores.append(score_val)
                    total_score += score_val
                    count += 1
                except ExamScore.DoesNotExist:
                    student_scores.append(None)

            # Calculate average
            average = (total_score / count) if count > 0 else None

            student_rows.append({
                'student': student,
                'scores': student_scores,
                'average': average
            })

        exam_data.append({
            'subject': subject,
            'exam_numbers': exam_numbers_list,
            'student_rows': student_rows
        })

    # Pagination - paginate by subjects (each subject is a section)
    page = request.GET.get('page', 1)
    per_page = 5  # Show 5 subjects per page to avoid screen overflow
    paginator = Paginator(exam_data, per_page)
    try:
        page_obj = paginator.page(page)
    except:
        page_obj = paginator.page(1)

    return render(request, 'exam.html', {
        'exam_data': page_obj if page_obj else [],
        'page_obj': page_obj,
        'tab': 'exam'
    })

def project(request):
    # Get all subjects that have project scores
    subjects_with_projects = Subject.objects.filter(
        project_scores__isnull=False
    ).distinct().order_by('name')

    # Get project data grouped by subject and student
    project_data = []
    for subject in subjects_with_projects:
        # Get assigned grade level for this subject
        assigned_subject = AssignedSubject.objects.filter(
            subject=subject,
            status='Active'
        ).first()

        # Filter students by grade level if subject is assigned
        if assigned_subject:
            students = StudentRecord.objects.filter(
                status='active',
                grade_and_section=assigned_subject.grade_level
            ).order_by('fullname')
        else:
            # If no assignment, show all active students (fallback)
            students = StudentRecord.objects.filter(status='active').order_by('fullname')

        project_numbers = ProjectScore.objects.filter(subject=subject).values_list('project_number', flat=True).distinct().order_by('project_number')
        project_numbers_list = list(project_numbers)

        student_rows = []
        for student in students:
            student_scores = []
            total_score = 0
            count = 0

            for project_num in project_numbers_list:
                try:
                    project_score = ProjectScore.objects.get(
                        student=student,
                        subject=subject,
                        project_number=project_num
                    )
                    score_val = float(project_score.score)
                    student_scores.append(score_val)
                    total_score += score_val
                    count += 1
                except ProjectScore.DoesNotExist:
                    student_scores.append(None)

            # Calculate average
            average = (total_score / count) if count > 0 else None

            student_rows.append({
                'student': student,
                'scores': student_scores,
                'average': average
            })

        project_data.append({
            'subject': subject,
            'project_numbers': project_numbers_list,
            'student_rows': student_rows
        })

    # Pagination - paginate by subjects (each subject is a section)
    page = request.GET.get('page', 1)
    per_page = 5  # Show 5 subjects per page to avoid screen overflow
    paginator = Paginator(project_data, per_page)
    try:
        page_obj = paginator.page(page)
    except:
        page_obj = paginator.page(1)

    return render(request, 'project.html', {
        'project_data': page_obj if page_obj else [],
        'page_obj': page_obj,
        'tab': 'project'
    })

def attendance(request):
    # Get all subjects that have attendance sessions
    subjects_with_sessions = Subject.objects.filter(
        attendance_sessions__isnull=False
    ).distinct().order_by('name')

    # Get attendance data grouped by subject
    attendance_data = []
    for subject in subjects_with_sessions:
        # Get assigned grade level for this subject
        assigned_subject = AssignedSubject.objects.filter(
            subject=subject,
            status='Active'
        ).first()

        # Filter students by grade level if subject is assigned
        if assigned_subject:
            students = StudentRecord.objects.filter(
                status='active',
                grade_and_section=assigned_subject.grade_level
            ).order_by('fullname')
        else:
            # If no assignment, show all active students (fallback)
            students = StudentRecord.objects.filter(status='active').order_by('fullname')

        # Get all weekly sessions for this subject
        sessions = WeeklyAttendanceSession.objects.filter(subject=subject).order_by('week_number')
        weeks_list = list(sessions)

        # Calculate overall attendance percentage for each student
        student_rows = []
        for student in students:
            week_attendance = []
            overall_present = 0
            overall_total = 0

            for session in weeks_list:
                try:
                    record = WeeklyAttendanceRecord.objects.get(session=session, student=student)
                    # Count present sessions from individual session fields
                    sessions_list = [record.session_1, record.session_2, record.session_3, record.session_4]
                    present_count = sum(1 for s in sessions_list if s == 'P')
                    total_count = len([s for s in sessions_list if s and s != '-'])

                    # Calculate percentage for this week
                    week_percentage = round((present_count / total_count * 100), 2) if total_count > 0 else 0

                    # Create summary string
                    summary = ','.join([s if s else '-' for s in sessions_list])

                    overall_present += present_count
                    overall_total += total_count

                    week_attendance.append({
                        'summary': summary,
                        'percentage': week_percentage,
                        'session_id': session.id
                    })
                except WeeklyAttendanceRecord.DoesNotExist:
                    week_attendance.append({
                        'summary': '-',
                        'percentage': 0,
                        'session_id': session.id
                    })

            # Calculate overall percentage
            overall_percentage = round((overall_present / overall_total * 100), 2) if overall_total > 0 else 0

            student_rows.append({
                'student': student,
                'week_attendance': week_attendance,
                'overall_percentage': overall_percentage
            })

        attendance_data.append({
            'subject': subject,
            'weeks': weeks_list,
            'student_rows': student_rows
        })

    # Pagination - paginate by subjects (each subject is a section)
    page = request.GET.get('page', 1)
    per_page = 5  # Show 5 subjects per page to avoid screen overflow
    paginator = Paginator(attendance_data, per_page)
    try:
        page_obj = paginator.page(page)
    except:
        page_obj = paginator.page(1)

    return render(request, 'attendance.html', {
        'attendance_data': page_obj if page_obj else [],
        'page_obj': page_obj,
        'tab': 'attendance'
    })

def add_attendance_session(request):
    if request.method == 'POST':
        form = WeeklyAttendanceSessionForm(request.POST)
        if form.is_valid():
            subject = form.cleaned_data['subject']
            week_number = form.cleaned_data['week_number']
            week_start_date = form.cleaned_data['week_start_date']
            week_end_date = form.cleaned_data['week_end_date']
            sessions_per_week = form.cleaned_data['sessions_per_week']

            # Create the weekly session
            session, created = WeeklyAttendanceSession.objects.get_or_create(
                subject=subject,
                week_number=week_number,
                defaults={
                    'week_start_date': week_start_date,
                    'week_end_date': week_end_date,
                    'sessions_per_week': sessions_per_week
                }
            )

            if created:
                # Get assigned grade level for this subject
                assigned_subject = AssignedSubject.objects.filter(
                    subject=subject,
                    status='Active'
                ).first()

                # Filter students by grade level if subject is assigned
                if assigned_subject:
                    students = StudentRecord.objects.filter(
                        status='active',
                        grade_and_section=assigned_subject.grade_level
                    )
                else:
                    students = StudentRecord.objects.filter(status='active')

                # Create empty attendance records for all students
                for student in students:
                    WeeklyAttendanceRecord.objects.get_or_create(
                        session=session,
                        student=student,
                        defaults={
                            'session_1': 'A',
                            'session_2': 'A',
                            'session_3': 'A',
                            'session_4': 'A'
                        }
                    )

                messages.success(request, f'Week {week_number} attendance session created successfully!')
            else:
                messages.warning(request, f'Week {week_number} attendance session already exists for this subject.')

            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': True, 'message': f'Week {week_number} attendance session created successfully!'})
            return redirect('attendance')
    else:
        form = WeeklyAttendanceSessionForm()

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render(request, 'modals/add_attendance_session_modal.html', {
            'form': form,
            'tab': 'attendance'
        })

    return render(request, 'add_attendance_session.html', {
        'form': form,
        'tab': 'attendance'
    })

def mark_attendance(request, session_id):
    """Display modal/form to mark attendance for a specific week"""
    session = get_object_or_404(WeeklyAttendanceSession, id=session_id)

    # Get assigned grade level for this subject
    assigned_subject = AssignedSubject.objects.filter(
        subject=session.subject,
        status='Active'
    ).first()

    # Filter students by grade level if subject is assigned
    if assigned_subject:
        students = StudentRecord.objects.filter(
            status='active',
            grade_and_section=assigned_subject.grade_level
        ).order_by('fullname')
    else:
        students = StudentRecord.objects.filter(status='active').order_by('fullname')

    # Get or create attendance records
    attendance_records = []
    for student in students:
        record, created = WeeklyAttendanceRecord.objects.get_or_create(
            session=session,
            student=student,
            defaults={
                'session_1': 'A',
                'session_2': 'A',
                'session_3': 'A',
                'session_4': 'A'
            }
        )
        attendance_records.append({
            'student': student,
            'record': record
        })

    return render(request, 'mark_attendance.html', {
        'session': session,
        'attendance_records': attendance_records,
        'tab': 'attendance'
    })

def save_attendance(request, session_id):
    """Save attendance marks from the form"""
    session = get_object_or_404(WeeklyAttendanceSession, id=session_id)

    if request.method == 'POST':
        try:
            # Get assigned grade level for this subject
            assigned_subject = AssignedSubject.objects.filter(
                subject=session.subject,
                status='Active'
            ).first()

            # Filter students by grade level if subject is assigned
            if assigned_subject:
                students = StudentRecord.objects.filter(
                    status='active',
                    grade_and_section=assigned_subject.grade_level
                )
            else:
                students = StudentRecord.objects.filter(status='active')

            for student in students:
                # Get the attendance record
                record, created = WeeklyAttendanceRecord.objects.get_or_create(
                    session=session,
                    student=student
                )

                # Update attendance for each session
                for session_num in range(1, 5):
                    key = f'attendance_{student.id}_session_{session_num}'
                    value = request.POST.get(key)
                    if value in ['P', 'A', 'L', 'E']:
                        setattr(record, f'session_{session_num}', value)

                record.save()

            messages.success(request, f'Attendance saved successfully for Week {session.week_number}!')
            return redirect('attendance')
        except Exception as e:
            messages.error(request, f'Error saving attendance: {str(e)}')

    return redirect('attendance')


def delete_student_scores(request, student_id, subject_id):
    """
    Delete all quiz, exam, project, and attendance records
    for a given student and subject, then return to score overview.
    """
    student = get_object_or_404(StudentRecord, id=student_id)
    subject = get_object_or_404(Subject, id=subject_id)

    # Delete detailed score records
    QuizScore.objects.filter(student=student, subject=subject).delete()
    ExamScore.objects.filter(student=student, subject=subject).delete()
    ProjectScore.objects.filter(student=student, subject=subject).delete()

    # Delete weekly attendance records for this subject & student
    sessions = WeeklyAttendanceSession.objects.filter(subject=subject)
    WeeklyAttendanceRecord.objects.filter(session__in=sessions, student=student).delete()

    messages.success(
        request,
        f"All scores and attendance for {student.fullname} in {subject.name} have been deleted.",
    )
    return redirect('score')

from .models import Student, Score

from django.shortcuts import render
from .models import StudentRecord, QuizScore, ExamScore, ProjectScore, Subject, AssignedSubject, WeeklyAttendanceSession, WeeklyAttendanceRecord
from .forms import QuizSetupForm, ExamSetupForm, ProjectSetupForm, WeeklyAttendanceSessionForm
from datetime import datetime, timedelta
from django.utils import timezone

@login_required
@user_passes_test(faculty_required)
def score(request):
    """Score view - accessible by faculty and admin"""
    # Filter by faculty assigned subjects if user is faculty
    if request.user.role == 'faculty':
        # Get assigned subjects for this faculty
        assignments = FacultyAssignment.objects.filter(
            faculty=request.user,
            status='Active'
        )
        assigned_subject_ids = []
        for assignment in assignments:
            assigned_subject_ids.extend(assignment.subjects.values_list('id', flat=True))
        assigned_subject_ids = list(set(assigned_subject_ids))

        if assigned_subject_ids:
            # Filter students by grade level of assigned subjects
            assigned_subjects = Subject.objects.filter(id__in=assigned_subject_ids)
            assigned_grade_levels = AssignedSubject.objects.filter(
                subject__in=assigned_subjects,
                status='Active'
            ).values_list('grade_level', flat=True).distinct()

            # Get students matching assigned grade levels
            # grade_and_section format is "Grade 7 - A", so we need to check if it starts with the grade level
            students = StudentRecord.objects.filter(status='active').order_by('fullname')
            # Filter students whose grade_and_section starts with any assigned grade level
            filtered_students = []
            for student in students:
                if student.grade_and_section:
                    # Extract grade level from grade_and_section (format: "Grade 7 - A" or just "Grade 7")
                    student_grade = student.grade_and_section.split(' - ')[0].strip()
                    if student_grade in assigned_grade_levels:
                        filtered_students.append(student.id)
            students = StudentRecord.objects.filter(id__in=filtered_students).order_by('fullname')

            # Filter subjects to only assigned ones
            subjects_with_scores = Subject.objects.filter(
                id__in=assigned_subject_ids
            ).filter(
                Q(quiz_scores__isnull=False)
                | Q(exam_scores__isnull=False)
                | Q(project_scores__isnull=False)
                | Q(attendance_sessions__isnull=False)
            ).distinct().order_by('name')
        else:
            # No assigned subjects - show empty
            students = StudentRecord.objects.none()
            subjects_with_scores = Subject.objects.none()
    else:
        # Admin sees all
        students = StudentRecord.objects.filter(status='active').order_by('fullname')
        subjects_with_scores = Subject.objects.filter(
            Q(quiz_scores__isnull=False)
            | Q(exam_scores__isnull=False)
            | Q(project_scores__isnull=False)
            | Q(attendance_sessions__isnull=False)
        ).distinct().order_by('name')

    # Calculate averages per student per subject
    student_score_data = []
    for student in students:
        student_subjects = []
        for subject in subjects_with_scores:
            # Calculate quiz average
            quiz_scores = QuizScore.objects.filter(
                student=student,
                subject=subject,
            )
            avg_quiz = None
            if quiz_scores.exists():
                scores = [float(qs.score) for qs in quiz_scores]
                avg_quiz = sum(scores) / len(scores) if scores else None

            # Calculate exam average
            exam_scores = ExamScore.objects.filter(
                student=student,
                subject=subject,
            )
            avg_exam = None
            if exam_scores.exists():
                scores = [float(es.score) for es in exam_scores]
                avg_exam = sum(scores) / len(scores) if scores else None

            # Calculate project average
            project_scores = ProjectScore.objects.filter(
                student=student,
                subject=subject,
            )
            avg_project = None
            if project_scores.exists():
                scores = [float(ps.score) for ps in project_scores]
                avg_project = sum(scores) / len(scores) if scores else None

            # Calculate attendance average (overall percentage across all weeks)
            attendance_sessions = WeeklyAttendanceSession.objects.filter(subject=subject)
            avg_attendance = None
            if attendance_sessions.exists():
                overall_present = 0
                overall_total = 0
                for session in attendance_sessions:
                    try:
                        record = WeeklyAttendanceRecord.objects.get(
                            session=session, student=student
                        )
                        # Count present sessions from individual session fields
                        sessions_list = [record.session_1, record.session_2, record.session_3, record.session_4]
                        present_count = sum(1 for s in sessions_list if s == 'P')
                        total_count = len([s for s in sessions_list if s and s != '-'])
                        overall_present += present_count
                        overall_total += total_count
                    except WeeklyAttendanceRecord.DoesNotExist:
                        continue

                if overall_total > 0:
                    avg_attendance = round((overall_present / overall_total) * 100, 2)

            # Compute overall grade ONLY if ALL components are present
            grade = None
            if avg_quiz is not None and avg_exam is not None and avg_project is not None and avg_attendance is not None:
                # Convert all to float to avoid Decimal/float type mixing
                grade = (float(avg_quiz) + float(avg_exam) + float(avg_project) + float(avg_attendance)) / 4

            # Only add subject if it has at least one type of score or attendance
            if (
                avg_quiz is not None
                or avg_exam is not None
                or avg_project is not None
                or avg_attendance is not None
            ):
                # Determine performance category
                performance_category = None
                if grade is not None:
                    if grade >= 90:
                        performance_category = 'Excellent'
                    elif grade >= 80:
                        performance_category = 'Good'
                    elif grade >= 70:
                        performance_category = 'Average'
                    else:
                        performance_category = 'At Risk'

                # Get ML prediction status if exists
                ml_prediction = MLPredictionStatus.objects.filter(
                    student=student,
                    subject=subject
                ).first()

                student_subjects.append(
                    {
                        'subject': subject,
                        'quiz_average': avg_quiz,
                        'exam_average': avg_exam,
                        'project_average': avg_project,
                        'attendance_average': avg_attendance,
                        'grade': grade,
                        'performance_category': performance_category,
                        'ml_prediction': ml_prediction,
                        'student_id': student.id,
                        'subject_id': subject.id,
                    }
                )

        if student_subjects:
            student_score_data.append(
                {
                    'student': student,
                    'subjects': student_subjects,
                }
            )

    # Pagination for students
    page = request.GET.get('page', 1)
    per_page = 15  # Increased to reduce pagination when not needed
    paginator = Paginator(students, per_page)
    try:
        page_obj = paginator.page(page)
    except:
        page_obj = paginator.page(1)

    # Rebuild student_score_data for paginated students only
    paginated_student_score_data = []
    for student in page_obj:
        student_subjects = []
        for subject in subjects_with_scores:
            # Calculate averages for this student and subject
            avg_quiz = None
            avg_exam = None
            avg_project = None
            avg_attendance = None

            quiz_scores = QuizScore.objects.filter(student=student, subject=subject)
            if quiz_scores.exists():
                avg_quiz = quiz_scores.aggregate(avg=Avg('score'))['avg']

            exam_scores = ExamScore.objects.filter(student=student, subject=subject)
            if exam_scores.exists():
                avg_exam = exam_scores.aggregate(avg=Avg('score'))['avg']

            project_scores = ProjectScore.objects.filter(student=student, subject=subject)
            if project_scores.exists():
                avg_project = project_scores.aggregate(avg=Avg('score'))['avg']

            # Calculate attendance average
            sessions = WeeklyAttendanceSession.objects.filter(subject=subject)
            overall_present = 0
            overall_total = 0
            for session in sessions:
                try:
                    record = WeeklyAttendanceRecord.objects.get(session=session, student=student)
                    # Count present sessions from individual session fields
                    sessions_list = [record.session_1, record.session_2, record.session_3, record.session_4]
                    present_count = sum(1 for s in sessions_list if s == 'P')
                    total_count = len([s for s in sessions_list if s and s != '-'])
                    overall_present += present_count
                    overall_total += total_count
                except WeeklyAttendanceRecord.DoesNotExist:
                    continue

            if overall_total > 0:
                avg_attendance = round((overall_present / overall_total) * 100, 2)

            # Compute overall grade ONLY if ALL components are present
            grade = None
            if avg_quiz is not None and avg_exam is not None and avg_project is not None and avg_attendance is not None:
                # Convert all to float to avoid Decimal/float type mixing
                grade = (float(avg_quiz) + float(avg_exam) + float(avg_project) + float(avg_attendance)) / 4

            # Only add subject if it has at least one type of score or attendance
            if (avg_quiz is not None or avg_exam is not None or avg_project is not None or avg_attendance is not None):
                performance_category = None
                if grade is not None:
                    if grade >= 90:
                        performance_category = 'Excellent'
                    elif grade >= 80:
                        performance_category = 'Good'
                    elif grade >= 70:
                        performance_category = 'Average'
                    else:
                        performance_category = 'At Risk'

                ml_prediction = MLPredictionStatus.objects.filter(
                    student=student,
                    subject=subject
                ).first()

                student_subjects.append({
                    'subject': subject,
                    'subject_id': subject.id,
                    'quiz_average': avg_quiz,
                    'exam_average': avg_exam,
                    'project_average': avg_project,
                    'attendance_average': avg_attendance,
                    'grade': grade,
                    'performance_category': performance_category,
                    'ml_prediction': ml_prediction,
                })

        if student_subjects:
            paginated_student_score_data.append({
                'student': student,
                'subjects': student_subjects,
            })

    return render(
        request,
        'score.html',
        {
            'page_obj': page_obj,
            'student_score_data': paginated_student_score_data,
            'subjects_with_scores': subjects_with_scores,
            'tab': 'score',
        },
    )

def add_quiz(request):
    if request.method == 'POST':
        form = QuizSetupForm(request.POST)
        if form.is_valid():
            subject = form.cleaned_data['subject']
            num_quizzes = form.cleaned_data['number_of_quizzes']

            # Get assigned grade level for this subject
            assigned_subject = AssignedSubject.objects.filter(
                subject=subject,
                status='Active'
            ).first()

            # Filter students by grade level if subject is assigned
            if assigned_subject:
                students = StudentRecord.objects.filter(
                    status='active',
                    grade_and_section=assigned_subject.grade_level
                ).order_by('fullname')
            else:
                # If no assignment, show all active students (fallback)
                students = StudentRecord.objects.filter(status='active').order_by('fullname')

            # Get existing quiz numbers for this subject
            existing_quizzes = QuizScore.objects.filter(subject=subject).values_list('quiz_number', flat=True).distinct()
            max_quiz_num = max(existing_quizzes) if existing_quizzes else 0

            start_quiz_num = max_quiz_num + 1
            quiz_range = list(range(start_quiz_num, start_quiz_num + num_quizzes))

            return render(request, 'add_quiz_scores.html', {
                'subject': subject,
                'num_quizzes': num_quizzes,
                'students': students,
                'start_quiz_num': start_quiz_num,
                'quiz_range': quiz_range,
                'tab': 'quiz'
            })
    else:
        form = QuizSetupForm()

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render(request, 'modals/add_quiz_modal.html', {
            'form': form,
            'tab': 'quiz'
        })

    return render(request, 'add_quiz.html', {
        'form': form,
        'tab': 'quiz'
    })

def save_quiz_scores(request):
    if request.method == 'POST':
        subject_id = request.POST.get('subject_id')
        start_quiz_num = int(request.POST.get('start_quiz_num', 1))
        num_quizzes = int(request.POST.get('num_quizzes', 1))

        subject = get_object_or_404(Subject, id=subject_id)

        # Get assigned grade level for this subject
        assigned_subject = AssignedSubject.objects.filter(
            subject=subject,
            status='Active'
        ).first()

        # Filter students by grade level if subject is assigned
        if assigned_subject:
            students = StudentRecord.objects.filter(
                status='active',
                grade_and_section=assigned_subject.grade_level
            )
        else:
            # If no assignment, use all active students (fallback)
            students = StudentRecord.objects.filter(status='active')

        try:
            for student in students:
                for quiz_num in range(start_quiz_num, start_quiz_num + num_quizzes):
                    score_key = f'score_{student.id}_{quiz_num}'
                    score_value = request.POST.get(score_key)

                    if score_value:
                        score = float(score_value)
                        QuizScore.objects.update_or_create(
                            student=student,
                            subject=subject,
                            quiz_number=quiz_num,
                            defaults={'score': score}
                        )

            messages.success(request, f'Quiz scores saved successfully for {subject.name}!')
            return redirect('quiz')
        except Exception as e:
            messages.error(request, f'Error saving quiz scores: {str(e)}')

    return redirect('quiz')

def add_exam(request):
    if request.method == 'POST':
        form = ExamSetupForm(request.POST)
        if form.is_valid():
            subject = form.cleaned_data['subject']
            num_exams = form.cleaned_data['number_of_exams']

            # Get assigned grade level for this subject
            assigned_subject = AssignedSubject.objects.filter(
                subject=subject,
                status='Active'
            ).first()

            # Filter students by grade level if subject is assigned
            if assigned_subject:
                students = StudentRecord.objects.filter(
                    status='active',
                    grade_and_section=assigned_subject.grade_level
                ).order_by('fullname')
            else:
                # If no assignment, show all active students (fallback)
                students = StudentRecord.objects.filter(status='active').order_by('fullname')

            # Get existing exam numbers for this subject
            existing_exams = ExamScore.objects.filter(subject=subject).values_list('exam_number', flat=True).distinct()
            max_exam_num = max(existing_exams) if existing_exams else 0

            start_exam_num = max_exam_num + 1
            exam_range = list(range(start_exam_num, start_exam_num + num_exams))

            return render(request, 'add_exam_scores.html', {
                'subject': subject,
                'num_exams': num_exams,
                'students': students,
                'start_exam_num': start_exam_num,
                'exam_range': exam_range,
                'tab': 'exam'
            })
    else:
        form = ExamSetupForm()

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render(request, 'modals/add_exam_modal.html', {
            'form': form,
            'tab': 'exam'
        })

    return render(request, 'add_exam.html', {
        'form': form,
        'tab': 'exam'
    })

def save_exam_scores(request):
    if request.method == 'POST':
        subject_id = request.POST.get('subject_id')
        start_exam_num = int(request.POST.get('start_exam_num', 1))
        num_exams = int(request.POST.get('num_exams', 1))

        subject = get_object_or_404(Subject, id=subject_id)

        # Get assigned grade level for this subject
        assigned_subject = AssignedSubject.objects.filter(
            subject=subject,
            status='Active'
        ).first()

        # Filter students by grade level if subject is assigned
        if assigned_subject:
            students = StudentRecord.objects.filter(
                status='active',
                grade_and_section=assigned_subject.grade_level
            )
        else:
            # If no assignment, use all active students (fallback)
            students = StudentRecord.objects.filter(status='active')

        try:
            for student in students:
                for exam_num in range(start_exam_num, start_exam_num + num_exams):
                    score_key = f'score_{student.id}_{exam_num}'
                    score_value = request.POST.get(score_key)

                    if score_value:
                        score = float(score_value)
                        ExamScore.objects.update_or_create(
                            student=student,
                            subject=subject,
                            exam_number=exam_num,
                            defaults={'score': score}
                        )

            messages.success(request, f'Exam scores saved successfully for {subject.name}!')
            return redirect('exam')
        except Exception as e:
            messages.error(request, f'Error saving exam scores: {str(e)}')

    return redirect('exam')

def add_project(request):
    if request.method == 'POST':
        form = ProjectSetupForm(request.POST)
        if form.is_valid():
            subject = form.cleaned_data['subject']
            num_projects = form.cleaned_data['number_of_projects']

            # Get assigned grade level for this subject
            assigned_subject = AssignedSubject.objects.filter(
                subject=subject,
                status='Active'
            ).first()

            # Filter students by grade level if subject is assigned
            if assigned_subject:
                students = StudentRecord.objects.filter(
                    status='active',
                    grade_and_section=assigned_subject.grade_level
                ).order_by('fullname')
            else:
                # If no assignment, show all active students (fallback)
                students = StudentRecord.objects.filter(status='active').order_by('fullname')

            # Get existing project numbers for this subject
            existing_projects = ProjectScore.objects.filter(subject=subject).values_list('project_number', flat=True).distinct()
            max_project_num = max(existing_projects) if existing_projects else 0

            start_project_num = max_project_num + 1
            project_range = list(range(start_project_num, start_project_num + num_projects))

            return render(request, 'add_project_scores.html', {
                'subject': subject,
                'num_projects': num_projects,
                'students': students,
                'start_project_num': start_project_num,
                'project_range': project_range,
                'tab': 'project'
            })
    else:
        form = ProjectSetupForm()

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render(request, 'modals/add_project_modal.html', {
            'form': form,
            'tab': 'project'
        })

    return render(request, 'add_project.html', {
        'form': form,
        'tab': 'project'
    })

def save_project_scores(request):
    if request.method == 'POST':
        subject_id = request.POST.get('subject_id')
        start_project_num = int(request.POST.get('start_project_num', 1))
        num_projects = int(request.POST.get('num_projects', 1))

        subject = get_object_or_404(Subject, id=subject_id)

        # Get assigned grade level for this subject
        assigned_subject = AssignedSubject.objects.filter(
            subject=subject,
            status='Active'
        ).first()

        # Filter students by grade level if subject is assigned
        if assigned_subject:
            students = StudentRecord.objects.filter(
                status='active',
                grade_and_section=assigned_subject.grade_level
            )
        else:
            # If no assignment, use all active students (fallback)
            students = StudentRecord.objects.filter(status='active')

        try:
            for student in students:
                for project_num in range(start_project_num, start_project_num + num_projects):
                    score_key = f'score_{student.id}_{project_num}'
                    score_value = request.POST.get(score_key)

                    if score_value:
                        score = float(score_value)
                        ProjectScore.objects.update_or_create(
                            student=student,
                            subject=subject,
                            project_number=project_num,
                            defaults={'score': score}
                        )

            messages.success(request, f'Project scores saved successfully for {subject.name}!')
            return redirect('project')
        except Exception as e:
            messages.error(request, f'Error saving project scores: {str(e)}')

    return redirect('project')

# ==================== MACHINE LEARNING INTEGRATION ====================
try:
    import numpy as np
    from sklearn.linear_model import LinearRegression
    from sklearn.tree import DecisionTreeClassifier
    from sklearn.model_selection import train_test_split
    SKLEARN_AVAILABLE = True
    NUMPY_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    NUMPY_AVAILABLE = False
    # numpy and sklearn are optional - ML features will be disabled if not installed

def prepare_ml_data():
    """Prepare training data from existing scores"""
    if not NUMPY_AVAILABLE:
        return None, None, None

    X = []  # Features: quiz_avg, exam_avg, project_avg, attendance_avg
    y_grade = []  # Target: final grade (for regression)
    y_category = []  # Target: performance category (for classification)

    students = StudentRecord.objects.filter(status='active')
    for student in students:
        subjects_with_scores = Subject.objects.filter(
            Q(quiz_scores__student=student) |
            Q(exam_scores__student=student) |
            Q(project_scores__student=student) |
            Q(attendance_sessions__attendance_records__student=student)
        ).distinct()

        for subject in subjects_with_scores:
            # Calculate averages
            quiz_scores = QuizScore.objects.filter(student=student, subject=subject)
            avg_quiz = None
            if quiz_scores.exists():
                scores = [float(qs.score) for qs in quiz_scores]
                avg_quiz = sum(scores) / len(scores) if scores else None

            exam_scores = ExamScore.objects.filter(student=student, subject=subject)
            avg_exam = None
            if exam_scores.exists():
                scores = [float(es.score) for es in exam_scores]
                avg_exam = sum(scores) / len(scores) if scores else None

            project_scores = ProjectScore.objects.filter(student=student, subject=subject)
            avg_project = None
            if project_scores.exists():
                scores = [float(ps.score) for ps in project_scores]
                avg_project = sum(scores) / len(scores) if scores else None

            attendance_sessions = WeeklyAttendanceSession.objects.filter(subject=subject)
            avg_attendance = None
            if attendance_sessions.exists():
                overall_present = 0
                overall_total = 0
                for session in attendance_sessions:
                    try:
                        record = WeeklyAttendanceRecord.objects.get(session=session, student=student)
                        summary = record.get_attendance_summary()
                        sessions_list = summary.split(',')
                        present_count = sum(1 for s in sessions_list if s == 'P')
                        total_count = len([s for s in sessions_list if s != '-'])
                        overall_present += present_count
                        overall_total += total_count
                    except WeeklyAttendanceRecord.DoesNotExist:
                        continue
                if overall_total > 0:
                    avg_attendance = round((overall_present / overall_total) * 100, 2)

            # Only include if all features are present
            if avg_quiz is not None and avg_exam is not None and avg_project is not None and avg_attendance is not None:
                # Convert all to float to avoid Decimal/float type mixing
                grade = (float(avg_quiz) + float(avg_exam) + float(avg_project) + float(avg_attendance)) / 4
                X.append([avg_quiz, avg_exam, avg_project, avg_attendance])
                y_grade.append(grade)

                # Categorize performance
                if grade >= 90:
                    y_category.append('Excellent')
                elif grade >= 80:
                    y_category.append('Good')
                elif grade >= 70:
                    y_category.append('Average')
                else:
                    y_category.append('At Risk')

    if len(X) == 0:
        return None, None, None

    try:
        return np.array(X), np.array(y_grade), np.array(y_category)
    except NameError:
        return None, None, None

def train_ml_models():
    """Train ML models for grade prediction"""
    if not SKLEARN_AVAILABLE:
        return None, None, None

    X, y_grade, y_category = prepare_ml_data()

    if X is None or len(X) < 10:  # Need at least 10 samples
        return None, None, None

    # Split data
    X_train, X_test, y_grade_train, y_grade_test, y_cat_train, y_cat_test = train_test_split(
        X, y_grade, y_category, test_size=0.2, random_state=42
    )

    # Train Linear Regression for grade prediction
    regressor = LinearRegression()
    regressor.fit(X_train, y_grade_train)

    # Train Decision Tree for category prediction
    category_map = {'Excellent': 0, 'Good': 1, 'Average': 2, 'At Risk': 3}
    y_cat_train_numeric = [category_map[cat] for cat in y_cat_train]
    classifier = DecisionTreeClassifier(random_state=42, max_depth=5)
    classifier.fit(X_train, y_cat_train_numeric)

    return regressor, classifier, category_map

@login_required
@user_passes_test(faculty_required)
def predict_student_performance(request, student_id, subject_id):
    """Predict student's final grade and performance category"""
    if not SKLEARN_AVAILABLE or not NUMPY_AVAILABLE:
        error_msg = 'Machine Learning features require numpy and scikit-learn. Please install: pip install numpy scikit-learn'
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'message': error_msg}, status=400)
        messages.error(request, error_msg)
        return redirect('score')

    student = get_object_or_404(StudentRecord, id=student_id)
    subject = get_object_or_404(Subject, id=subject_id)

    # Get current averages
    quiz_scores = QuizScore.objects.filter(student=student, subject=subject)
    avg_quiz = None
    if quiz_scores.exists():
        scores = [float(qs.score) for qs in quiz_scores]
        avg_quiz = sum(scores) / len(scores) if scores else None

    exam_scores = ExamScore.objects.filter(student=student, subject=subject)
    avg_exam = None
    if exam_scores.exists():
        scores = [float(es.score) for es in exam_scores]
        avg_exam = sum(scores) / len(scores) if scores else None

    project_scores = ProjectScore.objects.filter(student=student, subject=subject)
    avg_project = None
    if project_scores.exists():
        scores = [float(ps.score) for ps in project_scores]
        avg_project = sum(scores) / len(scores) if scores else None

    attendance_sessions = WeeklyAttendanceSession.objects.filter(subject=subject)
    avg_attendance = None
    if attendance_sessions.exists():
        overall_present = 0
        overall_total = 0
        for session in attendance_sessions:
            try:
                record = WeeklyAttendanceRecord.objects.get(session=session, student=student)
                summary = record.get_attendance_summary()
                sessions_list = summary.split(',')
                present_count = sum(1 for s in sessions_list if s == 'P')
                total_count = len([s for s in sessions_list if s != '-'])
                overall_present += present_count
                overall_total += total_count
            except WeeklyAttendanceRecord.DoesNotExist:
                continue
        if overall_total > 0:
            avg_attendance = round((overall_present / overall_total) * 100, 2)

    # Use available scores only - no requirement for all categories
    # Calculate grade from available components
    components = []
    weights = []

    if avg_quiz is not None:
        components.append(avg_quiz)
        weights.append(0.25)  # Default weight for quiz
    if avg_exam is not None:
        components.append(avg_exam)
        weights.append(0.30)  # Default weight for exam
    if avg_project is not None:
        components.append(avg_project)
        weights.append(0.25)  # Default weight for project
    if avg_attendance is not None:
        # Convert attendance percentage to grade scale (0-100)
        attendance_grade = avg_attendance  # Already a percentage
        components.append(attendance_grade)
        weights.append(0.20)  # Default weight for attendance

    if not components:
        error_msg = 'No scores available for prediction.'
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'message': error_msg}, status=400)
        messages.warning(request, error_msg)
        return redirect('score')

    # Normalize weights to sum to 1.0
    total_weight = sum(weights)
    if total_weight > 0:
        weights = [w / total_weight for w in weights]

    # Calculate weighted average grade
    predicted_grade = sum(comp * weight for comp, weight in zip(components, weights))

    # Determine category based on grade
    if predicted_grade >= 90:
        predicted_category = 'Excellent'
    elif predicted_grade >= 80:
        predicted_category = 'Good'
    elif predicted_grade >= 70:
        predicted_category = 'Average'
    else:
        predicted_category = 'At Risk'

    # Save prediction to database
    MLPredictionStatus.objects.update_or_create(
        student=student,
        subject=subject,
        defaults={
            'predicted_grade': predicted_grade,
            'predicted_category': predicted_category,
        }
    )

    messages.success(request, f'Grade prediction saved for {student.fullname} in {subject.name}')

    # Return JSON for AJAX requests
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'message': f'Grade prediction saved for {student.fullname} in {subject.name}',
            'predicted_grade': round(predicted_grade, 2),
            'predicted_category': predicted_category
        })

    return redirect('score')

@login_required
@user_passes_test(faculty_required)
def get_at_risk_students(request):
    """Get list of students who are at risk based on current grades (< 70)"""
    students = StudentRecord.objects.filter(status='active')
    at_risk_list = []

    for student in students:
        subjects_with_scores = Subject.objects.filter(
            Q(quiz_scores__student=student) |
            Q(exam_scores__student=student) |
            Q(project_scores__student=student) |
            Q(attendance_sessions__attendance_records__student=student)
        ).distinct()

        for subject in subjects_with_scores:
            quiz_scores = QuizScore.objects.filter(student=student, subject=subject)
            exam_scores = ExamScore.objects.filter(student=student, subject=subject)
            project_scores = ProjectScore.objects.filter(student=student, subject=subject)
            attendance_sessions = WeeklyAttendanceSession.objects.filter(subject=subject)

            avg_quiz = None
            if quiz_scores.exists():
                scores = [float(qs.score) for qs in quiz_scores]
                avg_quiz = sum(scores) / len(scores) if scores else None

            avg_exam = None
            if exam_scores.exists():
                scores = [float(es.score) for es in exam_scores]
                avg_exam = sum(scores) / len(scores) if scores else None

            avg_project = None
            if project_scores.exists():
                scores = [float(ps.score) for ps in project_scores]
                avg_project = sum(scores) / len(scores) if scores else None

            avg_attendance = None
            if attendance_sessions.exists():
                overall_present = 0
                overall_total = 0
                for session in attendance_sessions:
                    try:
                        record = WeeklyAttendanceRecord.objects.get(session=session, student=student)
                        summary = record.get_attendance_summary()
                        sessions_list = summary.split(',')
                        present_count = sum(1 for s in sessions_list if s == 'P')
                        total_count = len([s for s in sessions_list if s != '-'])
                        overall_present += present_count
                        overall_total += total_count
                    except WeeklyAttendanceRecord.DoesNotExist:
                        continue
                if overall_total > 0:
                    avg_attendance = round((overall_present / overall_total) * 100, 2)

            # Calculate grade from available scores
            available_scores = []
            if avg_quiz is not None:
                available_scores.append(avg_quiz)
            if avg_exam is not None:
                available_scores.append(avg_exam)
            if avg_project is not None:
                available_scores.append(avg_project)
            if avg_attendance is not None:
                available_scores.append(avg_attendance)

            if available_scores:
                current_grade = sum(available_scores) / len(available_scores)

                # Categorize: <70 = At Risk, 70-79 = Average, 80-89 = Good, 90+ = Excellent
                if current_grade < 70:
                    at_risk_list.append({
                        'student': student,
                        'subject': subject,
                        'current_grade': current_grade,
                        'performance_category': 'At Risk',
                        'avg_quiz': avg_quiz,
                        'avg_exam': avg_exam,
                        'avg_project': avg_project,
                        'avg_attendance': avg_attendance,
                    })

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render(request, 'modals/at_risk_students_modal.html', {
            'at_risk_list': at_risk_list,
            'tab': 'score'
        })
    return render(request, 'at_risk_students.html', {
        'at_risk_list': at_risk_list,
        'tab': 'score'
    })

# ==================== PDF GENERATION ====================
from django.http import HttpResponse
from io import BytesIO
from datetime import datetime

def generate_grade_pdf(request, student_id):
    """Generate PDF report for a student's grades and scores"""
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
        from reportlab.lib import colors
    except ImportError:
        messages.error(request, 'PDF generation requires reportlab. Please install: pip install reportlab')
        return redirect('score')

    student = get_object_or_404(StudentRecord, id=student_id)

    # Get all subjects with scores
    subjects_with_scores = Subject.objects.filter(
        Q(quiz_scores__student=student) |
        Q(exam_scores__student=student) |
        Q(project_scores__student=student) |
        Q(attendance_sessions__attendance_records__student=student)
    ).distinct()

    # Create PDF buffer
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    elements = []

    # Styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#1f2937'),
        spaceAfter=30,
    )

    # Title
    elements.append(Paragraph(f"Grade Report - {student.fullname}", title_style))
    elements.append(Paragraph(f"Student ID: {student.student_id} | Grade & Section: {student.grade_and_section}", styles['Normal']))
    elements.append(Paragraph(f"Generated on: {datetime.now().strftime('%B %d, %Y')}", styles['Normal']))
    elements.append(Spacer(1, 0.3*inch))

    # Build data for each subject
    for subject in subjects_with_scores:
        # Calculate averages
        quiz_scores = QuizScore.objects.filter(student=student, subject=subject)
        exam_scores = ExamScore.objects.filter(student=student, subject=subject)
        project_scores = ProjectScore.objects.filter(student=student, subject=subject)

        avg_quiz = None
        if quiz_scores.exists():
            scores = [float(qs.score) for qs in quiz_scores]
            avg_quiz = sum(scores) / len(scores) if scores else None

        avg_exam = None
        if exam_scores.exists():
            scores = [float(es.score) for es in exam_scores]
            avg_exam = sum(scores) / len(scores) if scores else None

        avg_project = None
        if project_scores.exists():
            scores = [float(ps.score) for ps in project_scores]
            avg_project = sum(scores) / len(scores) if scores else None

        # Calculate attendance
        attendance_sessions = WeeklyAttendanceSession.objects.filter(subject=subject)
        avg_attendance = None
        if attendance_sessions.exists():
            overall_present = 0
            overall_total = 0
            for session in attendance_sessions:
                try:
                    record = WeeklyAttendanceRecord.objects.get(session=session, student=student)
                    summary = record.get_attendance_summary()
                    sessions_list = summary.split(',')
                    present_count = sum(1 for s in sessions_list if s == 'P')
                    total_count = len([s for s in sessions_list if s != '-'])
                    overall_present += present_count
                    overall_total += total_count
                except WeeklyAttendanceRecord.DoesNotExist:
                    continue
            if overall_total > 0:
                avg_attendance = round((overall_present / overall_total) * 100, 2)

        # Calculate grade
        grade = None
        if avg_quiz is not None and avg_exam is not None and avg_project is not None and avg_attendance is not None:
            grade = (avg_quiz + avg_exam + avg_project + avg_attendance) / 4

        # Subject header
        elements.append(Paragraph(f"<b>{subject.name} ({subject.code})</b>", styles['Heading2']))

        # Create table data
        data = [
            ['Category', 'Average'],
            ['Quiz', f"{avg_quiz:.2f}" if avg_quiz else "N/A"],
            ['Exam', f"{avg_exam:.2f}" if avg_exam else "N/A"],
            ['Project', f"{avg_project:.2f}" if avg_project else "N/A"],
            ['Attendance', f"{avg_attendance:.2f}%" if avg_attendance else "N/A"],
            ['Overall Grade', f"{grade:.2f}" if grade else "N/A"],
        ]

        table = Table(data, colWidths=[3*inch, 2*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1f2937')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ]))

        elements.append(table)
        elements.append(Spacer(1, 0.3*inch))

    # Build PDF
    doc.build(elements)
    buffer.seek(0)

    # Create response
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="grade_report_{student.fullname}_{datetime.now().strftime("%Y%m%d")}.pdf"'
    return response

# ==================== EDIT SCORES ====================
def edit_quiz_scores(request, student_id, subject_id):
    """Edit quiz scores for a specific student and subject"""
    student = get_object_or_404(StudentRecord, id=student_id)
    subject = get_object_or_404(Subject, id=subject_id)

    if request.method == 'POST':
        try:
            for key, value in request.POST.items():
                if key.startswith('quiz_') and value:
                    quiz_num = int(key.split('_')[1])
                    score = float(value)
                    QuizScore.objects.update_or_create(
                        student=student,
                        subject=subject,
                        quiz_number=quiz_num,
                        defaults={'score': score}
                    )
            messages.success(request, f'Quiz scores updated for {student.fullname}!')
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': True, 'message': f'Quiz scores updated for {student.fullname}!'})
            return redirect('score')
        except Exception as e:
            messages.error(request, f'Error updating quiz scores: {str(e)}')

    # Get all quiz scores for this student and subject
    quiz_scores = QuizScore.objects.filter(student=student, subject=subject).order_by('quiz_number')
    quiz_dict = {qs.quiz_number: qs.score for qs in quiz_scores}

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render(request, 'modals/edit_quiz_scores_modal.html', {
            'student': student,
            'subject': subject,
            'quiz_scores': quiz_dict,
            'student_id': student_id,
            'subject_id': subject_id,
            'tab': 'quiz'
        })
    return render(request, 'edit_quiz_scores.html', {
        'student': student,
        'subject': subject,
        'quiz_scores': quiz_dict,
        'tab': 'quiz'
    })

def edit_exam_scores(request, student_id, subject_id):
    """Edit exam scores for a specific student and subject"""
    student = get_object_or_404(StudentRecord, id=student_id)
    subject = get_object_or_404(Subject, id=subject_id)

    if request.method == 'POST':
        try:
            for key, value in request.POST.items():
                if key.startswith('exam_') and value:
                    exam_num = int(key.split('_')[1])
                    score = float(value)
                    ExamScore.objects.update_or_create(
                        student=student,
                        subject=subject,
                        exam_number=exam_num,
                        defaults={'score': score}
                    )
            messages.success(request, f'Exam scores updated for {student.fullname}!')
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': True, 'message': f'Exam scores updated for {student.fullname}!'})
            return redirect('score')
        except Exception as e:
            messages.error(request, f'Error updating exam scores: {str(e)}')

    exam_scores = ExamScore.objects.filter(student=student, subject=subject).order_by('exam_number')
    exam_dict = {es.exam_number: es.score for es in exam_scores}

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render(request, 'modals/edit_exam_scores_modal.html', {
            'student': student,
            'subject': subject,
            'exam_scores': exam_dict,
            'student_id': student_id,
            'subject_id': subject_id,
            'tab': 'exam'
        })
    return render(request, 'edit_exam_scores.html', {
        'student': student,
        'subject': subject,
        'exam_scores': exam_dict,
        'tab': 'exam'
    })

def edit_project_scores(request, student_id, subject_id):
    """Edit project scores for a specific student and subject"""
    student = get_object_or_404(StudentRecord, id=student_id)
    subject = get_object_or_404(Subject, id=subject_id)

    if request.method == 'POST':
        try:
            for key, value in request.POST.items():
                if key.startswith('project_') and value:
                    project_num = int(key.split('_')[1])
                    score = float(value)
                    ProjectScore.objects.update_or_create(
                        student=student,
                        subject=subject,
                        project_number=project_num,
                        defaults={'score': score}
                    )
            messages.success(request, f'Project scores updated for {student.fullname}!')
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': True, 'message': f'Project scores updated for {student.fullname}!'})
            return redirect('score')
        except Exception as e:
            messages.error(request, f'Error updating project scores: {str(e)}')

    project_scores = ProjectScore.objects.filter(student=student, subject=subject).order_by('project_number')
    project_dict = {ps.project_number: ps.score for ps in project_scores}

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render(request, 'modals/edit_project_scores_modal.html', {
            'student': student,
            'subject': subject,
            'project_scores': project_dict,
            'student_id': student_id,
            'subject_id': subject_id,
            'tab': 'project'
        })
    return render(request, 'edit_project_scores.html', {
        'student': student,
        'subject': subject,
        'project_scores': project_dict,
        'tab': 'project'
    })

def edit_attendance_scores(request, student_id, subject_id):
    """Edit attendance for a specific student and subject"""
    student = get_object_or_404(StudentRecord, id=student_id)
    subject = get_object_or_404(Subject, id=subject_id)

    if request.method == 'POST':
        try:
            sessions = WeeklyAttendanceSession.objects.filter(subject=subject)
            for session in sessions:
                record, created = WeeklyAttendanceRecord.objects.get_or_create(
                    session=session,
                    student=student
                )
                for session_num in range(1, 5):
                    key = f'attendance_{session.id}_session_{session_num}'
                    value = request.POST.get(key)
                    if value in ['P', 'A', 'L', 'E']:
                        setattr(record, f'session_{session_num}', value)
                record.save()
            messages.success(request, f'Attendance updated for {student.fullname}!')
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': True, 'message': f'Attendance updated for {student.fullname}!'})
            return redirect('score')
        except Exception as e:
            messages.error(request, f'Error updating attendance: {str(e)}')
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'message': f'Error updating attendance: {str(e)}'})

    sessions = WeeklyAttendanceSession.objects.filter(subject=subject).order_by('week_number')
    attendance_data = {}
    for session in sessions:
        try:
            record = WeeklyAttendanceRecord.objects.get(session=session, student=student)
            attendance_data[session.id] = {
                'session': session,
                'record': record,
                'sessions': [record.session_1 or '-', record.session_2 or '-', record.session_3 or '-', record.session_4 or '-']
            }
        except WeeklyAttendanceRecord.DoesNotExist:
            attendance_data[session.id] = {
                'session': session,
                'record': None,
                'sessions': ['-', '-', '-', '-']
            }

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render(request, 'modals/edit_attendance_scores_modal.html', {
            'student': student,
            'subject': subject,
            'attendance_data': attendance_data,
            'student_id': student_id,
            'subject_id': subject_id,
            'tab': 'attendance'
        })
    attendance_records = []
    for session in sessions:
        record, created = WeeklyAttendanceRecord.objects.get_or_create(
            session=session,
            student=student,
            defaults={'session_1': 'A', 'session_2': 'A', 'session_3': 'A', 'session_4': 'A'}
        )
        attendance_records.append({
            'session': session,
            'record': record
        })
    return render(request, 'edit_attendance_scores.html', {
        'student': student,
        'subject': subject,
        'attendance_records': attendance_records,
        'tab': 'attendance'
    })

