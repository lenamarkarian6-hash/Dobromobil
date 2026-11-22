import secrets
import uuid

from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.db.models import Sum


# ========== Пользователи и роли ==========

class Profile(models.Model):
    """
    Профиль пользователя сайта. На сайте ровно 4 роли:
    амбассадор, организатор, фандрайзер, волонтёр.
    У каждой роли — свой личный кабинет.
    """
    ROLE_AMBASSADOR = 'ambassador'
    ROLE_ORGANIZER = 'organizer'
    ROLE_FUNDRAISER = 'fundraiser'
    ROLE_VOLUNTEER = 'volunteer'

    ROLE_CHOICES = [
        (ROLE_AMBASSADOR, 'Амбассадор'),
        (ROLE_ORGANIZER, 'Организатор'),
        (ROLE_FUNDRAISER, 'Фандрайзер'),
        (ROLE_VOLUNTEER, 'Волонтёр'),
    ]

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name='profile', verbose_name='Пользователь'
    )
    role = models.CharField('Роль', max_length=20, choices=ROLE_CHOICES, default=ROLE_VOLUNTEER)
    phone = models.CharField('Телефон', max_length=50, blank=True)
    city = models.CharField('Город', max_length=100, blank=True)
    about = models.TextField('О себе', blank=True)
    ref_code = models.CharField('Код приглашения', max_length=20, unique=True, blank=True)
    referred_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='invited_profiles', verbose_name='Пригласил (амбассадор)'
    )
    created_at = models.DateTimeField('Создан', auto_now_add=True)

    class Meta:
        verbose_name = 'Профиль'
        verbose_name_plural = 'Профили'

    def save(self, *args, **kwargs):
        if not self.ref_code:
            code = secrets.token_hex(4)
            while Profile.objects.filter(ref_code=code).exists():
                code = secrets.token_hex(4)
            self.ref_code = code
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.user.get_full_name() or self.user.username} ({self.get_role_display()})'


# ========== Направления, приюты, рейсы ==========

class Direction(models.Model):
    """
    Направление помощи. Например: 'Помощь приютам животных'.
    Сайт поддерживает несколько направлений.
    """
    name = models.CharField('Название', max_length=200)
    slug = models.SlugField('Слаг для URL', unique=True)
    description = models.TextField('Описание', blank=True)
    is_active = models.BooleanField('Активно', default=True)
    created_at = models.DateTimeField('Создано', auto_now_add=True)

    class Meta:
        verbose_name = 'Направление'
        verbose_name_plural = 'Направления'
        ordering = ['name']

    def __str__(self):
        return self.name


class Shelter(models.Model):
    """Приют, которому помогает проект. Появляется на карте."""
    direction = models.ForeignKey(
        Direction, on_delete=models.CASCADE, related_name='shelters', verbose_name='Направление'
    )
    organizer = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='shelters', verbose_name='Организатор'
    )
    name = models.CharField('Название', max_length=200)
    address = models.CharField('Адрес', max_length=300, blank=True)
    lat = models.FloatField('Широта', null=True, blank=True)
    lng = models.FloatField('Долгота', null=True, blank=True)
    description = models.TextField('Описание', blank=True)
    needs = models.TextField('Потребности', blank=True)
    contact = models.CharField('Контакт', max_length=200, blank=True)
    is_active = models.BooleanField('Активен', default=True)

    class Meta:
        verbose_name = 'Приют'
        verbose_name_plural = 'Приюты'
        ordering = ['name']

    def __str__(self):
        return self.name


class Trip(models.Model):
    """Рейс — конкретный выезд волонтёров к приюту."""
    STATUS_PLANNED = 'planned'
    STATUS_OPEN = 'open'
    STATUS_FULL = 'full'
    STATUS_DONE = 'done'
    STATUS_CANCELLED = 'cancelled'

    STATUS_CHOICES = [
        (STATUS_PLANNED, 'Запланирован'),
        (STATUS_OPEN, 'Набор волонтёров'),
        (STATUS_FULL, 'Набран'),
        (STATUS_DONE, 'Выполнен'),
        (STATUS_CANCELLED, 'Отменён'),
    ]

    direction = models.ForeignKey(
        Direction, on_delete=models.CASCADE, related_name='trips', verbose_name='Направление'
    )
    shelter = models.ForeignKey(
        Shelter, on_delete=models.CASCADE, related_name='trips', verbose_name='Приют'
    )
    title = models.CharField('Название рейса', max_length=200)
    date = models.DateTimeField('Дата и время')
    seats_total = models.PositiveIntegerField('Всего мест', default=5)
    status = models.CharField('Статус', max_length=20, choices=STATUS_CHOICES, default=STATUS_OPEN)
    description = models.TextField('Описание', blank=True)
    created_at = models.DateTimeField('Создан', auto_now_add=True)

    class Meta:
        verbose_name = 'Рейс'
        verbose_name_plural = 'Рейсы'
        ordering = ['date']

    def seats_taken(self):
        return self.enrollments.count()

    def seats_left(self):
        return max(0, self.seats_total - self.seats_taken())

    def is_open(self):
        return self.status == self.STATUS_OPEN and self.seats_left() > 0

    def __str__(self):
        return f'{self.title} — {self.date:%d.%m.%Y %H:%M}'


class Enrollment(models.Model):
    """Запись волонтёра на рейс. Часы проставляет организатор после рейса."""
    trip = models.ForeignKey(Trip, on_delete=models.CASCADE, related_name='enrollments', verbose_name='Рейс')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='enrollments', verbose_name='Волонтёр')
    created_at = models.DateTimeField('Записался', auto_now_add=True)
    hours = models.PositiveIntegerField('Часы', default=0)
    is_attended = models.BooleanField('Посетил рейс', default=False)

    class Meta:
        verbose_name = 'Запись на рейс'
        verbose_name_plural = 'Записи на рейсы'
        unique_together = ('trip', 'user')
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.user.username} → {self.trip.title}'


class ShelterApplication(models.Model):
    """Заявка организатора на добавление приюта на карту."""
    STATUS_NEW = 'new'
    STATUS_APPROVED = 'approved'
    STATUS_REJECTED = 'rejected'
    STATUS_CHOICES = [
        (STATUS_NEW, 'На рассмотрении'),
        (STATUS_APPROVED, 'Одобрена'),
        (STATUS_REJECTED, 'Отклонена'),
    ]

    user = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='shelter_applications', verbose_name='Организатор'
    )
    name = models.CharField('Название приюта', max_length=200)
    address = models.CharField('Адрес', max_length=300)
    lat = models.FloatField('Широта', null=True, blank=True)
    lng = models.FloatField('Долгота', null=True, blank=True)
    contact_name = models.CharField('Контактное лицо', max_length=150)
    contact_phone = models.CharField('Телефон', max_length=50)
    contact_email = models.EmailField('Email')
    description = models.TextField('Описание приюта', blank=True)
    needs = models.TextField('Актуальные потребности', blank=True)
    legal_info = models.TextField('Юридические данные (ИНН, ОГРН и т.д.)', blank=True)
    status = models.CharField('Статус', max_length=20, choices=STATUS_CHOICES, default=STATUS_NEW)
    shelter = models.OneToOneField(
        Shelter, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='application', verbose_name='Созданный приют'
    )
    created_at = models.DateTimeField('Создано', auto_now_add=True)

    class Meta:
        verbose_name = 'Заявка приюта'
        verbose_name_plural = 'Заявки приютов'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.name} ({self.get_status_display()})'


class ShelterApplicationPhoto(models.Model):
    application = models.ForeignKey(
        ShelterApplication, on_delete=models.CASCADE, related_name='photos', verbose_name='Заявка'
    )
    image = models.ImageField('Фото', upload_to='shelters/%Y/%m/')

    class Meta:
        verbose_name = 'Фото приюта'
        verbose_name_plural = 'Фото приютов'


# ========== Пожертвования ==========

PURPOSE_CHOICES = [
    ('general', 'Туда, где нужнее всего'),
    ('food', 'Корма'),
    ('medicine', 'Медикаменты'),
    ('transport', 'Транспорт'),
    ('equipment', 'Инвентарь'),
]


class Campaign(models.Model):
    """Сбор средств, который ведёт фандрайзер. Публикуется после проверки."""
    owner = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='campaigns', verbose_name='Фандрайзер'
    )
    title = models.CharField('Название сбора', max_length=200)
    description = models.TextField('Описание')
    purpose = models.CharField('Направление помощи', max_length=20, choices=PURPOSE_CHOICES, default='general')
    shelter = models.ForeignKey(
        Shelter, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='campaigns', verbose_name='Приют'
    )
    goal = models.PositiveIntegerField('Цель, ₽', validators=[MinValueValidator(100)])
    deadline = models.DateField('Срок сбора', null=True, blank=True)
    is_approved = models.BooleanField('Одобрен модератором', default=False)
    is_active = models.BooleanField('Сбор идёт', default=True)
    created_at = models.DateTimeField('Создан', auto_now_add=True)

    class Meta:
        verbose_name = 'Сбор'
        verbose_name_plural = 'Сборы'
        ordering = ['-created_at']

    def collected(self):
        return self.donations.filter(status=Donation.STATUS_PAID).aggregate(s=Sum('amount'))['s'] or 0

    def progress(self):
        if not self.goal:
            return 0
        return min(100, round(self.collected() * 100 / self.goal))

    def __str__(self):
        return self.title


class Donation(models.Model):
    """Пожертвование. Статус «оплачено» подтверждает администратор после поступления средств."""
    STATUS_PENDING = 'pending'
    STATUS_PAID = 'paid'
    STATUS_CANCELLED = 'cancelled'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Ожидает оплаты'),
        (STATUS_PAID, 'Оплачено'),
        (STATUS_CANCELLED, 'Отменено'),
    ]

    PERIOD_ONCE = 'once'
    PERIOD_MONTHLY = 'monthly'
    PERIOD_CHOICES = [
        (PERIOD_ONCE, 'Разовое'),
        (PERIOD_MONTHLY, 'Ежемесячное'),
    ]

    PAYMENT_CHOICES = [
        ('sbp', 'Система быстрых платежей (СБП) — по номеру телефона, без комиссии'),
        ('transfer', 'Перевод по реквизитам — с карты любого банка или со счёта организации'),
    ]

    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    user = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='donations', verbose_name='Пользователь'
    )
    campaign = models.ForeignKey(
        Campaign, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='donations', verbose_name='Сбор'
    )
    purpose = models.CharField('Направление помощи', max_length=20, choices=PURPOSE_CHOICES, default='general')
    amount = models.PositiveIntegerField('Сумма, ₽', validators=[MinValueValidator(10), MaxValueValidator(1_000_000)])
    period = models.CharField('Периодичность', max_length=10, choices=PERIOD_CHOICES, default=PERIOD_ONCE)
    payment_method = models.CharField('Способ оплаты', max_length=20, choices=PAYMENT_CHOICES, default='sbp')
    donor_name = models.CharField('Имя', max_length=150, blank=True)
    email = models.EmailField('Email для чека')
    comment = models.CharField('Комментарий', max_length=300, blank=True)
    is_anonymous = models.BooleanField('Анонимно', default=False)
    status = models.CharField('Статус', max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    created_at = models.DateTimeField('Создано', auto_now_add=True)

    class Meta:
        verbose_name = 'Пожертвование'
        verbose_name_plural = 'Пожертвования'
        ordering = ['-created_at']

    @property
    def number(self):
        return f'ДМ-{self.pk:06d}'

    def __str__(self):
        return f'{self.number}: {self.amount} ₽ ({self.get_status_display()})'


# ========== Отзывы и отчёты ==========

class Review(models.Model):
    """Отзыв участника проекта. Публикуется после модерации."""
    name = models.CharField('Имя', max_length=150)
    role = models.CharField('Роль', max_length=20, choices=Profile.ROLE_CHOICES)
    user = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='reviews', verbose_name='Пользователь'
    )
    text = models.TextField('Текст отзыва')
    rating = models.PositiveSmallIntegerField(
        'Оценка (1–5)', default=5, validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    photo = models.ImageField('Фото', upload_to='reviews/%Y/%m/', blank=True)
    is_published = models.BooleanField('Опубликован', default=False)
    created_at = models.DateTimeField('Создано', auto_now_add=True)

    class Meta:
        verbose_name = 'Отзыв'
        verbose_name_plural = 'Отзывы'
        ordering = ['-created_at']

    def stars(self):
        return '⭐' * self.rating

    def __str__(self):
        return f'{self.name} ({self.get_role_display()}) — {self.rating}'


class MonthlyReport(models.Model):
    """Отчёт за период. Заполняется в админке и показывается на вкладке «Отзывы»."""
    period = models.CharField('Период', max_length=50, help_text='Например: «Октябрь 2026»')
    period_start = models.DateField('Начало периода', help_text='Для сортировки')
    trips = models.PositiveIntegerField('Рейсов', default=0)
    shelters = models.PositiveIntegerField('Приютов', default=0)
    volunteers = models.PositiveIntegerField('Волонтёров', default=0)
    collected = models.PositiveIntegerField('Собрано, ₽', default=0)
    spent = models.PositiveIntegerField('Потрачено, ₽', default=0)
    comment = models.TextField('Комментарий', blank=True)
    is_published = models.BooleanField('Опубликован', default=True)

    class Meta:
        verbose_name = 'Отчёт'
        verbose_name_plural = 'Отчёты'
        ordering = ['-period_start']

    def balance(self):
        return self.collected - self.spent

    def __str__(self):
        return self.period


class ContactMessage(models.Model):
    """Вопрос из FAQ / обращение со страницы «О нас»."""
    name = models.CharField('Имя', max_length=150)
    email = models.EmailField('Email')
    subject = models.CharField('Тема', max_length=200, blank=True)
    message = models.TextField('Сообщение')
    is_answered = models.BooleanField('Отвечено', default=False)
    created_at = models.DateTimeField('Создано', auto_now_add=True)

    class Meta:
        verbose_name = 'Сообщение'
        verbose_name_plural = 'Сообщения'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.name}: {self.subject or "без темы"}'
