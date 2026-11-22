from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path

from core import views

urlpatterns = [
    path('admin/', admin.site.urls),

    # 8 вкладок сайта
    path('', views.home, name='home'),
    path('about/', views.about, name='about'),                 # О нас + контакты
    path('register/', views.register, name='register'),        # Регистрация / вход
    path('map/', views.map_view, name='map'),                  # Карта приютов
    path('rules/', views.shelter_rules, name='shelter_rules'),  # Правила
    path('reviews/', views.reviews, name='reviews'),           # Отзывы + отчёты
    path('faq/', views.faq, name='faq'),                       # Вопросы
    path('donations/', views.donations, name='donations'),     # Пожертвования

    # Вход, выход, личный кабинет
    path('login/', views.LoginView.as_view(), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('cabinet/', views.cabinet, name='cabinet'),

    # Внутренние страницы
    path('guide/', views.guide, name='guide'),
    path('donations/<uuid:token>/', views.donation_done, name='donation_done'),
    path('direction/<slug:slug>/', views.direction_detail, name='direction_detail'),
    path('trip/<int:trip_id>/', views.trip_detail, name='trip_detail'),
    path('trip/<int:trip_id>/enroll/', views.enroll, name='enroll'),
    path('trip/<int:trip_id>/cancel/', views.cancel_enrollment, name='cancel_enrollment'),

    # Старые адреса
    path('contacts/', views.legacy_redirect('/about/#contacts')),
    path('reports/', views.legacy_redirect('/reviews/#reports')),
    path('shelter/register/', views.legacy_redirect('/register/?role=organizer')),
    path('shelter/rules/', views.legacy_redirect('/rules/')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
