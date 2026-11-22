from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.models import User

from .models import Profile, Review, Donation, Campaign, Trip, Shelter, ContactMessage, PURPOSE_CHOICES

MAX_PHOTO_SIZE = 5 * 1024 * 1024  # 5 МБ


def check_photo_size(f):
    if f and f.size > MAX_PHOTO_SIZE:
        raise forms.ValidationError('Файл слишком большой: максимум 5 МБ.')
    return f


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleImageField(forms.ImageField):
    """Поле для загрузки нескольких фото сразу."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('widget', MultipleFileInput(attrs={'accept': 'image/*'}))
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single = super().clean
        if isinstance(data, (list, tuple)):
            return [check_photo_size(single(d, initial)) for d in data if d]
        return [check_photo_size(single(data, initial))] if data else []


class RegisterForm(UserCreationForm):
    """
    Регистрация для всех 4 ролей. Блок «Приют» обязателен только для организатора:
    у волонтёра, амбассадора и фандрайзера описание приюта и потребности не требуются.
    """
    role = forms.ChoiceField(label='Кем вы хотите быть в проекте', choices=Profile.ROLE_CHOICES,
                             widget=forms.RadioSelect, initial=Profile.ROLE_VOLUNTEER)
    first_name = forms.CharField(label='Имя и фамилия', max_length=150)
    email = forms.EmailField(label='Электронная почта')
    phone = forms.CharField(label='Телефон', max_length=50)
    city = forms.CharField(label='Город', max_length=100, required=False)
    about = forms.CharField(label='О себе', required=False,
                            widget=forms.Textarea(attrs={'rows': 3,
                                                         'placeholder': 'Опыт, чем хотите помочь (необязательно)'}))
    ref = forms.CharField(required=False, widget=forms.HiddenInput)

    # --- Данные приюта (обязательны только для организатора) ---
    shelter_name = forms.CharField(label='Название приюта', max_length=200, required=False)
    shelter_address = forms.CharField(label='Фактический адрес приюта', max_length=300, required=False,
                                      widget=forms.TextInput(attrs={'placeholder': 'Город, улица, дом'}))
    shelter_lat = forms.FloatField(label='Широта', required=False,
                                   widget=forms.NumberInput(attrs={'step': 'any', 'placeholder': 'Например, 61.2540'}))
    shelter_lng = forms.FloatField(label='Долгота', required=False,
                                   widget=forms.NumberInput(attrs={'step': 'any', 'placeholder': 'Например, 73.3962'}))
    position = forms.CharField(label='Ваша должность в приюте', max_length=100, required=False)
    shelter_description = forms.CharField(
        label='Описание приюта', required=False,
        widget=forms.Textarea(attrs={'rows': 4, 'placeholder': 'Сколько животных, чем занимаетесь, как давно работаете...'}))
    shelter_needs = forms.CharField(
        label='Актуальные потребности', required=False,
        widget=forms.Textarea(attrs={'rows': 4, 'placeholder': 'Корма, медикаменты, тёплые вещи, инвентарь...'}))
    inn = forms.CharField(label='ИНН', max_length=12, required=False)
    ogrn = forms.CharField(label='ОГРН', max_length=15, required=False)
    legal_status = forms.CharField(label='Статус НКО', max_length=200, required=False,
                                   widget=forms.TextInput(attrs={'placeholder': 'Укажите статус или напишите, что юрлица нет'}))
    shelter_photos = MultipleImageField(label='Фотографии приюта (до 3 фото)', required=False)

    agree = forms.BooleanField(label='Согласен(на) на обработку персональных данных и размещение данных на сайте')

    ORGANIZER_REQUIRED = ('shelter_name', 'shelter_address', 'shelter_description', 'shelter_needs')

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username',)
        labels = {'username': 'Логин'}

    def clean_email(self):
        email = self.cleaned_data['email'].lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('Пользователь с такой почтой уже зарегистрирован.')
        return email

    def clean_shelter_photos(self):
        photos = self.cleaned_data.get('shelter_photos') or []
        if len(photos) > 3:
            raise forms.ValidationError('Можно загрузить не более 3 фото.')
        return photos

    def clean(self):
        data = super().clean()
        if data.get('role') == Profile.ROLE_ORGANIZER:
            for name in self.ORGANIZER_REQUIRED:
                if not (data.get(name) or '').strip():
                    self.add_error(name, 'Обязательное поле для организатора.')
        return data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.first_name = self.cleaned_data['first_name']
        user.email = self.cleaned_data['email']
        if commit:
            user.save()
        return user


class LoginForm(AuthenticationForm):
    """Вход по логину или по электронной почте."""
    username = forms.CharField(label='Логин или email', max_length=254,
                               widget=forms.TextInput(attrs={'autofocus': True}))

    def clean(self):
        login_value = self.cleaned_data.get('username', '')
        if '@' in login_value:
            user = User.objects.filter(email__iexact=login_value).first()
            if user:
                self.cleaned_data['username'] = user.username
        return super().clean()


class ProfileForm(forms.Form):
    first_name = forms.CharField(label='Имя и фамилия', max_length=150)
    phone = forms.CharField(label='Телефон', max_length=50, required=False)
    city = forms.CharField(label='Город', max_length=100, required=False)
    about = forms.CharField(label='О себе', required=False, widget=forms.Textarea(attrs={'rows': 3}))


class ReviewForm(forms.ModelForm):
    class Meta:
        model = Review
        fields = ('name', 'role', 'rating', 'text', 'photo')
        labels = {'name': 'Ваше имя', 'role': 'Ваша роль', 'rating': 'Ваша оценка',
                  'text': 'Ваш отзыв', 'photo': 'Фото (необязательно)'}
        widgets = {
            'rating': forms.Select(choices=[(5, '5 — Отлично'), (4, '4 — Хорошо'), (3, '3 — Нормально'),
                                            (2, '2 — Плохо'), (1, '1 — Очень плохо')]),
            'text': forms.Textarea(attrs={'rows': 5, 'placeholder': 'Расскажите о своём опыте...'}),
            'photo': forms.ClearableFileInput(attrs={'accept': 'image/*'}),
        }

    def clean_photo(self):
        return check_photo_size(self.cleaned_data.get('photo'))


class DonationForm(forms.ModelForm):
    agree_offer = forms.BooleanField(label='Я принимаю условия публичной оферты и согласен(на) '
                                           'на обработку персональных данных')

    class Meta:
        model = Donation
        fields = ('campaign', 'purpose', 'amount', 'period', 'payment_method',
                  'donor_name', 'email', 'comment', 'is_anonymous')
        labels = {'campaign': 'Сбор (необязательно)', 'purpose': 'На что направить',
                  'amount': 'Сумма пожертвования, ₽', 'period': 'Периодичность',
                  'payment_method': 'Способ оплаты', 'donor_name': 'Ваше имя (необязательно)',
                  'email': 'Email — пришлём подтверждение и реквизиты',
                  'comment': 'Комментарий (необязательно)', 'is_anonymous': 'Не показывать моё имя в отчётах'}
        widgets = {
            'amount': forms.NumberInput(attrs={'min': 10, 'step': 1, 'placeholder': 'Например, 700'}),
            'period': forms.RadioSelect,
            'payment_method': forms.RadioSelect,
            'purpose': forms.Select(choices=PURPOSE_CHOICES),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['campaign'].queryset = Campaign.objects.filter(is_approved=True, is_active=True)
        self.fields['campaign'].empty_label = 'Общий фонд проекта'


class ContactForm(forms.ModelForm):
    class Meta:
        model = ContactMessage
        fields = ('name', 'email', 'subject', 'message')
        labels = {'name': 'Ваше имя', 'email': 'Электронная почта', 'subject': 'Тема обращения',
                  'message': 'Ваше сообщение'}
        widgets = {
            'subject': forms.Select(choices=[('', 'Выберите тему'), ('Волонтёрство', 'Волонтёрство'),
                                             ('Помощь приюту', 'Помощь приюту'), ('Пожертвования', 'Пожертвования'),
                                             ('Сотрудничество', 'Сотрудничество'), ('Другой вопрос', 'Другой вопрос')]),
            'message': forms.Textarea(attrs={'rows': 5, 'placeholder': 'Напишите сообщение...'}),
        }


class CampaignForm(forms.ModelForm):
    class Meta:
        model = Campaign
        fields = ('title', 'description', 'purpose', 'shelter', 'goal', 'deadline')
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'deadline': forms.DateInput(attrs={'type': 'date'}),
            'purpose': forms.Select(choices=PURPOSE_CHOICES),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['shelter'].queryset = Shelter.objects.filter(is_active=True)
        self.fields['shelter'].empty_label = 'Без привязки к приюту'


class TripForm(forms.ModelForm):
    class Meta:
        model = Trip
        fields = ('shelter', 'title', 'date', 'seats_total', 'description')
        widgets = {
            'date': forms.DateTimeInput(attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'),
            'description': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Место сбора, что взять с собой'}),
        }

    def __init__(self, *args, organizer=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['shelter'].queryset = Shelter.objects.filter(organizer=organizer, is_active=True)


class ShelterNeedsForm(forms.ModelForm):
    class Meta:
        model = Shelter
        fields = ('needs',)
        labels = {'needs': 'Актуальные потребности'}
        widgets = {'needs': forms.Textarea(attrs={'rows': 3})}
