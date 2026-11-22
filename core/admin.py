from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from django.utils.html import format_html

from .models import (
    Profile, Direction, Shelter, Trip, Enrollment, ShelterApplication, ShelterApplicationPhoto,
    Campaign, Donation, Review, MonthlyReport, ContactMessage,
)


class ProfileInline(admin.StackedInline):
    model = Profile
    fk_name = 'user'
    can_delete = False
    readonly_fields = ('ref_code',)


admin.site.unregister(User)


@admin.register(User)
class UserWithProfileAdmin(UserAdmin):
    inlines = (ProfileInline,)
    list_display = ('username', 'first_name', 'email', 'role', 'is_staff')
    list_filter = ('profile__role', 'is_staff')

    @admin.display(description='Роль')
    def role(self, obj):
        profile = getattr(obj, 'profile', None)
        return profile.get_role_display() if profile else '—'


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'phone', 'city', 'referred_by', 'created_at')
    list_filter = ('role',)
    search_fields = ('user__username', 'user__first_name', 'user__email', 'phone')


@admin.register(Direction)
class DirectionAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'is_active')
    prepopulated_fields = {'slug': ('name',)}


@admin.register(Shelter)
class ShelterAdmin(admin.ModelAdmin):
    list_display = ('name', 'direction', 'organizer', 'address', 'lat', 'lng', 'is_active')
    list_filter = ('direction', 'is_active')


@admin.register(Trip)
class TripAdmin(admin.ModelAdmin):
    list_display = ('title', 'direction', 'shelter', 'date', 'status', 'seats_taken', 'seats_total')
    list_filter = ('direction', 'status')
    date_hierarchy = 'date'


@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ('user', 'trip', 'created_at', 'is_attended', 'hours')
    list_filter = ('trip__direction', 'is_attended')
    list_editable = ('is_attended', 'hours')


class ShelterApplicationPhotoInline(admin.TabularInline):
    model = ShelterApplicationPhoto
    extra = 0
    readonly_fields = ('preview',)

    @admin.display(description='Превью')
    def preview(self, obj):
        return format_html('<img src="{}" style="height:80px;border-radius:6px;">', obj.image.url) if obj.image else '—'


@admin.register(ShelterApplication)
class ShelterApplicationAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'address', 'contact_phone', 'status', 'created_at')
    list_filter = ('status',)
    inlines = (ShelterApplicationPhotoInline,)
    actions = ('approve', 'reject')

    @admin.action(description='Одобрить и добавить приют на карту')
    def approve(self, request, queryset):
        direction = Direction.objects.filter(is_active=True).first()
        if direction is None:
            self.message_user(request, 'Сначала создайте хотя бы одно направление помощи.', messages.ERROR)
            return
        count = 0
        for app in queryset.exclude(status=ShelterApplication.STATUS_APPROVED):
            if app.shelter is None:
                app.shelter = Shelter.objects.create(
                    direction=direction, organizer=app.user, name=app.name, address=app.address,
                    lat=app.lat, lng=app.lng, description=app.description, needs=app.needs,
                    contact=f'{app.contact_name}, {app.contact_phone}',
                )
            app.status = ShelterApplication.STATUS_APPROVED
            app.save()
            count += 1
        self.message_user(request, f'Одобрено заявок: {count}. Приюты без координат не видны на карте — '
                                   f'укажите широту и долготу в разделе «Приюты».')

    @admin.action(description='Отклонить')
    def reject(self, request, queryset):
        queryset.update(status=ShelterApplication.STATUS_REJECTED)


@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    list_display = ('title', 'owner', 'goal', 'collected', 'is_approved', 'is_active', 'created_at')
    list_filter = ('is_approved', 'is_active', 'purpose')
    list_editable = ('is_approved', 'is_active')


@admin.register(Donation)
class DonationAdmin(admin.ModelAdmin):
    list_display = ('number', 'created_at', 'amount', 'period', 'purpose', 'campaign', 'email', 'payment_method', 'status')
    list_filter = ('status', 'period', 'payment_method', 'purpose')
    search_fields = ('email', 'donor_name')
    readonly_fields = ('token',)
    actions = ('mark_paid', 'mark_cancelled')

    @admin.action(description='Отметить как оплаченные')
    def mark_paid(self, request, queryset):
        queryset.update(status=Donation.STATUS_PAID)

    @admin.action(description='Отменить')
    def mark_cancelled(self, request, queryset):
        queryset.update(status=Donation.STATUS_CANCELLED)


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('name', 'role', 'rating', 'photo_preview', 'is_published', 'created_at')
    list_filter = ('is_published', 'role', 'rating')
    list_editable = ('is_published',)
    readonly_fields = ('photo_preview',)

    @admin.display(description='Фото')
    def photo_preview(self, obj):
        return format_html('<img src="{}" style="height:60px;border-radius:6px;">', obj.photo.url) if obj.photo else '—'


@admin.register(MonthlyReport)
class MonthlyReportAdmin(admin.ModelAdmin):
    list_display = ('period', 'trips', 'shelters', 'volunteers', 'collected', 'spent', 'is_published')
    list_editable = ('is_published',)


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'subject', 'is_answered', 'created_at')
    list_filter = ('is_answered',)
    list_editable = ('is_answered',)


admin.site.site_header = 'Добромобиль — администрирование'
admin.site.site_title = 'Добромобиль'
