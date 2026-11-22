from django.contrib import messages
from django.contrib.auth import login, views as auth_views
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group
from django.db import transaction
from django.db.models import Sum, Count, Q
from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import (
    RegisterForm, LoginForm, ProfileForm, ReviewForm, DonationForm, ContactForm,
    CampaignForm, TripForm, ShelterNeedsForm,
)
from .models import (
    Profile, Direction, Shelter, Trip, Enrollment, ShelterApplication, ShelterApplicationPhoto,
    Campaign, Donation, Review, MonthlyReport,
)

# Роли, которые могут записываться на рейсы
TRIP_ROLES = (Profile.ROLE_VOLUNTEER, Profile.ROLE_AMBASSADOR)


def get_role(user):
    profile = getattr(user, 'profile', None) if user.is_authenticated else None
    return profile.role if profile else None


# ========== Публичные страницы ==========

def home(request):
    upcoming = Trip.objects.filter(status=Trip.STATUS_OPEN, date__gte=timezone.now()).select_related('shelter')[:3]
    return render(request, 'core/home.html', {'upcoming': upcoming})


def about(request):
    """«О нас» + контакты + форма обращения."""
    if request.method == 'POST':
        form = ContactForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Спасибо за обращение! Мы ответим в течение 2 рабочих дней.')
            return redirect('/about/#contacts')
    else:
        form = ContactForm()
    return render(request, 'core/about.html', {'form': form})


def guide(request):
    return render(request, 'core/guide.html')


def shelter_rules(request):
    return render(request, 'core/shelter_rules.html')


def faq(request):
    if request.method == 'POST':
        form = ContactForm(request.POST)
        if form.is_valid():
            msg = form.save(commit=False)
            msg.subject = msg.subject or 'Вопрос со страницы FAQ'
            msg.save()
            messages.success(request, 'Вопрос отправлен! Ответим в течение 2 рабочих дней.')
            return redirect('faq')
    else:
        form = ContactForm()
    return render(request, 'core/faq.html', {'form': form})


def map_view(request):
    shelters = Shelter.objects.filter(is_active=True).exclude(lat__isnull=True).exclude(lng__isnull=True)
    now = timezone.now()
    data = []
    for s in shelters:
        trips = s.trips.exclude(status=Trip.STATUS_CANCELLED).order_by('date')
        data.append({
            'name': s.name,
            'address': s.address,
            'lat': s.lat,
            'lng': s.lng,
            'needs': s.needs,
            'trips': [{
                'title': t.title,
                'date': timezone.localtime(t.date).strftime('%Y-%m-%d'),
                'date_display': timezone.localtime(t.date).strftime('%d.%m.%Y %H:%M'),
                'status': t.status,
                'status_display': t.get_status_display(),
                'url': f'/trip/{t.id}/',
                'upcoming': t.date >= now,
            } for t in trips],
        })
    return render(request, 'core/map.html', {'shelters_data': data})


def direction_detail(request, slug):
    direction = get_object_or_404(Direction, slug=slug, is_active=True)
    return render(request, 'core/direction_detail.html', {
        'direction': direction,
        'shelters': direction.shelters.filter(is_active=True),
        'trips': direction.trips.exclude(status__in=[Trip.STATUS_DONE, Trip.STATUS_CANCELLED]),
    })


def trip_detail(request, trip_id):
    trip = get_object_or_404(Trip.objects.select_related('shelter'), id=trip_id)
    enrolled = request.user.is_authenticated and trip.enrollments.filter(user=request.user).exists()
    return render(request, 'core/trip_detail.html', {
        'trip': trip,
        'enrolled': enrolled,
        'can_enroll': get_role(request.user) in TRIP_ROLES,
    })


@login_required
@require_POST
def enroll(request, trip_id):
    trip = get_object_or_404(Trip, id=trip_id)
    if get_role(request.user) not in TRIP_ROLES:
        messages.error(request, 'Записываться на рейсы могут волонтёры и амбассадоры.')
    elif not trip.is_open():
        messages.error(request, 'Запись на этот рейс закрыта или мест нет.')
    elif Enrollment.objects.filter(trip=trip, user=request.user).exists():
        messages.warning(request, 'Вы уже записаны на этот рейс.')
    else:
        Enrollment.objects.create(trip=trip, user=request.user)
        messages.success(request, 'Вы записались на рейс! Координатор свяжется с вами за 1–2 дня.')
    return redirect('trip_detail', trip_id=trip.id)


@login_required
@require_POST
def cancel_enrollment(request, trip_id):
    deleted, _ = Enrollment.objects.filter(
        trip_id=trip_id, user=request.user, trip__date__gt=timezone.now()
    ).delete()
    if deleted:
        messages.success(request, 'Запись на рейс отменена.')
    else:
        messages.error(request, 'Отменить запись нельзя: рейс уже прошёл или вы не были записаны.')
    return redirect(request.POST.get('next') or 'cabinet')


# ========== Отзывы + отчёты ==========

def reviews(request):
    if request.method == 'POST':
        form = ReviewForm(request.POST, request.FILES)
        if form.is_valid():
            review = form.save(commit=False)
            review.user = request.user if request.user.is_authenticated else None
            review.is_published = False  # сначала модерация
            review.save()
            messages.success(request, 'Спасибо за отзыв! Он появится на сайте после проверки модератором.')
            return redirect('/reviews/#leave-review')
    else:
        initial = {}
        if request.user.is_authenticated:
            initial['name'] = request.user.first_name or request.user.username
            if get_role(request.user):
                initial['role'] = get_role(request.user)
        form = ReviewForm(initial=initial)

    reports_list = MonthlyReport.objects.filter(is_published=True)
    return render(request, 'core/reviews.html', {
        'reviews': Review.objects.filter(is_published=True)[:30],
        'form': form,
        'latest_report': reports_list.first(),
        'reports': reports_list,
        'photos': Review.objects.filter(is_published=True).exclude(photo='')[:8],
    })


# ========== Пожертвования ==========

def donations(request):
    if request.method == 'POST':
        form = DonationForm(request.POST)
        if form.is_valid():
            donation = form.save(commit=False)
            if request.user.is_authenticated:
                donation.user = request.user
            if donation.campaign:
                donation.purpose = donation.campaign.purpose
            donation.save()
            return redirect('donation_done', token=donation.token)
    else:
        initial = {}
        if request.user.is_authenticated:
            initial = {'email': request.user.email, 'donor_name': request.user.first_name}
        campaign_id = request.GET.get('campaign')
        if campaign_id and campaign_id.isdigit():
            initial['campaign'] = campaign_id
        form = DonationForm(initial=initial)

    return render(request, 'core/donations.html', {
        'form': form,
        'campaigns': Campaign.objects.filter(is_approved=True, is_active=True).select_related('shelter'),
        'presets': [(100, 'Небольшой, но важный вклад'), (300, 'Поддержка покупки необходимых вещей'),
                    (500, 'Помощь ежедневным нуждам приюта'), (1000, 'Более весомая поддержка животных')],
    })


def donation_done(request, token):
    donation = get_object_or_404(Donation.objects.select_related('campaign'), token=token)
    return render(request, 'core/donation_done.html', {'donation': donation})


# ========== Регистрация и вход ==========

def register(request):
    """Вкладка «Регистрация»: регистрация или вход в личный кабинет."""
    if request.user.is_authenticated and request.method == 'GET':
        return render(request, 'core/register.html', {'already': True})

    if request.method == 'POST':
        form = RegisterForm(request.POST, request.FILES)
        if form.is_valid():
            with transaction.atomic():
                user = form.save()
                d = form.cleaned_data
                referrer = None
                if d.get('ref'):
                    ref_profile = Profile.objects.filter(
                        ref_code=d['ref'], role=Profile.ROLE_AMBASSADOR).select_related('user').first()
                    referrer = ref_profile.user if ref_profile else None
                Profile.objects.create(user=user, role=d['role'], phone=d['phone'], city=d.get('city', ''),
                                       about=d.get('about', ''), referred_by=referrer)
                group, _ = Group.objects.get_or_create(name=dict(Profile.ROLE_CHOICES)[d['role']])
                user.groups.add(group)

                if d['role'] == Profile.ROLE_ORGANIZER:
                    legal = '\n'.join(f'{label}: {d[key]}' for key, label in
                                      (('inn', 'ИНН'), ('ogrn', 'ОГРН'), ('legal_status', 'Статус НКО'),
                                       ('position', 'Должность заявителя')) if d.get(key))
                    app = ShelterApplication.objects.create(
                        user=user, name=d['shelter_name'], address=d['shelter_address'],
                        lat=d.get('shelter_lat'), lng=d.get('shelter_lng'),
                        contact_name=d['first_name'], contact_phone=d['phone'], contact_email=d['email'],
                        description=d['shelter_description'], needs=d['shelter_needs'], legal_info=legal,
                    )
                    for photo in d.get('shelter_photos') or []:
                        ShelterApplicationPhoto.objects.create(application=app, image=photo)

            login(request, user)
            messages.success(request, 'Регистрация прошла успешно! Добро пожаловать в личный кабинет.')
            return redirect('cabinet')
    else:
        form = RegisterForm(initial={
            'ref': request.GET.get('ref', ''),
            'role': request.GET.get('role') if request.GET.get('role') in dict(Profile.ROLE_CHOICES) else
            Profile.ROLE_VOLUNTEER,
        })
    return render(request, 'core/register.html', {
        'form': form, 'login_form': LoginForm(request), 'active_tab': 'register',
    })


class LoginView(auth_views.LoginView):
    """Вход в личный кабинет — на той же вкладке «Регистрация»."""
    template_name = 'core/register.html'
    authentication_form = LoginForm
    redirect_authenticated_user = True

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['login_form'] = ctx.pop('form')
        ctx['form'] = RegisterForm()
        ctx['active_tab'] = 'login'
        return ctx

    def get_success_url(self):
        return self.get_redirect_url() or '/cabinet/'


# ========== Личные кабинеты ==========

def _profile_form(request, profile):
    if request.method == 'POST' and request.POST.get('action') == 'profile':
        form = ProfileForm(request.POST)
        if form.is_valid():
            request.user.first_name = form.cleaned_data['first_name']
            request.user.save(update_fields=['first_name'])
            for f in ('phone', 'city', 'about'):
                setattr(profile, f, form.cleaned_data[f])
            profile.save()
            messages.success(request, 'Профиль сохранён.')
            return None, True
        return form, False
    return ProfileForm(initial={'first_name': request.user.first_name, 'phone': profile.phone,
                                'city': profile.city, 'about': profile.about}), False


@login_required
def cabinet(request):
    profile = getattr(request.user, 'profile', None)
    if profile is None:
        # Например, суперпользователь, созданный через createsuperuser
        return render(request, 'core/cabinet_staff.html')

    profile_form, saved = _profile_form(request, profile)
    if saved:
        return redirect('cabinet')

    ctx = {'profile': profile, 'profile_form': profile_form,
           'my_donations': request.user.donations.select_related('campaign')[:10]}
    handler = {
        Profile.ROLE_VOLUNTEER: _cabinet_volunteer,
        Profile.ROLE_AMBASSADOR: _cabinet_ambassador,
        Profile.ROLE_ORGANIZER: _cabinet_organizer,
        Profile.ROLE_FUNDRAISER: _cabinet_fundraiser,
    }[profile.role]
    result = handler(request, ctx)
    if result is not None:
        return result
    return render(request, f'core/cabinet_{profile.role}.html', ctx)


def _trips_context(request, ctx):
    enrollments = request.user.enrollments.select_related('trip', 'trip__shelter')
    now = timezone.now()
    ctx.update({
        'upcoming_enrollments': [e for e in enrollments if e.trip.date >= now],
        'past_enrollments': [e for e in enrollments if e.trip.date < now],
        'total_hours': sum(e.hours for e in enrollments),
        'trips_done': sum(1 for e in enrollments if e.is_attended),
        'available_trips': Trip.objects.filter(status=Trip.STATUS_OPEN, date__gte=now)
                                       .exclude(enrollments__user=request.user)
                                       .select_related('shelter')[:6],
    })


def _cabinet_volunteer(request, ctx):
    _trips_context(request, ctx)


def _cabinet_ambassador(request, ctx):
    _trips_context(request, ctx)
    invited = Profile.objects.filter(referred_by=request.user).select_related('user').order_by('-created_at')
    ctx.update({
        'invited': invited,
        'invited_by_role': invited.values('role').annotate(n=Count('id')),
        'ref_link': request.build_absolute_uri(f"/register/?ref={ctx['profile'].ref_code}"),
        'invited_hours': Enrollment.objects.filter(user__profile__referred_by=request.user)
                                           .aggregate(s=Sum('hours'))['s'] or 0,
    })


def _cabinet_organizer(request, ctx):
    user = request.user
    shelters = user.shelters.filter(is_active=True)
    action = request.POST.get('action') if request.method == 'POST' else None

    trip_form = TripForm(organizer=user)
    if action == 'trip':
        trip_form = TripForm(request.POST, organizer=user)
        if trip_form.is_valid():
            trip = trip_form.save(commit=False)
            trip.direction = trip.shelter.direction
            trip.status = Trip.STATUS_OPEN
            trip.save()
            messages.success(request, f'Рейс «{trip.title}» создан и открыт для записи.')
            return redirect('cabinet')
    elif action == 'needs':
        shelter = get_object_or_404(Shelter, id=request.POST.get('shelter_id'), organizer=user)
        form = ShelterNeedsForm(request.POST, instance=shelter)
        if form.is_valid():
            form.save()
            messages.success(request, 'Потребности приюта обновлены — они видны на карте.')
        return redirect('cabinet')
    elif action == 'attendance':
        enrollment = get_object_or_404(Enrollment, id=request.POST.get('enrollment_id'), trip__shelter__organizer=user)
        try:
            enrollment.hours = max(0, min(24, int(request.POST.get('hours') or 0)))
        except ValueError:
            enrollment.hours = 0
        enrollment.is_attended = bool(request.POST.get('is_attended'))
        enrollment.save(update_fields=['hours', 'is_attended'])
        messages.success(request, f'Участие {enrollment.user.first_name or enrollment.user.username} отмечено.')
        return redirect('cabinet')
    elif action == 'trip_status':
        trip = get_object_or_404(Trip, id=request.POST.get('trip_id'), shelter__organizer=user)
        if request.POST.get('status') in dict(Trip.STATUS_CHOICES):
            trip.status = request.POST['status']
            trip.save(update_fields=['status'])
            messages.success(request, f'Статус рейса «{trip.title}»: {trip.get_status_display()}.')
        return redirect('cabinet')

    ctx.update({
        'applications': user.shelter_applications.all(),
        'shelters': shelters,
        'trips': Trip.objects.filter(shelter__organizer=user).select_related('shelter')
                             .prefetch_related('enrollments__user__profile').order_by('-date'),
        'trip_form': trip_form,
        'status_choices': Trip.STATUS_CHOICES,
    })


def _cabinet_fundraiser(request, ctx):
    user = request.user
    form = CampaignForm()
    if request.method == 'POST' and request.POST.get('action') == 'campaign':
        form = CampaignForm(request.POST)
        if form.is_valid():
            campaign = form.save(commit=False)
            campaign.owner = user
            campaign.save()
            messages.success(request, 'Сбор создан и отправлен на проверку модератору.')
            return redirect('cabinet')
    elif request.method == 'POST' and request.POST.get('action') == 'campaign_close':
        campaign = get_object_or_404(Campaign, id=request.POST.get('campaign_id'), owner=user)
        campaign.is_active = False
        campaign.save(update_fields=['is_active'])
        messages.success(request, f'Сбор «{campaign.title}» завершён.')
        return redirect('cabinet')

    campaigns = user.campaigns.annotate(
        collected_sum=Sum('donations__amount', filter=Q(donations__status=Donation.STATUS_PAID)),
        donors=Count('donations', filter=Q(donations__status=Donation.STATUS_PAID)),
    )
    campaign_donations = Donation.objects.filter(campaign__owner=user).select_related('campaign')[:20]
    ctx.update({
        'campaign_form': form,
        'campaigns': campaigns,
        'campaign_donations': campaign_donations,
        'total_collected': sum(c.collected_sum or 0 for c in campaigns),
        'campaign_base_url': request.build_absolute_uri('/donations/?campaign='),
    })


def legacy_redirect(target):
    """Старые адреса (отдельные страницы контактов и отчётов) ведут на объединённые вкладки."""
    def view(request):
        return redirect(target, permanent=True)
    return view

