from monitoring.models import User
from django.contrib.auth.hashers import make_password
User.objects.create(
    full_name='admin',
    phone_number='+256762038491',
    password_hash=make_password('qwerty'),
    role='Admin',
    is_active=True,
)
