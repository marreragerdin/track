from django.contrib.messages import success
from django.shortcuts import render, redirect
from .forms import LoginForm
from django.contrib.auth import authenticate, login
from .models import Student, Faculty, Subject, AuditTrail, User
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect
from .forms import UserForm, StudentForm, FacultyForm
from django.db.models import Q
from .models import SchoolYear, Subject, Section, FacultyAssignment, GradingComponent
from .forms import SchoolYearForm, SubjectForm, SectionForm, FacultyAssignmentForm, GradingComponentForm
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth import get_user_model
from .models import SchoolYear, Subject, Section, FacultyAssignment, GradingComponent
from .forms import SchoolYearForm, SubjectForm, SectionForm, FacultyAssignmentForm, GradingComponentForm




# Create your views here.


def index(request):
    return render(request, 'index.html')




def login_view(request):
    form = LoginForm(request.POST or None)
    msg = None
    if request.method == 'POST' and form.is_valid():
        username = form.cleaned_data.get('username')
        password = form.cleaned_data.get('password')
        user = authenticate(username=username, password=password)
        if user is not None:
            login(request, user)
            # Redirect based on role
            if user.role == 'admin':
                return redirect('adminpage')
            elif user.role == 'student':
                return redirect('student')
            elif user.role == 'faculty':
                return redirect('faculty')
        else:
            msg = 'Invalid credentials'
    return render(request, 'login.html', {'form': form, 'msg': msg})




def admin(request):
    return render(request,'admin.html')


def student(request):
    return render(request,'student.html')


def faculty(request):
    return render(request,'faculty.html')

def admin_dashboard(request):
    total_students = Student.objects.count()
    total_faculty = Faculty.objects.count()
    active_school_year = "2025-2026"  # Replace with dynamic model if you have one
    context = {
        'total_students': total_students,
        'total_faculty': total_faculty,
        'active_school_year': active_school_year
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


# account/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import User, Student, Faculty, Subject, AuditTrail
from .forms import UserForm, StudentForm, FacultyForm
from django.db.models import Q

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

    context = {
        'tab': tab,
        'students': students,
        'faculty': faculty,
        'admins': admins,
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
        if form.is_valid():
            if role == "admin":
                user = form.save(commit=False)
                user.is_admin = True
                user.role = "admin"
                if form.cleaned_data.get('password'):
                    user.set_password(form.cleaned_data['password'])
                user.save()

            elif role == "student":
                user = User.objects.create_user(
                    username=form.cleaned_data['username'],
                    password=form.cleaned_data['password'],
                    first_name=form.cleaned_data['first_name'],
                    last_name=form.cleaned_data['last_name'],
                )
                user.is_student = True
                user.role = "student"
                user.save()

                Student.objects.create(
                    user=user,
                    year_level=form.cleaned_data['year_level'],
                    section=form.cleaned_data['section'],
                    course=form.cleaned_data['course'],
                    status=form.cleaned_data['status']
                )

            elif role == "faculty":
                user = User.objects.create_user(
                    username=form.cleaned_data['username'],
                    password=form.cleaned_data['password'],
                    first_name=form.cleaned_data['first_name'],
                    last_name=form.cleaned_data['last_name'],
                )
                user.is_faculty = True
                user.role = "faculty"
                user.save()

                faculty = Faculty.objects.create(
                    user=user,
                    department=form.cleaned_data['department'],
                    status=form.cleaned_data['status']
                )
                faculty.subjects.set(form.cleaned_data['subjects'])

            return redirect("manage_user")
    else:
        form = form_class()

    return render(request, "add_user.html", {"form": form, "role": role})




@login_required
def edit_user(request, user_type, pk):
    if user_type == 'student':
        obj = get_object_or_404(Student, pk=pk)
        form_class = StudentForm
    elif user_type == 'faculty':
        obj = get_object_or_404(Faculty, pk=pk)
        form_class = FacultyForm
    else:
        obj = get_object_or_404(User, pk=pk)
        form_class = UserForm

    if request.method == 'POST':
        form = form_class(request.POST, instance=obj)
        if form.is_valid():
            obj = form.save()
            AuditTrail.objects.create(user=request.user, action=f"Edited {user_type} {obj}")
            return redirect('manage_user')
    else:
        form = form_class(instance=obj)

    return render(request, 'edit_user.html', {'form': form, 'user_type': user_type})


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

    faculties = User.objects.filter(is_faculty=True)
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

# ---------- Add School Year ----------
def add_school_year(request):
    if request.method == 'POST':
        year = request.POST.get('year')
        status = request.POST.get('status', 'Active')
        SchoolYear.objects.create(year=year, status=status)
        messages.success(request, 'School Year added successfully!')
        return redirect('/academic_setup/?tab=school_year')

    # Generate years list
    current_year = 2025  # you can use datetime.now().year
    years = list(range(current_year, current_year+5))
    return render(request, 'add_school_year.html', {'years': years})


def add_subject(request):
    if request.method == 'POST':
        code = request.POST.get('code')
        name = request.POST.get('name')
        status = request.POST.get('status', 'Active')
        # Collect section names and store them as comma-separated text
        section_list = []

        # Create Subject first
        subject = Subject.objects.create(
            code=code,
            name=name,
            status=status
        )

        # Save Section records
        for i in range(1, sections_count + 1):
            section_name = request.POST.get(f'section_{i}')
            if section_name:
                section_list.append(section_name)

                Section.objects.create(
                    name=section_name,
                    adviser='',
                    number_of_students=0,
                    status='Active',
                    subject=subject
                )

        # Save comma-separated list into the Subject model
        subject.sections_covered = ", ".join(section_list)
        subject.save()

        messages.success(request, 'Subject added successfully!')
        return redirect('/academic_setup/?tab=subject')

    return render(request, 'add_subject.html')

# ---------- Add Section ----------
def add_section(request):
    if request.method == 'POST':
        grade = request.POST.get('grade')
        name = request.POST.get('name')
        adviser = request.POST.get('adviser')
        number_of_students = request.POST.get('number_of_students', 0)
        status = request.POST.get('status', 'Active')

        Section.objects.create(
            grade=grade,
            name=name,
            adviser=adviser,
            number_of_students=number_of_students,
            status=status
        )
        messages.success(request, 'Section added successfully!')
        return redirect('/academic_setup/?tab=section')

    return render(request, 'add_section.html')


# ---------- Assign Faculty ----------
@login_required
def add_faculty(request):
    subjects_qs = Subject.objects.all()
    faculties = Faculty.objects.select_related('user').all()  # all faculty in DB

    if request.method == 'POST':
        # --- Replace your old update_or_create code with this ---
        faculty_id = request.POST.get('faculty_8')  # adjust based on your form
        subject_ids = request.POST.getlist('subject')  # list of selected subjects
        status = request.POST.get('status')

        faculty_instance = User.objects.get(id=faculty_id)
        subjects_qs = Subject.objects.filter(id__in=subject_ids)

        # Create or update the FacultyAssignment object
        assignment, created = FacultyAssignment.objects.update_or_create(
            faculty=faculty_instance,
            defaults={'status': status}
        )

        # Assign the subjects properly
        assignment.subjects.set(subjects_qs)

        messages.success(request, "Faculty assigned successfully!")
        return redirect('/academic_setup/?tab=faculty')

    context = {
        'subjects_qs': subjects_qs,
        'faculties': faculties,
    }
    return render(request, 'add_faculty.html', context)


# ---------- Add Grading Component ----------
def add_grading(request):
    if request.method == 'POST':
        component = request.POST.get('component')
        weight = request.POST.get('weight', 0)
        status = request.POST.get('status', 'Active')

        GradingComponent.objects.create(
            component=component,
            weight=weight,
            status=status
        )
        messages.success(request, 'Grading Component added successfully!')
        return redirect('/academic_setup/?tab=grading')

    return render(request, 'add_grading.html')

def admin_required(user):
    return user.is_authenticated and getattr(user, "is_admin", False)

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

    faculties = User.objects.filter(is_faculty=True)
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

# ---------- Add School Year ----------
def add_school_year(request):
    if request.method == 'POST':
        year = request.POST.get('year')
        status = request.POST.get('status', 'Active')
        SchoolYear.objects.create(year=year, status=status)
        messages.success(request, 'School Year added successfully!')
        return redirect('/academic_setup/?tab=school_year')

    # Generate years list
    current_year = 2025  # you can use datetime.now().year
    years = list(range(current_year, current_year+5))
    return render(request, 'add_school_year.html', {'years': years})


# ---------- Add Subject ----------
def add_subject(request):
    if request.method == 'POST':
        code = request.POST.get('code')
        name = request.POST.get('name')
        grade_level = request.POST.get('grade_level')
        status = request.POST.get('status', 'Active')

        subject = Subject.objects.create(
            code=code, name=name, grade_level=grade_level, status=status
        )

        messages.success(request, 'Subject added successfully!')
        return redirect('/academic_setup/?tab=subject')

    return render(request, 'add_subject.html')


# ---------- Add Section ----------
def add_section(request):
    if request.method == 'POST':
        grade = request.POST.get('grade')
        name = request.POST.get('name')
        adviser = request.POST.get('adviser')
        number_of_students = request.POST.get('number_of_students', 0)
        status = request.POST.get('status', 'Active')

        Section.objects.create(
            grade=grade,
            name=name,
            adviser=adviser,
            number_of_students=number_of_students,
            status=status
        )
        messages.success(request, 'Section added successfully!')
        return redirect('/academic_setup/?tab=section')

    return render(request, 'add_section.html')


# ---------- Assign Faculty ----------
def add_faculty(request):
    subjects_qs = Subject.objects.all()
    faculties = Faculty.objects.all()  # Use Faculty model

    if request.method == 'POST':
        subject_id = request.POST.get('subject')
        status = request.POST.get('status', 'Active')
        subject = get_object_or_404(Subject, id=subject_id)

        # Get selected faculty IDs safely
        faculty_ids = [
            int(key.split('_')[1])
            for key in request.POST
            if key.startswith('faculty_') and key.split('_')[1].isdigit()
        ]
        for faculty_id in faculty_ids:
            faculty = get_object_or_404(Faculty, id=faculty_id)

            assignment, created = FacultyAssignment.objects.update_or_create(
                faculty=faculty.user,  # assign the User object
                defaults={'status': status}
            )
            # Add the subject to the ManyToMany field
            assignment.subjects.add(subject)

        messages.success(request, "Faculty assigned successfully!")
        return redirect('/academic_setup/?tab=faculty')

    return render(request, 'add_faculty.html', {'subjects_qs': subjects_qs, 'faculties': faculties})

# ---------- Add Grading Component ----------
def add_grading(request):
    if request.method == 'POST':
        component = request.POST.get('component')
        weight = request.POST.get('weight', 0)
        status = request.POST.get('status', 'Active')

        GradingComponent.objects.create(
            component=component,
            weight=weight,
            status=status
        )
        messages.success(request, 'Grading Component added successfully!')
        return redirect('/academic_setup/?tab=grading')

    return render(request, 'add_grading.html')

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from .models import SchoolYear, Subject, Section, FacultyAssignment, GradingComponent, User
from .forms import SchoolYearForm, SubjectForm, SectionForm, FacultyAssignmentForm, GradingComponentForm

# ---------- School Year ----------
def edit_school_year(request, pk):
    obj = get_object_or_404(SchoolYear, pk=pk)
    if request.method == 'POST':
        form = SchoolYearForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, "School Year updated!")
            return redirect('/academic_setup/?tab=school_year')
    else:
        form = SchoolYearForm(instance=obj)
    obj = get_object_or_404(SchoolYear, pk=pk)
    years = range(2020, 2031)
    return render(request, 'edit_school_year.html', {'obj': obj, 'years': years})


# ---------- Subject ----------
def edit_subject(request, pk):
    obj = get_object_or_404(Subject, pk=pk)
    if request.method == 'POST':
        form = SubjectForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Subject updated!")
            return redirect('/academic_setup/?tab=subject')
    else:
        form = SubjectForm(instance=obj)
        # Split sections_covered if you want to show each section separately
    return render(request, 'edit_subject.html', {'form': form, 'obj': obj})


# ---------- Section ----------
def edit_section(request, pk):
    obj = get_object_or_404(Section, pk=pk)
    if request.method == 'POST':
        form = SectionForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Section updated!")
            return redirect('/academic_setup/?tab=section')
    else:
        form = SectionForm(instance=obj)
    return render(request, 'edit_section.html', {'form': form, 'obj': obj})


# ---------- Faculty Assignment ----------
def edit_faculty(request, pk):
    obj = get_object_or_404(FacultyAssignment, pk=pk)
    if request.method == 'POST':
        form = FacultyAssignmentForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Faculty assignment updated!")
            return redirect('/academic_setup/?tab=faculty')
    else:
        form = FacultyAssignmentForm(instance=obj)
    return render(request, 'edit_faculty.html', {'form': form, 'obj': obj})


# ---------- Grading Component ----------
def edit_grading(request, pk):
    obj = get_object_or_404(GradingComponent, pk=pk)
    if request.method == 'POST':
        form = GradingComponentForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Grading Component updated!")
            return redirect('/academic_setup/?tab=grading')
    else:
        form = GradingComponentForm(instance=obj)
    return render(request, 'edit_grading.html', {'form': form, 'obj': obj})

# views.py
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from .models import SchoolYear, Subject, Section, FacultyAssignment, GradingComponent

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


def record(request):
    return render(request, 'student_record.html', {'account': StudentRecord.objects.all()})

def view_student(request, id):
    student = StudentRecord.objects.get(pk=id)

    return HttpResponseRedirect(reverse('index'))

from .forms import RecordForm

def add(request):
    if request.method == 'POST':
        form = RecordForm(request.POST)
        if form.is_valid():
            new_student_id = form.cleaned_data['student_id']
            new_fullname = form.cleaned_data['fullname']
            new_grade_and_section = form.cleaned_data['grade_and_section']
            new_gender = form.cleaned_data['gender']
            new_age = form.cleaned_data['age']
            new_address = form.cleaned_data['address']
            new_parent = form.cleaned_data['parent']
            new_parent_contact = form.cleaned_data['parent_contact']
            new_status = form.cleaned_data['status']

            new_student = StudentRecord(
                student_id = new_student_id,
                fullname = new_fullname,
                grade_and_section = new_grade_and_section,
                gender = new_gender,
                age = new_age,
                address = new_address,
                parent = new_parent,
                parent_contact = new_parent_contact,
                status = new_status,
            )

            new_student.save()
            return render(request, 'add.html',{
                'form': RecordForm(),
                'success': True
            })

    else:
        form = RecordForm()
    return render(request, 'add.html', {
        'form': RecordForm()
    })

def edit(request, id):
    if request.method == "POST":
        student = StudentRecord.objects.get(pk=id)
        form = RecordForm(request.POST, instance=student)
        if form.is_valid():
            form.save()
            return render(request, 'edit.html',{
                'form':form,
                'success': True
            })
    else:
        student = StudentRecord.objects.get(pk=id)
        form = RecordForm(instance=student)
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
        except Exception as e:
            messages.error(request, f'Something went wrong: {str(e)}')
        return redirect('assign_subject')

    context = {
        'grades': grades,
        'subjects': subjects,
        'status_choices': status_choices
    }
    return render(request, 'assign.html', context)



from .models import AssignedSubject

def assign_subject(request):
    assigned_subjects = AssignedSubject.objects.all()

    context = {
        'assigned_subjects': assigned_subjects
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
            return redirect('assign_subject')
        except Exception as e:
            messages.error(request, f'Something went wrong: {str(e)}')

    context = {
        'assigned': assigned,
        'grades': grades,
        'subjects': subjects,
        'status_choices': status_choices
    }
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
    return render(request, 'quiz.html', {'tab': 'quiz'})

def exam(request):
    return render(request, 'exam.html', {'tab': 'exam'})

def project(request):
    return render(request, 'project.html', {'tab': 'project'})

def attendance(request):
    return render(request, 'attendance.html', {'tab': 'attendance'})

from .models import Student, Score

from .models import Student

from .models import StudentRecord, Score
from .models import StudentRecord

from django.shortcuts import render
from .models import StudentRecord

def score(request):
    students = StudentRecord.objects.all().order_by('-id')  # get all students
    return render(request, 'score.html', {
        'students': students,
        'tab': 'score'
    })




