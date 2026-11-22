import datetime

from django.db import migrations

ROLES = ['Амбассадор', 'Организатор', 'Фандрайзер', 'Волонтёр']
OLD_ROLES = ['Жертвователь', 'Координатор']

REVIEWS = [
    ('Анна', 'volunteer', 'Первый раз поехала с «Добромобилем» в приют. Координатор всё объяснил, работа '
     'нашлась для всех. Уехала с чувством, что сделала что-то важное. Через неделю записалась снова.'),
    ('Ирина — приют «Добрые руки»', 'organizer', 'Мы приют небольшой, и каждая машина с кормом — праздник. '
     'Через сайт заявку рассмотрели за два дня, рейс приехал через неделю. Спасибо, что не забываете про нас.'),
    ('Сергей', 'volunteer', 'Удобно, что видно рейсы, где нужна помощь. Записался, отвёз корм, отметил '
     'выполнение — всё в личном кабинете.'),
]


def forwards(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Direction = apps.get_model('core', 'Direction')
    MonthlyReport = apps.get_model('core', 'MonthlyReport')
    Review = apps.get_model('core', 'Review')

    for name in ROLES:
        Group.objects.get_or_create(name=name)
    Group.objects.filter(name__in=OLD_ROLES).delete()

    Direction.objects.get_or_create(
        slug='shelters',
        defaults={'name': 'Помощь приютам животных',
                  'description': 'Рейсы в приюты, сбор кормов, медикаментов и тёплых вещей.'},
    )

    MonthlyReport.objects.get_or_create(
        period='Октябрь 2026',
        defaults={'period_start': datetime.date(2026, 10, 1), 'trips': 8, 'shelters': 5, 'volunteers': 34,
                  'collected': 120000, 'spent': 118500},
    )

    if not Review.objects.exists():
        for name, role, text in REVIEWS:
            Review.objects.create(name=name, role=role, text=text, rating=5, is_published=True)


class Migration(migrations.Migration):
    dependencies = [
        ('auth', '0012_alter_user_first_name_max_length'),
        ('core', '0003_roles_donations_reports'),
    ]

    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
