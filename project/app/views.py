import csv

import pydf
import requests
from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import authenticate
from django.contrib.auth import login as log_in
from django.contrib.auth import logout as log_out
from django.contrib.auth.decorators import login_required
from django.core.files.base import ContentFile
from django.http import FileResponse
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.crypto import get_random_string

from .forms import DeleteForm
from .forms import RecipientForm
from .forms import VolunteerForm
from .models import Picture
from .models import Recipient
from .models import Volunteer
from .tasks import send_recipient_confirmation
from .tasks import send_volunteer_confirmation


# Root
def index(request):
    if request.user.is_authenticated:
        return redirect('account')
    pictures = Picture.objects.all()
    return render(
        request,
        'app/pages/index.html',
        context={
            'pictures': pictures,
            'is_active': settings.ACTIVE,
        }
    )

# Authentication
def login(request):
    # Set landing page depending on initial button
    initial = request.GET.get('initial', 'None')
    redirect_uri = request.build_absolute_uri(reverse('callback'))
    state = f"{initial}|{get_random_string()}"
    request.session['state'] = state

    params = {
        'response_type': 'code',
        'client_id': settings.AUTH0_CLIENT_ID,
        'scope': 'openid profile email',
        'redirect_uri': redirect_uri,
        'state': state,
        'screen_hint': 'signup',
    }
    url = requests.Request(
        'GET',
        f'https://{settings.AUTH0_DOMAIN}/authorize',
        params=params,
    ).prepare().url
    return redirect(url)

def callback(request):
    # Reject if state doesn't match
    browser_state = request.session.get('state')
    server_state = request.GET.get('state')
    if browser_state != server_state:
        return HttpResponse(status=400)

    # get initial
    initial = browser_state.partition("|")[0]

    # Get Auth0 Code
    code = request.GET.get('code', None)
    if not code:
        return HttpResponse(status=400)
    token_url = f'https://{settings.AUTH0_DOMAIN}/oauth/token'
    redirect_uri = request.build_absolute_uri(reverse('callback'))
    token_payload = {
        'client_id': settings.AUTH0_CLIENT_ID,
        'client_secret': settings.AUTH0_CLIENT_SECRET,
        'redirect_uri': redirect_uri,
        'code': code,
        'grant_type': 'authorization_code'
    }
    token = requests.post(
        token_url,
        json=token_payload,
    ).json()
    access_token = token['access_token']
    user_url = f'https://{settings.AUTH0_DOMAIN}/userinfo?access_token={access_token}'
    payload = requests.get(user_url).json()
    # format payload key
    payload['username'] = payload.pop('sub')
    user = authenticate(request, **payload)
    if user:
        log_in(request, user)
        if initial == 'recipient':
            return redirect('recipient-create')
        if initial == 'volunteer':
            return redirect('volunteer-create')
        if user.is_admin:
            return redirect('admin:index')
        recipient = getattr(user, 'recipient', None)
        volunteer = getattr(user, 'volunteer', None)
        if recipient and volunteer:
            return redirect('account')
        if recipient:
            return redirect('recipient')
        if volunteer:
            return redirect('volunteer')
        return redirect('account')
    return HttpResponse(status=403)

def logout(request):
    log_out(request)
    params = {
        'client_id': settings.AUTH0_CLIENT_ID,
        'return_to': request.build_absolute_uri(reverse('index')),
    }
    logout_url = requests.Request(
        'GET',
        f'https://{settings.AUTH0_DOMAIN}/v2/logout',
        params=params,
    ).prepare().url
    messages.success(
        request,
        "You Have Been Logged Out!",
    )
    return redirect(logout_url)

#Account
@login_required
def account(request):
    user = request.user
    recipient = getattr(user, 'recipient', None)
    volunteer = getattr(user, 'volunteer', None)
    assignment = getattr(volunteer, 'recipient', None) if volunteer else None
    return render(
        request,
        'app/pages/account.html',
        context={
            'user': user,
            'recipient': recipient,
            'volunteer': volunteer,
            'assignment': assignment,
        }
    )

@login_required
def account_delete(request):
    if request.method == "POST":
        form = DeleteForm(request.POST)
        if form.is_valid():
            user = request.user
            user.delete()
            messages.error(
                request,
                "Account Deleted!",
            )
            return redirect('index')
    else:
        form = DeleteForm()
    return render(
        request,
        'app/pages/account_delete.html',
        {'form': form,},
    )

# Recipient
@login_required
def recipient(request):
    try:
        recipient = request.user.recipient
    except AttributeError:
        return redirect('recipient-create')
    assignments = getattr(recipient, 'assignments', None)
    return render(
        request,
        'app/pages/recipient.html',
        context={
            'recipient': recipient,
            'assignments': assignments,
        }
    )

@login_required
def recipient_create(request):
    recipient = getattr(request.user, 'recipient', None)
    if recipient:
        return redirect('recipient')

    initial = {
        'name': request.user.name,
        'email': request.user.email,
    }
    form = RecipientForm(request.POST) if request.POST else RecipientForm(initial=initial)

    if form.is_valid():
        recipient = form.save(commit=False)
        recipient.user = request.user
        recipient.save()
        send_recipient_confirmation.delay(recipient)
        messages.success(
            request,
            "Registration complete!  We will reach out before November 8th with futher details.",
        )
        return redirect('recipient')
    return render(
        request,
        'app/pages/recipient_create.html',
        context={
            'form': form,
        }
    )

@login_required
def recipient_update(request):
    recipient = getattr(request.user, 'recipient', None)
    if not recipient:
        return redirect('recipient-create')
    form = RecipientForm(request.POST, instance=recipient) if request.POST else RecipientForm(instance=recipient)
    if form.is_valid():
        form.save()
        messages.success(
            request,
            "Recipient information updated!",
        )
        return redirect('recipient')
    return render(
        request,
        'app/pages/recipient_update.html',
        context={
            'form': form,
        }
    )

@login_required
def recipient_delete(request):
    if request.method == "POST":
        form = DeleteForm(request.POST)
        if form.is_valid():
            recipient = getattr(request.user, 'recipient', None)
            if recipient:
                recipient.delete()
            messages.error(
                request,
                "Removed!",
            )
            return redirect('account')
    else:
        form = DeleteForm()
    return render(
        request,
        'app/pages/recipient_delete.html',
        {'form': form,},
    )


# Volunteer
@login_required
def volunteer(request):
    try:
        volunteer = request.user.volunteer
    except AttributeError:
        return redirect('volunteer-create')
    assignment = getattr(volunteer, 'assignment', None)
    return render(
        request,
        'app/pages/volunteer.html',
        context={
            'volunteer': volunteer,
            'assignment': assignment,
        }
    )

@login_required
def volunteer_create(request):
    volunteer = getattr(request.user, 'volunteer', None)
    if volunteer:
        return redirect('volunteer')

    initial = {
        'name': request.user.name,
        'email': request.user.email,
    }
    form = VolunteerForm(request.POST) if request.POST else VolunteerForm(initial=initial)
    if form.is_valid():
        volunteer = form.save(commit=False)
        volunteer.user = request.user
        volunteer.save()
        send_volunteer_confirmation.delay(volunteer)
        messages.success(
            request,
            "Signup complete!  We will reach out before November 8th with futher details.",
        )
        return redirect('volunteer')
    return render(
        request,
        'app/pages/volunteer_create.html',
        context={
            'form': form,
        }
    )

@login_required
def volunteer_update(request):
    volunteer = getattr(request.user, 'volunteer', None)
    if not volunteer:
        return redirect('volunteer-create')
    form = VolunteerForm(request.POST, instance=volunteer) if request.POST else VolunteerForm(instance=volunteer)
    if form.is_valid():
        form.save()
        messages.success(
            request,
            "Volunteer information updated!",
        )
        return redirect('volunteer')
    return render(
        request,
        'app/pages/volunteer_update.html',
        context={
            'form': form,
        }
    )

@login_required
def volunteer_delete(request):
    if request.method == "POST":
        form = DeleteForm(request.POST)
        if form.is_valid():
            volunteer = getattr(request.user, 'volunteer', None)
            if volunteer:
                volunteer.delete()
            messages.error(
                request,
                "You have been removed as a Volunteer!",
            )
            return redirect('account')
    else:
        form = DeleteForm()
    return render(
        request,
        'app/pages/volunteer_delete.html',
        {'form': form,},
    )


# Admin
@staff_member_required
def dashboard(request):
    volunteers = Volunteer.objects.order_by(
        'last_name',
        'first_name',
    )
    return render(
        request,
        'app/pages/dashboard.html',
        {'volunteers': volunteers},
    )

@staff_member_required
def dashboard_volunteer(request, volunteer_id):
    volunteer = Volunteer.objects.get(pk=volunteer_id)
    return render(
        request,
        'app/pages/volunteer.html',
        {'volunteer': volunteer},
    )


@staff_member_required
def handout_pdf(request, volunteer_id):
    volunteer = get_object_or_404(Volunteer, pk=volunteer_id)
    context={
        'volunteer': volunteer,
        'recipient': volunteer.recipient,
        'map': map,
    }
    rendered = render_to_string('app/pages/handout.html', context)
    pdf = pydf.generate_pdf(
        rendered,
        enable_smart_shrinking=False,
        orientation='Portrait',
        margin_top='10mm',
        margin_bottom='10mm',
    )
    content = ContentFile(pdf)
    return FileResponse(
        content,
        as_attachment=True,
        filename='rake_up_eagle_handout.pdf',
    )

@staff_member_required
def handout_pdfs(request):
    volunteers = Volunteer.objects.order_by(
        'last',
        'first',
    )
    output = ''
    for volunteer in volunteers:
        context={
            'volunteer': volunteer,
            'recipient': volunteer.recipient,
            'map': map,
        }
        rendered = render_to_string('app/pages/handout.html', context)
        output += "<br>"+rendered
    pdf = pydf.generate_pdf(
        output,
        enable_smart_shrinking=False,
        orientation='Portrait',
        margin_top='10mm',
        margin_bottom='10mm',
    )
    content = ContentFile(pdf)
    return FileResponse(
        content,
        as_attachment=True,
        filename='handouts.pdf',
    )

@staff_member_required
def export_csv(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="export.csv"'
    vs = Volunteer.objects.order_by(
        'last',
        'first',
    )

    writer = csv.writer(response)
    writer.writerow([
        'Volunteer',
        'Phone',
        'Number',
        'Recipient',
        'Address',
        'Phone',
        'Email',
        'Dog',
        'Size',
    ])
    for v in vs:
        writer.writerow([
            v.name,
            v.phone,
            v.number,
            v.recipient.name,
            v.recipient.address,
            v.recipient.phone,
            v.recipient.email,
            v.recipient.is_dog,
            v.recipient.get_size_display(),
        ])
    return response
