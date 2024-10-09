
from django.shortcuts import render, get_object_or_404
from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from rest_framework.decorators import action
from django.utils.timezone import now
from .models import CustomUser, Event, Registration
from .serializers import CustomUserSerializer, EventSerializer, RegistrationSerializer
from .tasks import generate_registration_report, send_event_registration_email  # Import the Celery tasks
from celery.result import AsyncResult
from django_filters import rest_framework as django_filters
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied
from rest_framework import viewsets, filters




class RegisterUserView(APIView):
    permission_classes = [AllowAny]  # Allow any user to register

    def post(self, request):
        user_data = {
            'username': request.data.get('username'),
            'password': request.data.get('password'),
            'role': request.data.get('role'),  # Organizer or Attendee
            'email': request.data.get('email')
        }

        # Create a CustomUser instance
        serializer = CustomUserSerializer(data=user_data)
        if serializer.is_valid():
            user = serializer.save()
            return Response({
                'detail': 'Successfully registered.'
            }, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LoginUserView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        username = request.data.get('username')
        password = request.data.get('password')

        # Print input data for debugging
        print(f"Login attempt: Username={username}, Password={password}")

        # Authenticate the user
        user = authenticate(username=username, password=password)

        if user is not None:
            refresh = RefreshToken.for_user(user)  # Generate JWT tokens
            return Response({
                'detail': 'Login successful.',
                'user_id': user.id,
                'username': user.username,
                'role': user.role,
                'access': str(refresh.access_token),  # Access token
                'refresh': str(refresh),  # Refresh token
            }, status=status.HTTP_200_OK)

        print("Authentication failed: Invalid username or password")
        return Response({'error': 'Invalid username or password'}, status=status.HTTP_401_UNAUTHORIZED)


class UserViewSet(viewsets.ModelViewSet):
    queryset = CustomUser.objects.all()
    serializer_class = CustomUserSerializer
    permission_classes = [AllowAny]  # Allow any user to access user endpoints


class IsOrganizerPermission(IsAuthenticated):
    """Custom permission to allow only organizers to perform certain actions."""
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == 'Organizer'

class IsAttendeePermission(IsAuthenticated):
    """Custom permission to allow only attendees to register and check-in for events."""
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == 'Attendee'



class EventFilter(django_filters.FilterSet):
    start_time = django_filters.DateTimeFilter(field_name='start_time', lookup_expr='gte')  # Filter for upcoming events

    class Meta:
        model = Event
        fields = ['start_time']  # Add any other fields you want to filter on


class EventViewSet(viewsets.ModelViewSet):
    queryset = Event.objects.all()
    serializer_class = EventSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = (django_filters.DjangoFilterBackend, filters.SearchFilter)
    filterset_class = EventFilter
    search_fields = ['title']  # Assuming you have a related field for location

    def get_queryset(self):
        # Organizers should only see events they created
        if self.request.user.role == 'Organizer':
            return Event.objects.filter(organizer=self.request.user)
        # Attendees should only access available events (this is handled separately)
        raise PermissionDenied("You do not have permission to view this endpoint.")

    def create(self, request, *args, **kwargs):
        # Only organizers can create events
        if request.user.role != 'Organizer':
            raise PermissionDenied("Only organizers can create events.")
        
        # Modify the request data to include the organizer
        request.data['organizer'] = request.user.id  # Automatically set the organizer

        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        # Only organizers can update events
        if request.user.role != 'Organizer':
            raise PermissionDenied("Only organizers can update events.")
        request.data['organizer'] = request.user.id  # Automatically set the organizer
    
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        # Only organizers can delete events
        if request.user.role != 'Organizer':
            raise PermissionDenied("Only organizers can delete events.")
        request.data['organizer'] = request.user.id  # Automatically set the organizer

        return super().destroy(request, *args, **kwargs)


    @action(detail=True, methods=['post'], permission_classes=[IsAttendeePermission])
    def register(self, request, pk=None):
        """Attendee registers for an event."""
        event = get_object_or_404(Event, pk=pk)
        user = request.user

        if user.role != 'Attendee':
            return Response({'detail': 'Only attendees can register for events.'}, status=status.HTTP_403_FORBIDDEN)

        if Registration.objects.filter(event=event, user=user).exists():
            return Response({'detail': 'You are already registered for this event.'}, status=status.HTTP_400_BAD_REQUEST)

        registered_count = Registration.objects.filter(event=event).count()
        if registered_count >= event.capacity:
            return Response({'detail': 'This event is full.'}, status=status.HTTP_400_BAD_REQUEST)

        Registration.objects.create(event=event, user=user)
        send_event_registration_email.delay(user.email, event.title)
        return Response({'detail': 'Successfully registered for the event.'}, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], permission_classes=[IsAttendeePermission])
    def check_in(self, request, pk=None):
        """Attendee checks in to an event."""
        event = get_object_or_404(Event, pk=pk)
        user = request.user

        if user.role != 'Attendee':
            return Response({'detail': 'Only attendees can check-in for events.'}, status=status.HTTP_403_FORBIDDEN)

        registration = get_object_or_404(Registration, event=event, user=user)
        if registration.checked_in:
            return Response({'detail': 'You are already checked in.'}, status=status.HTTP_400_BAD_REQUEST)

        registration.checked_in = True
        registration.save()
        return Response({'detail': 'Successfully checked in.'}, status=status.HTTP_200_OK)

class AvailableEventsView(APIView):
    """View for attendees to see available events."""
    permission_classes = [IsAttendeePermission]

    def get(self, request):
        available_events = Event.objects.filter(capacity__gt=0)
        serializer = EventSerializer(available_events, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)



class RegistrationViewSet(viewsets.ModelViewSet):
    queryset = Registration.objects.all()
    serializer_class = RegistrationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Attendees can only see events they registered for
        if self.request.user.role == 'Attendee':
            return Registration.objects.filter(user=self.request.user)
        raise PermissionDenied("Only attendees can view their registrations.")

    def list(self, request, *args, **kwargs):
        # GET /registrations/: List all events the logged-in user (Attendee) has registered for
        if request.user.role != 'Attendee':
            raise PermissionDenied("Only attendees can view their registrations.")
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def cancel_registration(self, request, pk=None):
        """POST /events/{event_id}/cancel-registration/: Allows the attendee to cancel registration if the event is in the future."""
        event = get_object_or_404(Event, pk=pk)
        user = request.user

        # Ensure the user is an Attendee
        if user.role != 'Attendee':
            return Response({'detail': 'Only attendees can cancel event registration.'}, status=status.HTTP_403_FORBIDDEN)

        # Ensure the user is registered for the event
        try:
            registration = Registration.objects.get(event=event, user=user)
        except Registration.DoesNotExist:
            return Response({'detail': 'You are not registered for this event.'}, status=status.HTTP_404_NOT_FOUND)

        # Check if the event is in the future
        if event.start_time <= now():
            return Response({'detail': 'You can only cancel registration for future events.'}, status=status.HTTP_400_BAD_REQUEST)

        # Cancel the registration by deleting it
        registration.delete()
        return Response({'detail': 'Registration canceled successfully.'}, status=status.HTTP_200_OK)




class RegistrationsReportView(APIView):
    permission_classes = [IsOrganizerPermission]  # Only organizers can generate reports

    def get(self, request, event_id):
        event = get_object_or_404(Event, pk=event_id)

        if event.organizer != request.user:
            return Response({'detail': 'You are not the organizer of this event.'}, status=status.HTTP_403_FORBIDDEN)

        task = generate_registration_report.delay(event_id)  # Generate the CSV asynchronously
        return Response({
            'task_id': task.id,
            'detail': 'The registration report is generated please check thed desired folder'
        }, status=status.HTTP_202_ACCEPTED)


class CapacityStatusView(APIView):
    permission_classes = [IsOrganizerPermission]  # Only organizers can access capacity status

    def get(self, request, event_id):
        event = get_object_or_404(Event, pk=event_id)

        if event.organizer != request.user:
            return Response({'detail': 'You are not the organizer of this event.'}, status=status.HTTP_403_FORBIDDEN)

        total_capacity = event.capacity
        registered_count = Registration.objects.filter(event=event).count()
        remaining_capacity = total_capacity - registered_count

        return Response({
            'total_capacity': total_capacity,
            'registered_count': registered_count,
            'remaining_capacity': remaining_capacity
        }, status=status.HTTP_200_OK)


class ReportStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, task_id):
        result = AsyncResult(task_id)

        if result.ready():
            return Response({
                'status': 'completed',
                'result': result.result  # This will return the report file path or any other info you want to return
            }, status=status.HTTP_200_OK)
        else:
            return Response({
                'status': 'pending',
                'task_id': task_id
            }, status=status.HTTP_202_ACCEPTED)




    
#---------------------------------------------------
# class EventViewSet(viewsets.ModelViewSet):
#     queryset = Event.objects.all()
#     serializer_class = EventSerializer
#     permission_classes = [IsAuthenticated]

#     def get_queryset(self):
#         # Organizers should only see events they created
#         if self.request.user.role == 'Organizer':
#             return Event.objects.filter(organizer=self.request.user)
#         # Attendees should only access available events (this is handled separately)
#         raise PermissionDenied("You do not have permission to view this endpoint.")

#     def create(self, request, *args, **kwargs):
#         # Only organizers can create events
#         if request.user.role != 'Organizer':
#             raise PermissionDenied("Only organizers can create events.")
#         return super().create(request, *args, **kwargs)

#     def update(self, request, *args, **kwargs):
#         # Only organizers can update events
#         if request.user.role != 'Organizer':
#             raise PermissionDenied("Only organizers can update events.")
#         return super().update(request, *args, **kwargs)

#     def destroy(self, request, *args, **kwargs):
#         # Only organizers can delete events
#         if request.user.role != 'Organizer':
#             raise PermissionDenied("Only organizers can delete events.")
#         return super().destroy(request, *args, **kwargs)


#---------------------------------------------------------------


#''''''
'''
class AvailableEventsView(APIView):
    """View for attendees to see available events with filtering."""
    permission_classes = [IsAttendeePermission]
    filter_backends = [django_filters.DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['start_time']  # You can add other fields like end_time, etc.
    search_fields = ['title']  # Assuming you have a related field for location

    def get(self, request):
        # Fetch only events with available capacity
        available_events = Event.objects.filter(capacity__gt=0)

        # Apply filters and search if needed
        filter_backends = [django_filters.DjangoFilterBackend, filters.SearchFilter]
        queryset = self.filter_queryset(available_events)

        serializer = EventSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def filter_queryset(self, queryset):
        """Apply filters for searching and start_time filtering."""
        # For filtering based on start_time (past or upcoming events) and searching
        filterset = django_filters.FilterSet(data=self.request.query_params, queryset=queryset)
        queryset = filterset.qs

        # Apply search filter on title and location
        search_filter = filters.SearchFilter()
        queryset = search_filter.filter_queryset(self.request, queryset, view=self)

        return queryset
#.....................'''