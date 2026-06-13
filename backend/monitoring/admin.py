"""
Django admin registrations for all Smart-Stua monitoring models.
Styled with django-jazzmin for a clean, modern IoT management interface.
"""

from django.contrib import admin
from django.utils.html import format_html
from .models import User, SensorNode, Reading, AlertLog, Threshold


# ─── User ─────────────────────────────────────────────────────────────────────
@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display        = ['full_name', 'phone_number', 'email', 'role_badge',
                           'is_active', 'created_at']
    list_display_links  = ['full_name']
    list_filter         = ['role', 'is_active']
    search_fields       = ['full_name', 'phone_number', 'email']
    ordering            = ['full_name']
    readonly_fields     = ['created_at']
    list_per_page       = 25

    fieldsets = (
        ('Identity', {
            'fields': ('full_name', 'phone_number', 'email'),
        }),
        ('Access', {
            'fields': ('role', 'password_hash', 'is_active'),
        }),
        ('Metadata', {
            'fields': ('push_token', 'created_at'),
            'classes': ('collapse',),
        }),
    )

    @admin.display(description='Role')
    def role_badge(self, obj):
        colours = {
            'admin':         '#e74c3c',
            'store_manager': '#f39c12',
            'farmer':        '#27ae60',
        }
        colour = colours.get(obj.role, '#95a5a6')
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;'
            'border-radius:4px;font-size:11px;font-weight:600;">{}</span>',
            colour, obj.get_role_display()
        )

    def save_model(self, request, obj, form, change):
        from django.contrib.auth.hashers import make_password
        if obj.password_hash and not (
            obj.password_hash.startswith('pbkdf2_sha256$') or
            obj.password_hash.startswith('argon2$') or
            obj.password_hash.startswith('bcrypt$')
        ):
            obj.password_hash = make_password(obj.password_hash)
        super().save_model(request, obj, form, change)


# ─── SensorNode ───────────────────────────────────────────────────────────────
@admin.register(SensorNode)
class SensorNodeAdmin(admin.ModelAdmin):
    list_display        = ['node_identifier', 'location_label', 'status_badge',
                           'last_reading_at', 'pending_command', 'api_key_preview']
    list_display_links  = ['node_identifier']
    list_filter         = ['status', 'pending_command']
    search_fields       = ['node_identifier', 'location_label', 'gateway_id', 'mac_address']
    ordering            = ['location_label']
    readonly_fields     = ['installed_at', 'last_reading_at', 'api_key']
    list_per_page       = 25

    fieldsets = (
        ('Identification', {
            'fields': ('node_identifier', 'location_label', 'mac_address', 'gateway_id'),
        }),
        ('Status & Control', {
            'fields': ('status', 'pending_command', 'last_reading_at', 'installed_at'),
        }),
        ('Authentication', {
            'fields': ('api_key',),
            'description': (
                '⚠️ Copy this key into your ESP32 firmware (API_KEY constant). '
                'It is generated automatically and cannot be edited manually — '
                'use the "Rotate API Key" action to regenerate it.'
            ),
        }),
    )

    actions = ['rotate_api_key']

    @admin.display(description='Status')
    def status_badge(self, obj):
        colours = {
            'active':      '#27ae60',
            'inactive':    '#e74c3c',
            'maintenance': '#f39c12',
        }
        colour = colours.get(obj.status, '#95a5a6')
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;'
            'border-radius:4px;font-size:11px;font-weight:600;">{}</span>',
            colour, obj.get_status_display()
        )

    @admin.display(description='API Key')
    def api_key_preview(self, obj):
        """Show first 8 chars + masked tail — enough to identify, not enough to misuse."""
        if not obj.api_key:
            return '—'
        return format_html(
            '<code style="font-size:11px;">{}</code>',
            obj.api_key[:8] + '•' * 8
        )

    @admin.action(description='🔄  Rotate API key for selected nodes')
    def rotate_api_key(self, request, queryset):
        for node in queryset:
            node.rotate_api_key()
        self.message_user(
            request,
            f'API keys rotated for {queryset.count()} node(s). '
            'Update firmware on those devices now.',
        )


# ─── Reading ──────────────────────────────────────────────────────────────────
@admin.register(Reading)
class ReadingAdmin(admin.ModelAdmin):
    list_display        = ['reading_id', 'node', 'temperature_c', 'humidity_pct',
                           'moisture_pct', 'recorded_at']
    list_display_links  = ['reading_id']
    list_filter         = ['node']
    search_fields       = ['node__node_identifier', 'node__location_label']
    ordering            = ['-recorded_at']
    readonly_fields     = ['recorded_at']
    date_hierarchy      = 'recorded_at'
    list_per_page       = 50

    fieldsets = (
        ('Node', {
            'fields': ('node',),
        }),
        ('Sensor Values', {
            'fields': ('temperature_c', 'humidity_pct', 'moisture_pct'),
        }),
        ('Timestamps', {
            'fields': ('recorded_at', 'device_ts'),
        }),
    )


# ─── AlertLog ─────────────────────────────────────────────────────────────────
@admin.register(AlertLog)
class AlertLogAdmin(admin.ModelAdmin):
    list_display        = ['alert_id', 'node', 'risk_badge', 'ari_value',
                           'sent_to', 'sent_at', 'action_taken']
    list_display_links  = ['alert_id']
    list_filter         = ['risk_level', 'action_taken', 'alert_type']
    search_fields       = ['node__node_identifier', 'sent_to', 'message']
    ordering            = ['-sent_at']
    readonly_fields     = ['sent_at', 'sms_sid']
    date_hierarchy      = 'sent_at'
    list_per_page       = 50
    actions             = ['mark_action_taken']

    fieldsets = (
        ('Alert Info', {
            'fields': ('node', 'alert_type', 'risk_level', 'ari_value', 'message'),
        }),
        ('Notification', {
            'fields': ('sent_to', 'sent_at', 'sms_sid', 'action_taken'),
        }),
    )

    @admin.display(description='Risk')
    def risk_badge(self, obj):
        colours = {
            'High':   '#e74c3c',
            'Medium': '#f39c12',
            'Low':    '#27ae60',
        }
        colour = colours.get(obj.risk_level, '#95a5a6')
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;'
            'border-radius:4px;font-size:11px;font-weight:600;">{}</span>',
            colour, obj.risk_level
        )

    @admin.action(description='✅  Mark selected alerts as action taken')
    def mark_action_taken(self, request, queryset):
        updated = queryset.update(action_taken=True)
        self.message_user(request, f'{updated} alert(s) marked as resolved.')


# ─── Threshold ────────────────────────────────────────────────────────────────
@admin.register(Threshold)
class ThresholdAdmin(admin.ModelAdmin):
    list_display    = ['node', 'min_temp', 'max_temp', 'min_humidity',
                       'max_humidity', 'risk_duration', 'updated_at']
    search_fields   = ['node__node_identifier']
    readonly_fields = ['updated_at']
    list_per_page   = 25

    fieldsets = (
        ('Node', {
            'fields': ('node',),
        }),
        ('Temperature Thresholds (°C)', {
            'fields': ('min_temp', 'max_temp'),
        }),
        ('Humidity Thresholds (%)', {
            'fields': ('min_humidity', 'max_humidity'),
        }),
        ('Risk Timing', {
            'fields': ('risk_duration', 'updated_at'),
        }),
    )


# ─── Admin Site Branding ──────────────────────────────────────────────────────
# These are overridden by JAZZMIN_SETTINGS but kept as Django fallbacks.
admin.site.site_header  = 'Smart-Stua Administration'
admin.site.site_title   = 'Smart-Stua Admin'
admin.site.index_title  = 'IoT Aflatoxin Monitoring Platform'
