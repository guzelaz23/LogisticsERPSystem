from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Migrate to 2-role system: OPERATOR and MANAGEMENT'

    def handle(self, *args, **options):
        operator_group, created = Group.objects.get_or_create(name='OPERATOR')
        if created:
            self.stdout.write(self.style.SUCCESS('Created group: OPERATOR'))
        else:
            self.stdout.write('Group OPERATOR already exists')

        for old_name in ['SALES_OPS', 'FINANCE']:
            try:
                old_group = Group.objects.get(name=old_name)
                for user in old_group.user_set.all():
                    user.groups.add(operator_group)
                    user.groups.remove(old_group)
                    self.stdout.write(f'  Moved {user.username}: {old_name} -> OPERATOR')
                old_group.delete()
                self.stdout.write(self.style.SUCCESS(f'Deleted group: {old_name}'))
            except Group.DoesNotExist:
                self.stdout.write(f'Group {old_name} not found (skipped)')

        self.stdout.write(self.style.SUCCESS('Done. Active groups: OPERATOR, MANAGEMENT'))
