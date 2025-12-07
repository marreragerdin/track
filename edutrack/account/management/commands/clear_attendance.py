from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from account.models import WeeklyAttendanceSession, WeeklyAttendanceRecord, Subject

class Command(BaseCommand):
    help = 'Clear attendance data. Use --orphan to remove sessions with no records, --all to delete all sessions and records, or --subject <id> to target one subject. Must pass --yes to perform deletion.'

    def add_arguments(self, parser):
        parser.add_argument('--orphan', action='store_true', help='Delete WeeklyAttendanceSession objects that have no attendance records')
        parser.add_argument('--all', action='store_true', help='Delete ALL WeeklyAttendanceSession and WeeklyAttendanceRecord objects')
        parser.add_argument('--subject', type=int, help='Subject ID to target (deletes sessions/records for that subject)')
        parser.add_argument('--week', type=int, help='Week number to target (only used with --subject)')
        parser.add_argument('--yes', action='store_true', help='Confirm and execute deletions')

    def handle(self, *args, **options):
        orphan = options.get('orphan')
        delete_all = options.get('all')
        subject_id = options.get('subject')
        week = options.get('week')
        confirm = options.get('yes')

        if not (orphan or delete_all or subject_id):
            raise CommandError('Specify --orphan or --all or --subject <id> (use --help for details)')

        if delete_all and orphan:
            raise CommandError('Use either --all or --orphan, not both')

        # Build queryset(s) to delete
        sessions_qs = WeeklyAttendanceSession.objects.all()
        records_qs = WeeklyAttendanceRecord.objects.all()

        if subject_id:
            try:
                subject = Subject.objects.get(id=subject_id)
            except Subject.DoesNotExist:
                raise CommandError(f'Subject with id={subject_id} does not exist')
            sessions_qs = sessions_qs.filter(subject=subject)
            records_qs = records_qs.filter(session__subject=subject)
            if week:
                sessions_qs = sessions_qs.filter(week_number=week)
                records_qs = records_qs.filter(session__week_number=week)

        if orphan:
            # Sessions with zero records
            sessions_qs = sessions_qs.annotate(_count=models.Count('attendance_records')).filter(_count=0)
            sessions_count = sessions_qs.count()
            self.stdout.write(self.style.WARNING(f'Orphan sessions found: {sessions_count}'))
            if sessions_count == 0:
                self.stdout.write('Nothing to delete.')
                return
            if not confirm:
                self.stdout.write(self.style.NOTICE('Run with --yes to actually delete these orphan sessions.'))
                return
            with transaction.atomic():
                deleted, _ = sessions_qs.delete()
            self.stdout.write(self.style.SUCCESS(f'Deleted {sessions_count} orphan WeeklyAttendanceSession objects (cascade deleted {deleted} total objects).'))
            return

        if delete_all:
            sessions_count = sessions_qs.count()
            records_count = records_qs.count()
            self.stdout.write(self.style.WARNING(f'About to delete ALL attendance data: {sessions_count} sessions and {records_count} records'))
            if not confirm:
                self.stdout.write(self.style.NOTICE('Run with --yes to actually delete all attendance sessions and records.'))
                return
            with transaction.atomic():
                # Delete records first for clarity, though cascade would handle this
                rec_deleted, _ = records_qs.delete()
                sess_deleted, _ = sessions_qs.delete()
            self.stdout.write(self.style.SUCCESS(f'Deleted {sessions_count} WeeklyAttendanceSession and {records_count} WeeklyAttendanceRecord objects (cascade may have removed additional objects).'))
            return

        if subject_id:
            sessions_count = sessions_qs.count()
            records_count = records_qs.count()
            self.stdout.write(self.style.WARNING(f'About to delete attendance for Subject id={subject_id}: {sessions_count} sessions and {records_count} records'))
            if not confirm:
                self.stdout.write(self.style.NOTICE('Run with --yes to actually delete these sessions and records.'))
                return
            with transaction.atomic():
                rec_deleted, _ = records_qs.delete()
                sess_deleted, _ = sessions_qs.delete()
            self.stdout.write(self.style.SUCCESS(f'Deleted {sessions_count} sessions and {records_count} records for Subject id={subject_id}.'))
            return
