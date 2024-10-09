
from django.db import models
from django.contrib.auth.models import AbstractUser

class CustomUser(AbstractUser):
    ROLE_CHOICES = (
        ('Organizer', 'Organizer'),
        ('Attendee', 'Attendee'),
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)

    # Add unique related_name arguments to avoid clashes
    groups = models.ManyToManyField(
        'auth.Group',
        related_name='customuser_set',
        blank=True
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        related_name='customuser_set',
        blank=True
    )

class Event(models.Model):
    title = models.CharField(max_length=255)
    description = models.TextField()
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    location = models.CharField(max_length=255)
    capacity = models.IntegerField()
    organizer = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='events')  # Added this field

class Registration(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    event = models.ForeignKey(Event, on_delete=models.CASCADE)
    registration_time = models.DateTimeField(auto_now_add=True)
    checked_in = models.BooleanField(default=False)
