"""
Django admin registrations for all Smart-Stua monitoring models.
Provides web-based data management for the System Admin role.
"""

from django.contrib import admin
from .models import User, SensorNode, Reading, AlertLog, Threshold


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display  = ['full_name', 'phone_number', 'email', 'role', 'is_active', 'created_at']
    list_filter   = ['role', 'is_active']
    search_fields = ['full_name', 'phone_number', 'email']
    ordering      = ['full_name']
    readonly_fields = ['created_at']

    def save_model(self, request, obj, form, change):
        from django.contrib.auth.hashers import make_password
        # If the password hash is plaintext (doesn't start with Django hasher prefixes), hash it
        if obj.password_hash and not (
            obj.password_hash.startswith('pbkdf2_sha256$') or 
            obj.password_hash.startswith('argon2$') or 
            obj.password_hash.startswith('bcrypt$')
        ):
            obj.password_hash = make_password(obj.password_hash)
        super().save_model(request, obj, form, change)


@admin.register(SensorNode)
class SensorNodeAdmin(admin.ModelAdmin):
    list_display  = ['node_identifier', 'location_label', 'status',
                     'last_reading_at', 'pending_command']
    list_filter   = ['status', 'pending_command']
    search_fields = ['node_identifier', 'location_label', 'gateway_id']
    ordering      = ['location_label']
    readonly_fields = ['installed_at', 'last_reading_at']


@admin.register(Reading)
class ReadingAdmin(admin.ModelAdmin):
    list_display  = ['reading_id', 'node', 'temperature_c', 'humidity_pct', 'recorded_at']
    list_filter   = ['node']
    search_fields = ['node__node_identifier', 'node__location_label']
    ordering      = ['-recorded_at']
    readonly_fields = ['recorded_at']
    date_hierarchy = 'recorded_at'


@admin.register(AlertLog)
class AlertLogAdmin(admin.ModelAdmin):
    list_display  = ['alert_id', 'node', 'ari_value', 'risk_level',
                     'sent_to', 'sent_at', 'action_taken']
    list_filter   = ['risk_level', 'action_taken']
    search_fields = ['node__node_identifier', 'sent_to', 'message']
    ordering      = ['-sent_at']
    readonly_fields = ['sent_at', 'sms_sid']
    date_hierarchy = 'sent_at'
    actions = ['mark_action_taken']

    @admin.action(description='Mark selected alerts as action taken')
    def mark_action_taken(self, request, queryset):
        queryset.update(action_taken=True)


@admin.register(Threshold)
class ThresholdAdmin(admin.ModelAdmin):
    list_display  = ['node', 'min_temp', 'max_temp', 'min_humidity',
                     'max_humidity', 'risk_duration', 'updated_at']
    search_fields = ['node__node_identifier']
    readonly_fields = ['updated_at']


# ─── Admin Site Customisation ────────────────────────────────────────────────
admin.site.site_header  = 'Smart-Stua Administration'
admin.site.site_title   = 'Smart-Stua Admin'
admin.site.index_title  = 'Aflatoxin Monitoring System'
