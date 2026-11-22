from django.conf import settings

# Вкладки сайта: их всегда ровно 8 и они одинаковы на всех страницах.
NAV_TABS = [
    ('home', '/', 'Главная'),
    ('about', '/about/', 'О нас'),
    ('register', '/register/', 'Регистрация'),
    ('map', '/map/', 'Карта приютов'),
    ('shelter_rules', '/rules/', 'Правила'),
    ('reviews', '/reviews/', 'Отзывы'),
    ('faq', '/faq/', 'Вопросы'),
    ('donations', '/donations/', 'Пожертвования'),
]

# Внутренние страницы подсвечивают ближайшую по смыслу вкладку
ACTIVE_ALIASES = {
    'login': 'register', 'cabinet': 'register', 'guide': 'about',
    'donation_done': 'donations', 'trip_detail': 'map', 'direction_detail': 'map',
}


def site(request):
    match = getattr(request, 'resolver_match', None)
    name = match.url_name if match else ''
    return {
        'nav_tabs': NAV_TABS,
        'active_tab_name': ACTIVE_ALIASES.get(name, name),
        'org': settings.ORGANIZATION,
    }
