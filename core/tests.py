import io
import re
import shutil
import tempfile
from datetime import timedelta

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone

from .models import (
    Profile, Direction, Shelter, Trip, Enrollment, ShelterApplication, Campaign, Donation, Review,
)

TABS = ['Главная', 'О нас', 'Регистрация', 'Карта приютов', 'Правила', 'Отзывы', 'Вопросы', 'Пожертвования']
MEDIA = tempfile.mkdtemp()


def make_image(name='photo.png'):
    from PIL import Image
    buf = io.BytesIO()
    Image.new('RGB', (20, 20), 'orange').save(buf, 'PNG')
    return SimpleUploadedFile(name, buf.getvalue(), content_type='image/png')


def reg_data(role, username, **extra):
    data = {
        'role': role, 'username': username, 'password1': 'Dobro-Pass-2026', 'password2': 'Dobro-Pass-2026',
        'first_name': 'Тест Тестов', 'email': f'{username}@example.com', 'phone': '+79990000000',
        'agree': 'on',
    }
    data.update(extra)
    return data


@override_settings(MEDIA_ROOT=MEDIA)
class SiteTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA, ignore_errors=True)

    def register(self, role, username, **extra):
        return self.client.post('/register/', reg_data(role, username, **extra))

    # --- Навигация и подвал ---

    def test_all_tabs_same_on_every_page(self):
        for url in ['/', '/about/', '/register/', '/map/', '/rules/', '/reviews/', '/faq/', '/donations/',
                    '/guide/', '/login/']:
            html = self.client.get(url).content.decode()
            nav = re.search(r'<nav>(.*?)</nav>', html, re.S).group(1)
            labels = re.findall(r'>([^<]+)</a>', nav)
            self.assertEqual(labels, TABS, url)

    def test_footer_cleaned(self):
        html = self.client.get('/').content.decode()
        self.assertNotIn('Демонстрационные реквизиты', html)
        self.assertNotIn('Логотип', html)
        self.assertIn('footer-contacts', html)

    def test_old_urls_redirect(self):
        self.assertRedirects(self.client.get('/contacts/'), '/about/#contacts', status_code=301,
                             fetch_redirect_response=False)
        self.assertRedirects(self.client.get('/reports/'), '/reviews/#reports', status_code=301,
                             fetch_redirect_response=False)

    def test_reports_merged_into_reviews(self):
        html = self.client.get('/reviews/').content.decode()
        self.assertIn('id="reports"', html)
        self.assertIn('Октябрь 2026', html)

    def test_contacts_merged_into_about(self):
        resp = self.client.post('/about/', {'name': 'Оля', 'email': 'o@example.com', 'subject': 'Волонтёрство',
                                            'message': 'Привет'})
        self.assertEqual(resp.status_code, 302)
        self.assertIn('id="contacts"', self.client.get('/about/').content.decode())

    # --- Регистрация ---

    def test_volunteer_and_others_register_without_shelter_fields(self):
        for role in ('volunteer', 'ambassador', 'fundraiser'):
            self.client.logout()
            resp = self.register(role, f'user_{role}')
            self.assertRedirects(resp, '/cabinet/', fetch_redirect_response=False)
            user = User.objects.get(username=f'user_{role}')
            self.assertEqual(user.profile.role, role)
            self.assertTrue(user.groups.exists())

    def test_organizer_requires_shelter_description_and_needs(self):
        resp = self.register('organizer', 'org1')
        self.assertEqual(resp.status_code, 200)
        form = resp.context['form']
        for f in ('shelter_name', 'shelter_address', 'shelter_description', 'shelter_needs'):
            self.assertIn(f, form.errors)

        resp = self.register('organizer', 'org1', shelter_name='Добрые руки', shelter_address='Сургут',
                             shelter_description='60 собак', shelter_needs='Корма',
                             shelter_photos=[make_image('a.png'), make_image('b.png')])
        self.assertEqual(resp.status_code, 302)
        app = ShelterApplication.objects.get(name='Добрые руки')
        self.assertEqual(app.user.username, 'org1')
        self.assertEqual(app.photos.count(), 2)

    def test_login_by_email_opens_cabinet(self):
        self.register('volunteer', 'vol')
        self.client.logout()
        resp = self.client.post('/login/', {'username': 'vol@example.com', 'password': 'Dobro-Pass-2026'})
        self.assertRedirects(resp, '/cabinet/', fetch_redirect_response=False)
        self.assertContains(self.client.get('/cabinet/'), 'Личный кабинет: волонтёр')

    def test_each_role_has_own_cabinet(self):
        titles = {'volunteer': 'волонтёр', 'ambassador': 'амбассадор', 'organizer': 'организатор',
                  'fundraiser': 'фандрайзер'}
        for role, title in titles.items():
            self.client.logout()
            extra = {}
            if role == 'organizer':
                extra = dict(shelter_name='П', shelter_address='А', shelter_description='О', shelter_needs='Н')
            self.register(role, f'c_{role}', **extra)
            self.assertContains(self.client.get('/cabinet/'), f'Личный кабинет: {title}')

    def test_cabinet_requires_login(self):
        self.assertRedirects(self.client.get('/cabinet/'), '/login/?next=/cabinet/', fetch_redirect_response=False)

    # --- Сценарии ролей ---

    def test_ambassador_referral(self):
        self.register('ambassador', 'amb')
        code = User.objects.get(username='amb').profile.ref_code
        self.client.logout()
        self.register('volunteer', 'friend', ref=code)
        self.assertEqual(User.objects.get(username='friend').profile.referred_by.username, 'amb')

    def test_organizer_trip_flow(self):
        self.register('organizer', 'org', shelter_name='П', shelter_address='А',
                      shelter_description='О', shelter_needs='Н')
        org = User.objects.get(username='org')
        shelter = Shelter.objects.create(direction=Direction.objects.first(), organizer=org, name='П', lat=61, lng=73)
        when = (timezone.localtime() + timedelta(days=3)).strftime('%Y-%m-%dT%H:%M')
        resp = self.client.post('/cabinet/', {'action': 'trip', 'shelter': shelter.id, 'title': 'Рейс 1',
                                              'date': when, 'seats_total': 3})
        self.assertEqual(resp.status_code, 302)
        trip = Trip.objects.get(title='Рейс 1')
        self.assertEqual(trip.status, Trip.STATUS_OPEN)

        self.client.logout()
        self.register('volunteer', 'vol')
        self.client.post(f'/trip/{trip.id}/enroll/')
        enrollment = Enrollment.objects.get(trip=trip)

        self.client.logout()
        self.client.login(username='org', password='Dobro-Pass-2026')
        self.client.post('/cabinet/', {'action': 'attendance', 'enrollment_id': enrollment.id,
                                       'hours': 4, 'is_attended': 'on'})
        enrollment.refresh_from_db()
        self.assertEqual((enrollment.hours, enrollment.is_attended), (4, True))

    def test_fundraiser_cannot_enroll(self):
        shelter = Shelter.objects.create(direction=Direction.objects.first(), name='П')
        trip = Trip.objects.create(direction=shelter.direction, shelter=shelter, title='Р',
                                   date=timezone.now() + timedelta(days=1))
        self.register('fundraiser', 'fr')
        self.client.post(f'/trip/{trip.id}/enroll/')
        self.assertFalse(Enrollment.objects.exists())

    def test_fundraiser_campaign_and_donation(self):
        self.register('fundraiser', 'fr')
        self.client.post('/cabinet/', {'action': 'campaign', 'title': 'Корм на зиму', 'description': 'Нужно',
                                       'purpose': 'food', 'goal': 10000})
        campaign = Campaign.objects.get(title='Корм на зиму')
        self.assertFalse(campaign.is_approved)
        campaign.is_approved = True
        campaign.save()

        resp = self.client.post('/donations/', {'campaign': campaign.id, 'purpose': 'general', 'amount': 500,
                                                'period': 'once', 'payment_method': 'sbp',
                                                'email': 'd@example.com', 'agree_offer': 'on'})
        donation = Donation.objects.get()
        self.assertRedirects(resp, f'/donations/{donation.token}/', fetch_redirect_response=False)
        self.assertEqual(donation.purpose, 'food')
        self.assertContains(self.client.get(resp.url), donation.number)
        donation.status = Donation.STATUS_PAID
        donation.save()
        self.assertEqual(campaign.collected(), 500)

    def test_donation_requires_offer_consent(self):
        resp = self.client.post('/donations/', {'purpose': 'food', 'amount': 500, 'period': 'once',
                                                'payment_method': 'sbp', 'email': 'd@example.com'})
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(Donation.objects.exists())

    # --- Отзывы с фото ---

    def test_review_with_photo(self):
        Review.objects.all().delete()
        resp = self.client.post('/reviews/', {'name': 'Маша', 'role': 'volunteer', 'rating': 5,
                                              'text': 'Супер', 'photo': make_image()})
        self.assertEqual(resp.status_code, 302)
        review = Review.objects.get()
        self.assertTrue(review.photo.name.startswith('reviews/'))
        self.assertFalse(review.is_published)
        review.is_published = True
        review.save()
        self.assertContains(self.client.get('/reviews/'), review.photo.url)

    def test_review_rejects_non_image(self):
        bad = SimpleUploadedFile('x.png', b'not an image', content_type='image/png')
        resp = self.client.post('/reviews/', {'name': 'М', 'role': 'volunteer', 'rating': 5, 'text': 'Т', 'photo': bad})
        self.assertEqual(resp.status_code, 200)
        self.assertIn('photo', resp.context['form'].errors)
