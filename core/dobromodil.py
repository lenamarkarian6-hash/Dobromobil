from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login
from django.contrib import messages
from .models import Direction, Shelter, Trip, Enrollment
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login
from django.contrib.auth.forms import UserCreationForm
from django.contrib import messages

from .models import (
    Direction, Shelter, Trip, Enrollment,
    ShelterApplication, Review, ContactMessage
)

def home(request):
    directions = Direction.objects.filter(is_active=True)
    return render(request, 'core/home.html', {'directions': directions})


def direction_detail(request, slug):
    direction = get_object_or_404(Direction, slug=slug, is_active=True)
    shelters = direction.shelters.all()
    trips = direction.trips.exclude(status='done')
    return render(request, 'core/direction_detail.html', {
        'direction': direction,
        'shelters': shelters,
        'trips': trips,
    })


def map_view(request):
    shelters = Shelter.objects.exclude(lat__isnull=True).exclude(lng__isnull=True)
    return render(request, 'core/map.html', {'shelters': shelters})


def trip_detail(request, trip_id):
    trip = get_object_or_404(Trip, id=trip_id)
    return render(request, 'core/trip_detail.html', {'trip': trip})


@login_required
def enroll(request, trip_id):
    trip = get_object_or_404(Trip, id=trip_id)
    if trip.seats_left() <= 0:
        messages.error(request, 'Мест нет')
    elif Enrollment.objects.filter(trip=trip, user=request.user).exists():
        messages.warning(request, 'Вы уже записаны')
    else:
        Enrollment.objects.create(trip=trip, user=request.user)
        messages.success(request, 'Вы записались на рейс')
    return redirect('trip_detail', trip_id=trip.id)


def register(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, 'Регистрация успешна!')
            return redirect('home')
    else:
        form = UserCreationForm()
    return render(request, 'core/register.html', {'form': form})


@login_required
def cabinet(request):
    enrollments = request.user.enrollments.select_related('trip', 'trip__shelter').all()
    total_hours = sum(e.hours for e in enrollments)
    return render(request, 'core/cabinet.html', {
        'enrollments': enrollments,
        'total_hours': total_hours,
    })


def reports(request):
    directions = Direction.objects.filter(is_active=True)
    data = []
    for d in directions:
        data.append({
            'direction': d,
            'shelters': d.shelters.count(),
            'trips': d.trips.count(),
            'done_trips': d.trips.filter(status='done').count(),
            'volunteers': Enrollment.objects.filter(trip__direction=d).values('user').distinct().count(),
        })
    return render(request, 'core/reports.html', {'data': data})


# ========== Страницы контента (Полина) ==========

def about(request):
    """Страница «О нас»."""
    return render(request, 'core/about.html')


def guide(request):
    """Путеводитель: как стать волонтёром (6 шагов)."""
    return render(request, 'core/guide.html')


def shelter_rules(request):
    """Правила поведения в приюте."""
    return render(request, 'core/shelter_rules.html')


def donations(request):
    """Страница пожертвований."""
    return render(request, 'core/donations.html')


def shelter_register(request):
    """
    Регистрация приюта.
    GET  — показать форму
    POST — сохранить заявку и показать сообщение об успехе
    """
    if request.method == 'POST':
        ShelterApplication.objects.create(
            name=request.POST.get('name', '').strip(),
            address=request.POST.get('address', '').strip(),
            lat=request.POST.get('lat') or None,
            lng=request.POST.get('lng') or None,
            contact_name=request.POST.get('contact_name', '').strip(),
            contact_phone=request.POST.get('contact_phone', '').strip(),
            contact_email=request.POST.get('contact_email', '').strip(),
            description=request.POST.get('description', '').strip(),
            needs=request.POST.get('needs', '').strip(),
            legal_info=request.POST.get('legal_info', '').strip(),
        )
        messages.success(
            request,
            'Заявка отправлена! Мы свяжемся с вами в течение 3 рабочих дней.'
        )
        return redirect('shelter_register')

    return render(request, 'core/shelter_register.html')


def faq(request):
    """
    FAQ + форма вопроса.
    GET  — показать страницу
    POST — сохранить вопрос
    """
    if request.method == 'POST':
        ContactMessage.objects.create(
            name=request.POST.get('name', '').strip(),
            email=request.POST.get('email', '').strip(),
            subject=request.POST.get('subject', '').strip(),
            message=request.POST.get('message', '').strip(),
        )
        messages.success(
            request,
            'Вопрос отправлен! Ответим в течение 2 рабочих дней.'
        )
        return redirect('faq')

    return render(request, 'core/faq.html')


def reviews(request):
    """
    Отзывы + форма добавления отзыва.
    GET  — список опубликованных отзывов + форма
    POST — сохранить отзыв (на модерацию)
    """
    if request.method == 'POST':
        rating = request.POST.get('rating', 5)
        try:
            rating = int(rating)
            if rating < 1 or rating > 5:
                rating = 5
        except (TypeError, ValueError):
            rating = 5

        Review.objects.create(
            name=request.POST.get('name', '').strip(),
            role=request.POST.get('role', Review.ROLE_VOLUNTEER),
            text=request.POST.get('text', '').strip(),
            rating=rating,
            is_published=False,  # сначала модерация
        )
        messages.success(
            request,
            'Спасибо за отзыв! Он появится на сайте после проверки.'
        )
        return redirect('reviews')

    reviews_list = Review.objects.filter(is_published=True).order_by('-created_at')[:30]
    return render(request, 'core/reviews.html', {
        'reviews': reviews_list,
    })