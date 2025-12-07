# Generated migration to add adviser as ForeignKey with proper data migration

from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


def migrate_adviser_data(apps, schema_editor):
    """
    Migrate adviser string names to User ForeignKey.
    This will set adviser to NULL for names that don't match any User.
    """
    Section = apps.get_model('account', 'Section')
    User = apps.get_model('account', 'User')
    
    for section in Section.objects.all():
        if section.adviser_old:
            # Try to find a user by first_name + last_name combination
            adviser_name = section.adviser_old.strip()
            # Try exact match on full name
            try:
                user = User.objects.get(
                    models.Q(first_name__iexact=adviser_name.split()[0]) &
                    models.Q(last_name__iexact=' '.join(adviser_name.split()[1:]))
                )
                section.adviser = user
                section.save(update_fields=['adviser'])
            except User.DoesNotExist:
                # If no match found, leave adviser as NULL
                section.adviser = None
                section.save(update_fields=['adviser'])


def reverse_migrate(apps, schema_editor):
    """Reverse: copy ForeignKey back to CharField"""
    Section = apps.get_model('account', 'Section')
    
    for section in Section.objects.all():
        if section.adviser:
            section.adviser_old = f"{section.adviser.first_name} {section.adviser.last_name}"
            section.save(update_fields=['adviser_old'])


class Migration(migrations.Migration):

    dependencies = [
        ('account', '0025_studentrecord_account_username'),
    ]

    operations = [
        # Step 1: Add the new ForeignKey field as nullable
        migrations.AddField(
            model_name='section',
            name='adviser',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='advised_sections', to=settings.AUTH_USER_MODEL),
        ),
        # Step 2: Rename old adviser to adviser_old
        migrations.RenameField(
            model_name='section',
            old_name='adviser',
            new_name='adviser_old',
        ),
        # Step 3: Run the data migration
        migrations.RunPython(migrate_adviser_data, reverse_migrate),
    ]
