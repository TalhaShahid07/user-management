from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from .views import (
    RegisterUserView,
    LoginUserView,
    UserViewSet,
    EventViewSet,
    RegistrationViewSet,
    AvailableEventsView,
    RegistrationsReportView,
    CapacityStatusView,
    # ReportStatusView,
)

urlpatterns = [
    path('register/', RegisterUserView.as_view(), name='register'),  # User registration
    path('login/', LoginUserView.as_view(), name='login'),  # Custom login for JWT
    path('users/', UserViewSet.as_view({'get': 'list', 'post': 'create'}), name='user-list'),
    path('users/<int:pk>/', UserViewSet.as_view({'get': 'retrieve', 'put': 'update', 'delete': 'destroy'}), name='user-detail'),  # User detail
    path('events/', EventViewSet.as_view({'get': 'list', 'post': 'create'}), name='event-list'),
    path('events/<int:pk>/', EventViewSet.as_view({'get': 'retrieve', 'put': 'update', 'delete': 'destroy'}), name='event-detail'),
    path('events/available/', AvailableEventsView.as_view(), name='available-events'),

    # Event registration
    path('events/<int:pk>/register/', EventViewSet.as_view({'post': 'register'}), name='register-for-event'),

    # Event check-in
    path('events/<int:pk>/check-in/', EventViewSet.as_view({'post': 'check_in'}), name='check-in-for-event'),

    # Cancel event registration should now point to RegistrationViewSet
    path('events/<int:pk>/cancel-registration/', RegistrationViewSet.as_view({'post': 'cancel_registration'}), name='cancel-registration'),

    # Registration management
    path('registrations/', RegistrationViewSet.as_view({'get': 'list'}), name='registration-list'),

    # Generate registration report
    path('events/<int:event_id>/registrations-report/', RegistrationsReportView.as_view(), name='registrations-report'),

    # Check event capacity status
    path('events/<int:event_id>/capacity-status/', CapacityStatusView.as_view(), name='capacity-status'),

    # path('report-status/<str:task_id>/', ReportStatusView.as_view(), name='report-status'),  # Add this line

    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

]

