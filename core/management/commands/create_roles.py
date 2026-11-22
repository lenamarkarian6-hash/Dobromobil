from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group

from core.models import Profile

OLD_ROLES = ['Жертвователь', 'Координатор']


class Command(BaseCommand):
    help = 'Создаёт 4 роли сайта: Амбассадор, Организатор, Фандрайзер, Волонтёр'

    def handle(self, *args, **options):
        for _, role in Profile.ROLE_CHOICES:
            _, created = Group.objects.get_or_create(name=role)
            self.stdout.write(self.style.SUCCESS(f'Создана роль: {role}') if created else f'Роль уже есть: {role}')

        removed, _ = Group.objects.filter(name__in=OLD_ROLES).delete()
        if removed:
            self.stdout.write(f'Удалены старые роли: {", ".join(OLD_ROLES)}')
        self.stdout.write('Управление сайтом выполняет администратор (createsuperuser) через /admin/.')
