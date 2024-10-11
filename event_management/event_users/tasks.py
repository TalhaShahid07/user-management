
from datetime import timedelta
from event_management.celery import celery_task
import csv
from io import StringIO
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from .models import Registration, Event
import logging
from django.core.mail import send_mail
from celery import shared_task
from django.utils.timezone import now



# Set up logger to record information (info) and errors (error) during the execution of tasks.
# helps in debugging and monitoring the application.
logger = logging.getLogger(__name__)

# define a task and bind it to the task instance itself.
@shared_task(bind=True)
def generate_registration_report(self, event_id):
    logger.info(f"Starting report generation for event_id: {event_id}")

    try:
        # Fetch the event by ID
        event = Event.objects.get(id=event_id)
    except Event.DoesNotExist:
        logger.error(f"Event with ID {event_id} does not exist.")
        return {'error': 'Event not found.'}

    # Get all registrations where the user's role is 'Attendee'
    registrations = Registration.objects.filter(event=event, user__role='Attendee')
    logger.info(f"Found {registrations.count()} registrations for event: {event.title}")

    # Initialize the CSV output
    output = StringIO()         #create an in-memory file-like object where the CSV data will be stored.
    writer = csv.writer(output)
    writer.writerow(['User ID', 'Username', 'Registration Time', 'Checked In'])

    # Write registration data to CSV
    for registration in registrations:
        writer.writerow([
            registration.user.id,
            registration.user.username,
            registration.registration_time,  # Use the correct field
            registration.checked_in
        ])

    # Reset file pointer to the start
    output.seek(0)

    # Prepare the file name and content
    csv_file_name = f"{event.title}_registrations.csv"
    file_content = ContentFile(output.getvalue().encode('utf-8'))
    file_path = f'reports/{csv_file_name}'

    # Save the CSV file using Django's default storage
    saved_file_path = default_storage.save(file_path, file_content)
    logger.info(f"CSV report saved successfully at {saved_file_path}")

    return {
        'message': 'CSV report generated successfully!',
        'file_name': csv_file_name,
        'file_path': saved_file_path
    }


@shared_task
def send_event_registration_email(recipient_email, event_name):
    logger.info(f"Sending email to {recipient_email} for event {event_name}")
    
    subject = f"Registration Confirmation for {event_name}"
    message = f"Thank you for registering for {event_name}."
    email_from = 'talha.minhaj01@gmail.com'  # Use your email here
    recipient_list = [recipient_email]

    send_mail(subject, message, email_from, recipient_list)



# event_users

@shared_task
def send_event_reminder():
    """Send reminder emails to attendees 1 day before the event starts."""

    one_day_ago = now() + timedelta(days=1)
    upcoming_events = Registration.objects.filter(event__start_time__date=one_day_ago)

    for registration in upcoming_events:
        send_mail(
            subject=f"Reminder: {registration.event.title} is tomorrow!",
            message=f"Hello {registration.user.username},\n\n"
                    f"This is a reminder that the event '{registration.event.title}' "
                    f"will take place tomorrow at {registration.event.start_time}.\n\n"
                    f"Best regards,\nYour Event Management Team",
            from_email='talha.minhaj01@gmail.com',  # sender email
            recipient_list=[registration.user.email],
        )
        
        
        
        
    # soon = now() + timedelta(minutes=5)

    # # Filter registrations for events starting in the next 5 minutes
    # upcoming_events = Registration.objects.filter(event__start_time__lte=soon, event__start_time__gt=now())