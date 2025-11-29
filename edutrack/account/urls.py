from django.urls import path
from django.contrib.auth import views as auth_views
from . import views
from .views import assign

urlpatterns = [
    path('', views.index, name='index'),
    path('login/', views.login_view, name='login_view'),

    # Student & Faculty
    path('student/', views.student, name='student'),
    path('faculty/', views.faculty, name='faculty'),

    # Admin pages (You had duplicates here, I kept the standard 'admin/')
    path('adminpage/', views.admin, name='adminpage'),
    # path('admin/', views.admin, name='admin'), # <--- careful, this might conflict with Django's built-in admin if enabled

    # Password reset
    path('reset_password/', auth_views.PasswordResetView.as_view(template_name='password_reset.html'),
         name='reset_password'),
    path('reset_password_sent/', auth_views.PasswordResetDoneView.as_view(template_name='password_reset_sent.html'),
         name='password_reset_done'),
    path('reset/<uidb64>/<token>/',
         auth_views.PasswordResetConfirmView.as_view(template_name='password_reset_form.html'),
         name='password_reset_confirm'),
    path('reset_password_complete/',
         auth_views.PasswordResetCompleteView.as_view(template_name='password_reset_done.html'),
         name='reset_password_complete'),

    # User management
    path('manage_user/', views.manage_user, name='manage_user'),
    path('add_user/<str:role>/', views.add_user, name='add_user'),
    path('edit_user/<str:user_type>/<int:pk>/', views.edit_user, name='edit_user'),
    path('delete_user/<str:user_type>/<int:pk>/', views.delete_user, name='delete_user'),

    # Academic Setup
    path('academic_setup/', views.academic_setup, name='academic_setup'),


    path('academic/school-year/add/', views.add_school_year, name='add_school_year'),
    path('academic/subject/add/', views.add_subject, name='add_subject'),
    path('academic/section/add/', views.add_section, name='add_section'),
    path('academic/faculty/add/', views.add_faculty, name='add_faculty'),
    path('academic/grading/add/', views.add_grading, name='add_grading'),

path('academic_setup/school_year/edit/<int:pk>/', views.edit_school_year, name='edit_school_year'),
path('academic_setup/school_year/delete/<int:pk>/', views.delete_school_year, name='delete_school_year'),

path('academic_setup/subject/edit/<int:pk>/', views.edit_subject, name='edit_subject'),
path('academic_setup/subject/delete/<int:pk>/', views.delete_subject, name='delete_subject'),

path('academic_setup/section/edit/<int:pk>/', views.edit_section, name='edit_section'),
path('academic_setup/section/delete/<int:pk>/', views.delete_section, name='delete_section'),

path('academic_setup/faculty/edit/<int:pk>/', views.edit_faculty, name='edit_faculty'),
path('academic_setup/faculty/delete/<int:pk>/', views.delete_faculty, name='delete_faculty'),

path('academic_setup/grading/edit/<int:pk>/', views.edit_grading, name='edit_grading'),
path('academic_setup/grading/delete/<int:pk>/', views.delete_grading, name='delete_grading'),

    path('edit_student/<int:student_id>/', views.edit_student, name='edit_student'),
    path('edit_faculties/<int:faculty_id>/', views.edit_faculties, name='edit_faculties'),
    path('edit_admin/<int:admin_id>/', views.edit_admin, name='edit_admin'),
    path('delete_student/<int:student_id>/', views.delete_student, name='delete_student'),
    path('delete_faculty/<int:faculty_id>/', views.delete_faculty, name='delete_faculty'),
    path('delete_admin/<int:admin_id>/', views.delete_admin, name='delete_admin'),

    path('student_record/', views.record, name='student_record'),

    path('view_student/<int:id>/', views.view_student, name='view_student'),
    path('add/', views.add, name='add'),
    path('edit/<int:id>', views.edit, name='edit'),
    path('delete/<int:id>/', views.delete, name='delete'),

    path('assign_subject/', views.assign_subject, name='assign_subject'),
    path('assign/', assign, name='assign'),
    path('assign_subject/edit/<int:pk>/', views.edit_assigned_subject, name='edit_assign'),
    path('assign_subject/delete/<int:pk>/', views.delete_assigned_subject, name='delete_assigned_subject'),
    path('score/', views.score, name='score'),

    path('quiz/', views.quiz, name='quiz'),
    path('exam/', views.exam, name='exam'),
    path('project/', views.project, name='project'),
    path('attendance/', views.attendance, name='attendance'),



]