from django.db import models
from django.contrib.auth.models import User


class Direction(models.Model):
    """
    Направление помощи. Например: 'Помощь приютам животных',
    'Помощь бездомным', 'Экологический десант'.
    Сайт поддерживает несколько направлений — это ключевое требование ТЗ.
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
    """
    Благополучатель: приют для животных или иная организация,
    которой помогает проект. Привязан к направлению.
    """
    direction = models.ForeignKey(
        Direction,
        on_delete=models.CASCADE,
        related_name='shelters',
        verbose_name='Направление'
    )
    name = models.CharField('Название', max_length=200)
    address = models.CharField('Адрес', max_length=300, blank=True)
    lat = models.FloatField('Широта', null=True, blank=True)
    lng = models.FloatField('Долгота', null=True, blank=True)
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
    """
    Рейс — конкретный выезд волонтёров/перевозчиков к приюту.
    Это единица координации: волонтёр записывается на рейс,
    координатор видит, кто едет, сколько мест осталось.
    """
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
        Direction,
        on_delete=models.CASCADE,
        related_name='trips',
        verbose_name='Направление'
    )
    shelter = models.ForeignKey(
        Shelter,
        on_delete=models.CASCADE,
        related_name='trips',
        verbose_name='Приют'
    )
    title = models.CharField('Название рейса', max_length=200)
    date = models.DateTimeField('Дата и время')
    seats_total = models.PositiveIntegerField('Всего мест', default=5)
    status = models.CharField(
        'Статус',
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PLANNED
    )
    description = models.TextField('Описание', blank=True)
    created_at = models.DateTimeField('Создан', auto_now_add=True)

    class Meta:
        verbose_name = 'Рейс'
        verbose_name_plural = 'Рейсы'
        ordering = ['date']

    def seats_taken(self):
        """Сколько мест уже занято (по числу записей)."""
        return self.enrollments.count()

    def seats_left(self):
        """Сколько мест осталось. Не уходит в минус."""
        return max(0, self.seats_total - self.seats_taken())

    def is_open(self):
        """Можно ли ещё записаться."""
        return self.status == self.STATUS_OPEN and self.seats_left() > 0

    def __str__(self):
        return f'{self.title} — {self.date:%d.%m.%Y %H:%M}'


class Enrollment(models.Model):
    """
    Запись волонтёра на рейс. Один пользователь — одна запись на рейс
    (защита от дублей через unique_together). Часы заполняет координатор
    после выполнения рейса — из них складывается учёт часов волонтёра.
    """
    trip = models.ForeignKey(
        Trip,
        on_delete=models.CASCADE,
        related_name='enrollments',
        verbose_name='Рейс'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='enrollments',
        verbose_name='Волонтёр'
    )
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
    """Заявка на регистрацию приюта с сайта."""
    STATUS_NEW = 'new'
    STATUS_APPROVED = 'approved'
    STATUS_REJECTED = 'rejected'
    STATUS_CHOICES = [
        (STATUS_NEW, 'Новая'),
        (STATUS_APPROVED, 'Одобрена'),
        (STATUS_REJECTED, 'Отклонена'),
    ]

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
    created_at = models.DateTimeField('Создано', auto_now_add=True)

    class Meta:
        verbose_name = 'Заявка приюта'
        verbose_name_plural = 'Заявки приютов'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.name} ({self.get_status_display()})'


class Review(models.Model):
    """Отзыв волонтёра, приюта, перевозчика или жертвователя."""
    ROLE_VOLUNTEER = 'volunteer'
    ROLE_SHELTER = 'shelter'
    ROLE_CARRIER = 'carrier'
    ROLE_DONOR = 'donor'
    ROLE_CHOICES = [
        (ROLE_VOLUNTEER, 'Волонтёр'),
        (ROLE_SHELTER, 'Приют'),
        (ROLE_CARRIER, 'Перевозчик'),
        (ROLE_DONOR, 'Жертвователь'),
    ]

    name = models.CharField('Имя', max_length=150)
    role = models.CharField('Роль', max_length=20, choices=ROLE_CHOICES)
    text = models.TextField('Текст отзыва')
    rating = models.PositiveSmallIntegerField('Оценка (1–5)', default=5)
    is_published = models.BooleanField('Опубликован', default=False)
    created_at = models.DateTimeField('Создано', auto_now_add=True)

    class Meta:
        verbose_name = 'Отзыв'
        verbose_name_plural = 'Отзывы'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.name} ({self.get_role_display()}) — {self.rating}'


class ContactMessage(models.Model):
    """Вопрос из FAQ / обратная связь."""
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
