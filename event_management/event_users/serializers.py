
from rest_framework import serializers
from .models import CustomUser, Event, Registration

class CustomUserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    email = serializers.EmailField()

    class Meta:
        model = CustomUser
        fields = ['username', 'password', 'role', 'email']

    def create(self, validated_data):
        user = CustomUser(
            username=validated_data['username'],
            email=validated_data['email'],
            role=validated_data['role']
        )
        user.set_password(validated_data['password'])  # Ensure the password is hashed
        user.save()
        return user

# Event Serializer
class EventSerializer(serializers.ModelSerializer):
    # Including a field to display the remaining capacity
    available_capacity = serializers.SerializerMethodField()

    class Meta:
        model = Event
        fields = ['id', 'title', 'description', 'start_time', 'end_time', 'organizer', 'capacity', 'available_capacity']  # Include capacity-related fields

    def get_available_capacity(self, obj):
        # Calculate remaining capacity
        total_registered = Registration.objects.filter(event=obj).count()
        return obj.capacity - total_registered  # Remaining spots available


# Registration Serializer
class RegistrationSerializer(serializers.ModelSerializer):
    event_title = serializers.ReadOnlyField(source='event.title')  # Display event title in registration

    class Meta:
        model = Registration
        fields = ['id', 'user', 'event', 'event_title', 'checked_in']  # Include event title and check-in status

    def create(self, validated_data):
        # Prevent duplicate registrations
        event = validated_data['event']
        user = validated_data['user']

        if Registration.objects.filter(event=event, user=user).exists():
            raise serializers.ValidationError("You are already registered for this event.")

        # Check if event has available capacity
        total_registered = Registration.objects.filter(event=event).count()
        if total_registered >= event.capacity:
            raise serializers.ValidationError("Event is full.")

        return super().create(validated_data)
