from datetime import timedelta

from decouple import config
from django.contrib.auth import logout, authenticate, login
from django.contrib.auth.decorators import user_passes_test, login_required
from django.contrib.auth.models import AnonymousUser
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponseRedirect, JsonResponse, Http404
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_http_methods
from django.views.generic import ListView

from lead_managers.filters import TenantLeadFilterSet, HouseOwnerLeadFilterSet
from lead_managers.models import LeadManager, OTP
from lead_managers.utils import TENANT_LEAD, HOUSE_OWNER_LEAD
from leads.models import TenantLead, HouseOwnerLead, LeadStatusCategory, LeadSourceCategory, TenantLeadSource, \
    HouseOwnerLeadSource, LeadActivityCategory, TenantLeadActivity, HouseOwnerLeadActivity
from leads.utils import STATUS_NOT_ATTEMPTED, TENANT_LEAD_STATUS_CATEGORIES, OWNER_LEAD_STATUS_CATEGORIES
from utility.form_field_utils import get_number, get_datetime
from utility.sms_utils import generate_otp

LOGIN_URL = '/login/'


def is_lead_manager(user):
    return LeadManager.objects.filter(user=user).count()


lead_manager_login_test = user_passes_test(is_lead_manager, login_url=LOGIN_URL)


def lead_manager_login_required(view):
    decorated_view = login_required(lead_manager_login_test(view), login_url=LOGIN_URL)
    return decorated_view


class LeadManagerLoginRequiredMixin(object):

    @method_decorator(lead_manager_login_required)
    def dispatch(self, *args, **kwargs):
        return super(LeadManagerLoginRequiredMixin, self).dispatch(*args, **kwargs)


def logout_view(request):
    logout(request)
    request.session.flush()
    request.user = AnonymousUser
    return HttpResponseRedirect(reverse(home_page))


def login_view(request):
    error_msg = None
    logout(request)
    if request.POST:
        username, password = request.POST['username'], request.POST['password']
        user = authenticate(username=username, password=password)
        if user is not None:
            if is_lead_manager(user):
                if user.is_active:
                    login(request, user)
                    next_page = request.GET.get('next')
                    if next_page:
                        return HttpResponseRedirect(next_page)
                    else:
                        return HttpResponseRedirect(reverse(home_page))
            else:
                error_msg = 'You are not a Leads Manager.'
        else:
            error_msg = 'Username and Password do not match.'
    return render(request, 'login_page.html', {'error': error_msg})


@require_http_methods(['GET', 'POST'])
def reset_password_view(request):
    if request.method == 'GET':
        return render(request, 'reset_password_page.html')
    else:
        try:
            lead_manager = LeadManager.objects.get(user=request.user)
        except LeadManager.DoesNotExist:
            return JsonResponse({'error': "Some error occurred. Please refresh the page"}, status=500)

        lead_manager.user.password = request.POST['password']
        return JsonResponse({'detail': 'done'})


@require_http_methods(['POST'])
def generate_otp_view(request):
    phone_no = request.POST.get('phone_no')
    try:
        lead_manager = LeadManager.objects.get(phone_no=phone_no)
    except LeadManager.DoesNotExist:
        return JsonResponse({'error': "Invalid Phone Number"}, status=500)
    generate_otp(lead_manager.phone_no, lead_manager.user.first_name)
    return JsonResponse({'detail': 'done'})


@require_http_methods(['POST'])
def login_otp_view(request):
    phone_no = request.POST.get('phone_no')
    try:
        lead_manager = LeadManager.objects.get(phone_no=phone_no)
    except LeadManager.DoesNotExist:
        return JsonResponse({'error': "Invalid Phone Number"}, status=500)
    try:
        otp = OTP.objects.get(phone_no=phone_no, password=request.POST.get('password'))
    except OTP.DoesNotExist:
        return JsonResponse({'error': "Wrong OTP"}, status=500)

    if otp.timestamp >= timezone.now() - timedelta(minutes=10):
        login(request, lead_manager.user)
    else:
        return JsonResponse({"error": "OTP has expired"}, status=500)
    return JsonResponse({'detail': 'done'})


@lead_manager_login_required
@require_http_methods(['GET'])
def home_page(request):
    return render(request, 'home_page.html')


@lead_manager_login_required
@require_http_methods(['GET', 'POST'])
def new_lead_form_view(request):
    if request.method == 'GET':
        lead_source_categories = LeadSourceCategory.objects.filter(active=True).values_list('name', flat=True)
        return render(request, 'new_lead_form.html', {'lead_source_categories': lead_source_categories,
                                                      'GOOGLE_MAPS_API_KEY': config('GOOGLE_MAPS_API_KEY')
                                                      })

    if request.method == 'POST':
        lead_manager = LeadManager.objects.get(user=request.user)
        data = request.POST
        name = data.get('name')
        gender = data.get('gender')
        phone_no = data.get('phone_no')
        email = data.get('email')
        permanent_address = data.get('permanent_address')
        if len(data.get('new_source_category')):
            source_category, _ = LeadSourceCategory.objects.get_or_create(name=data.get('new_source_category'))
        else:
            source_category = LeadSourceCategory.objects.filter(name=data.get('source_category')).first()
        source_name = data.get('source_name')

        if data['lead_type'] == TENANT_LEAD:
            if TenantLead.objects.filter(phone_no=phone_no).exists():
                return JsonResponse({'detail': "Tenant Lead with this phone number already exists."})

            expected_rent_min = get_number(data.get('expected_rent_min'))
            expected_rent_max = get_number(data.get('expected_rent_max'))
            expected_movein_start = get_datetime(data.get('expected_movein_start'))
            expected_movein_end = get_datetime(data.get('expected_movein_end'))
            space_type = data.get('space_type')
            space_subtype = data.get('space_subtype')
            preferred_location = data.get('preferred_location')
            accomodation_for = data.getlist('accomodation_for')
            lead = TenantLead.objects.create(name=name, gender=gender, phone_no=phone_no, email=email,
                                             expected_rent_min=expected_rent_min, expected_rent_max=expected_rent_max,
                                             expected_movein_start=expected_movein_start,
                                             expected_movein_end=expected_movein_end, space_type=space_type,
                                             space_subtype=space_subtype, accomodation_for=accomodation_for,
                                             created_by=lead_manager)
            lead.preferred_location.street_address = preferred_location
            lead.preferred_location.save()

        elif data['lead_type'] == HOUSE_OWNER_LEAD:
            if HouseOwnerLead.objects.filter(phone_no=phone_no).exists():
                return JsonResponse({'detail': "House Owner Lead with this phone number already exists."})

            house_type = data.get('house_type')
            furnish_type = data.get('furnish_type')
            accomodation_allowed = data.getlist('accomodation_allowed')
            current_stay_status = data.get('current_stay_status')
            bhk_count = get_number(data.get('bhk_count'))
            current_rent = get_number(data.get('current_rent'))
            current_security_deposit = get_number(data.get('current_security_deposit'))
            expected_rent = get_number(data.get('expected_rent'))
            expected_security_deposit = get_number(data.get('expected_security_deposit'))
            shared_rooms_count = get_number(data.get('shared_rooms_count'))
            total_beds_count = get_number(data.get('total_beds_count'))
            private_rooms_count = get_number(data.get('private_rooms_count'))
            flats_count = get_number(data.get('flats_count'))
            house_address = data.get('house_address')
            lead = HouseOwnerLead.objects.create(name=name, gender=gender, phone_no=phone_no, email=email,
                                                 house_type=house_type, furnish_type=furnish_type,
                                                 accomodation_allowed=accomodation_allowed,
                                                 current_stay_status=current_stay_status, bhk_count=bhk_count,
                                                 current_rent=current_rent,
                                                 current_security_deposit=current_security_deposit,
                                                 expected_rent=expected_rent,
                                                 expected_security_deposit=expected_security_deposit,
                                                 shared_rooms_count=shared_rooms_count,
                                                 total_beds_count=total_beds_count,
                                                 private_rooms_count=private_rooms_count, flats_count=flats_count,
                                                 created_by=lead_manager)
            lead.house_address.street_address = house_address
            lead.house_address.save()
        else:
            return JsonResponse({'detail': 'Wrong lead type'})

        lead.managed_by.add(lead_manager)
        lead.permanent_address.street_address = permanent_address
        lead.permanent_address.save()
        lead.source.category = source_category
        lead.source.name = source_name
        lead.source.save()

        return JsonResponse({'detail': 'done'})


# noinspection PyAttributeOutsideInit
class FilteredListView(LeadManagerLoginRequiredMixin, ListView):
    filterset_class = None

    def get_filterset(self, *args, **kwargs):
        if self.lead_type == TENANT_LEAD:
            return TenantLeadFilterSet(*args, **kwargs)
        else:
            return HouseOwnerLeadFilterSet(*args, **kwargs)

    def get_queryset(self):
        lead_manager = LeadManager.objects.get(user=self.request.user)
        if self.lead_status == STATUS_NOT_ATTEMPTED:
            query = Q(status__name=STATUS_NOT_ATTEMPTED)
        else:
            query = Q(managed_by=lead_manager)

        if self.lead_type == TENANT_LEAD:
            queryset = TenantLead.objects.select_related('source', 'status', 'permanent_address', 'preferred_location'
                                                         ).filter(query).order_by('-updated_at')
        elif self.lead_type == HOUSE_OWNER_LEAD:
            queryset = HouseOwnerLead.objects.select_related('source', 'status', 'permanent_address', 'house_address'
                                                             ).filter(query).order_by('-updated_at')
        else:
            queryset = None
        self.filterset = self.get_filterset(self.request.GET, queryset=queryset)
        return self.filterset.qs.distinct()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filterset'] = self.filterset
        return context

    def get(self, request, *args, **kwargs):
        self.lead_type = request.GET.get('type')
        self.lead_status = request.GET.get('status')

        self.object_list = self.get_queryset()
        allow_empty = self.get_allow_empty()

        if not allow_empty:
            if self.get_paginate_by(self.object_list) is not None and hasattr(self.object_list, 'exists'):
                is_empty = not self.object_list.exists()
            else:
                is_empty = not self.object_list
            if is_empty:
                raise Http404("Empty list and '%(class_name)s.allow_empty' is False." % {
                    'class_name': self.__class__.__name__,
                })
        context = self.get_context_data()
        context['lead_type'] = self.lead_type
        context['lead_status'] = self.lead_status
        context['lead_source_categories'] = LeadSourceCategory.objects.filter(active=True).values_list('name', flat=True)
        context['lead_status_categories'] = LeadStatusCategory.objects.all().values_list('name', flat=True)

        # Filtered Categories on the basis of lead type
        if self.lead_type == TENANT_LEAD:
            context['lead_status_categories'] = context['lead_status_categories'].filter(
                name__in=TENANT_LEAD_STATUS_CATEGORIES)

        elif self.lead_type == HOUSE_OWNER_LEAD:
            context['lead_status_categories'] = context['lead_status_categories'].filter(
                name__in=OWNER_LEAD_STATUS_CATEGORIES)

        return self.render_to_response(context)


class LeadListView(FilteredListView):
    paginate_by = 10
    template_name = 'leads_list_page.html'


@lead_manager_login_required
@require_http_methods(['POST'])
def lead_exists_view(request):
    phone_no = request.POST.get('phone_no')
    tenant_lead = TenantLead.objects.filter(phone_no=phone_no).first()
    house_owner_lead = HouseOwnerLead.objects.filter(phone_no=phone_no).first()
    data = {}
    if tenant_lead:
        data['tenant_lead'] = {
            'id': tenant_lead.id,
            'name': tenant_lead.name
        }
    else:
        data['tenant_lead'] = None
    if house_owner_lead:
        data['house_owner_lead'] = {
            'id': house_owner_lead.id,
            'name': house_owner_lead.name
        }
    else:
        data['house_owner_lead'] = None
    return JsonResponse(data)


@lead_manager_login_required
@require_http_methods(['GET'])
def lead_manage_view(request):
    lead_manager = LeadManager.objects.get(user=request.user)
    lead_source_categories = LeadSourceCategory.objects.filter(active=True).values_list('name', flat=True)
    lead_activity_categories = LeadActivityCategory.objects.all().values_list('name', flat=True)
    lead_status_categories = LeadStatusCategory.objects.all().values_list('name', flat=True)

    lead_type = request.GET.get('type')
    lead_id = get_number(request.GET.get('id'))

    if lead_type == TENANT_LEAD and lead_id:
        # Showing different Lead status categories for Tenant
        lead_status_categories = lead_status_categories.filter(name__in=TENANT_LEAD_STATUS_CATEGORIES)
        try:
            lead = TenantLead.objects.get(id=lead_id)
        except TenantLead.DoesNotExist:
            return render(request, 'lead_manage_page.html', {'msg': "No such lead found!"})

    elif lead_type == HOUSE_OWNER_LEAD and lead_id:
        # Showing different Lead status categories for Tenant
        lead_status_categories = lead_status_categories.filter(name__in=OWNER_LEAD_STATUS_CATEGORIES)
        try:
            lead = HouseOwnerLead.objects.get(id=lead_id)
        except HouseOwnerLead.DoesNotExist:
            return render(request, 'lead_manage_page.html', {'msg': "No such lead found!"})
    else:
        return render(request, 'lead_manage_page.html', {'msg': "No such lead found!"})

    lead_activities = lead.activities.filter(is_deleted=False).order_by('-id')

    return render(request, 'lead_manage_page.html', {'lead_type': lead_type,
                                                     'lead': lead,
                                                     'me': lead_manager,
                                                     'lead_activities': lead_activities,
                                                     'lead_source_categories': lead_source_categories,
                                                     'lead_activity_categories': lead_activity_categories,
                                                     'lead_status_categories': lead_status_categories})


@lead_manager_login_required
@require_http_methods(['POST'])
def lead_edit_form_view(request):
    lead_manager = LeadManager.objects.get(user=request.user)
    data = dict(request.POST)

    # convert 'None' to None
    for key, val in data.items():
        if val == ['None']:
            data[key] = None
        else:
            data[key] = val[0]

    lead_type = data.get('type')
    lead_id = get_number(data.get('id'))

    if lead_type == TENANT_LEAD and lead_id:
        try:
            lead = TenantLead.objects.get(id=lead_id, managed_by=lead_manager)
        except TenantLead.DoesNotExist:
            return JsonResponse({'detail': 'Lead not found'})
    elif lead_type == HOUSE_OWNER_LEAD and lead_id:
        try:
            lead = HouseOwnerLead.objects.get(id=lead_id, managed_by=lead_manager)
        except HouseOwnerLead.DoesNotExist:
            return JsonResponse({'detail': 'Lead not found'})
    else:
        return JsonResponse({'detail': 'Lead not found'})

    lead.name = data.get('name')
    lead.phone_no = data.get('phone_no')
    lead.gender = data.get('gender')
    lead.email = data.get('email')
    lead.save()

    if not hasattr(lead, 'source'):
        if lead_type == TENANT_LEAD:
            TenantLeadSource(lead=lead).save()
        elif lead_type == HOUSE_OWNER_LEAD:
            HouseOwnerLeadSource(lead=lead).save()
    lead.source.category = LeadSourceCategory.objects.filter(name=data.get('source_category')).first()
    lead.source.name = data.get('source_name')
    lead.source.save()

    lead.permanent_address.street_address = data.get('permanent_street_address')
    lead.permanent_address.city = data.get('permanent_city')
    lead.permanent_address.state = data.get('permanent_state')
    lead.permanent_address.country = data.get('permanent_country')
    lead.permanent_address.save()

    if lead_type == TENANT_LEAD:
        lead.space_type = data.get('space_type')
        lead.space_subtype = data.get('space_subtype')
        lead.accomodation_for = request.POST.getlist('accomodation_for')
        lead.expected_rent_min = get_number(data.get('expected_rent_min'))
        lead.expected_rent_max = get_number(data.get('expected_rent_max'))
        lead.expected_movein_start = get_datetime(data.get('expected_movein_start'))
        lead.expected_movein_end = get_datetime(data.get('expected_movein_end'))
        lead.save()

        lead.preferred_location.street_address = data.get('preferred_location_street_address')
        lead.preferred_location.city = data.get('preferred_location_city')
        lead.preferred_location.state = data.get('preferred_location_state')
        lead.preferred_location.country = data.get('preferred_location_country')
        lead.preferred_location.save()

    elif lead_type == HOUSE_OWNER_LEAD:
        lead.house_type = data.get('house_type')
        lead.furnish_type = data.get('furnish_type')
        lead.accomodation_allowed = request.POST.getlist('accomodation_allowed')
        lead.current_stay_status = data.get('current_stay_status')
        lead.bhk_count = get_number(data.get('bhk_count'))
        lead.current_rent = get_number(data.get('current_rent'))
        lead.current_security_deposit = get_number(data.get('current_security_deposit'))
        lead.expected_rent = get_number(data.get('expected_rent'))
        lead.expected_security_deposit = get_number(data.get('expected_security_deposit'))
        lead.shared_rooms_count = get_number(data.get('shared_rooms_count'))
        lead.total_beds_count = get_number(data.get('total_beds_count'))
        lead.private_rooms_count = get_number(data.get('private_rooms_count'))
        lead.flats_count = get_number(data.get('flats_count'))
        lead.save()

        lead.house_address.street_address = data.get('house_street_address')
        lead.house_address.city = data.get('house_city')
        lead.house_address.state = data.get('house_state')
        lead.house_address.country = data.get('house_country')
        lead.house_address.save()

    return JsonResponse({'detail': 'done'})


@lead_manager_login_required
@require_http_methods(['POST'])
def new_lead_activity_form_view(request):
    lead_manager = LeadManager.objects.get(user=request.user)
    data = request.POST

    lead_type = data.get('lead_type')
    lead_id = get_number(data.get('lead_id'))

    if lead_type == TENANT_LEAD and lead_id:
        try:
            lead = TenantLead.objects.get(id=lead_id, managed_by=lead_manager)
        except TenantLead.DoesNotExist:
            return JsonResponse({'detail': 'Lead not found'})
    elif lead_type == HOUSE_OWNER_LEAD and lead_id:
        try:
            lead = HouseOwnerLead.objects.get(id=lead_id, managed_by=lead_manager)
        except HouseOwnerLead.DoesNotExist:
            return JsonResponse({'detail': 'Lead not found'})
    else:
        return JsonResponse({'detail': 'Lead not found'})

    if len(data.get('new_category')):
        category, _ = LeadActivityCategory.objects.get_or_create(name=data.get('new_category'))
    else:
        category = LeadActivityCategory.objects.filter(name=data.get('category')).first()
    post_status = LeadStatusCategory.objects.filter(name=data.get('post_status')).first()
    remarks = data.get('remarks')

    if category and post_status:
        if lead_type == TENANT_LEAD:
            TenantLeadActivity.objects.create(lead=lead, handled_by=lead_manager, category=category,
                                              post_status=post_status, remarks=remarks)
        elif lead_type == HOUSE_OWNER_LEAD:
            HouseOwnerLeadActivity.objects.create(lead=lead, handled_by=lead_manager, category=category,
                                                  post_status=post_status, remarks=remarks)
    return JsonResponse({'detail': 'done'})


@lead_manager_login_required
@require_http_methods(['POST'])
def lead_activity_form_edit_view(request):
    lead_manager = LeadManager.objects.get(user=request.user)
    data = request.POST
    lead_type = data.get('lead_type')

    if lead_type == TENANT_LEAD:
        try:
            lead_activity = TenantLeadActivity.objects.get(id=data.get('id'), lead__managed_by=lead_manager,
                                                           is_deleted=False)
        except TenantLeadActivity.DoesNotExist:
            return JsonResponse({'detail': 'Lead Activity not found'})
    elif lead_type == HOUSE_OWNER_LEAD:
        try:
            lead_activity = HouseOwnerLeadActivity.objects.get(id=data.get('id'), lead__managed_by=lead_manager,
                                                               is_deleted=False)
        except TenantLeadActivity.DoesNotExist:
            return JsonResponse({'detail': 'Lead Activity not found'})
    else:
        return JsonResponse({'detail': 'Lead Activity not found'})

    if data.get('remarks'):
        lead_activity.remarks = data.get('remarks')
        lead_activity.save()

    if data.get('delete'):
        lead_activity.is_deleted = True
        lead_activity.save()

    return JsonResponse({'detail': 'done'})


@lead_manager_login_required
@require_http_methods(['POST'])
def add_lead_manager_view(request):
    lead_manager = LeadManager.objects.get(user=request.user)
    data = request.POST

    lead_type = data.get('lead_type')
    lead_id = get_number(data.get('lead_id'))

    if lead_type == TENANT_LEAD and lead_id:
        try:
            lead = TenantLead.objects.get(id=lead_id)
        except TenantLead.DoesNotExist:
            return JsonResponse({'detail': 'Lead not found'})
    elif lead_type == HOUSE_OWNER_LEAD and lead_id:
        try:
            lead = HouseOwnerLead.objects.get(id=lead_id)
        except HouseOwnerLead.DoesNotExist:
            return JsonResponse({'detail': 'Lead not found'})
    else:
        return JsonResponse({'detail': 'Lead not found'})

    lead.managed_by.add(lead_manager)
    return JsonResponse({'detail': 'done'})


@lead_manager_login_required
@require_http_methods(['GET'])
def latest_activities_view(request):
    lead_type = request.GET.get('type')
    page = get_number(request.GET.get('page', 1))

    if lead_type == TENANT_LEAD:
        activities = TenantLeadActivity.objects.order_by('-id')
    elif lead_type == HOUSE_OWNER_LEAD:
        activities = HouseOwnerLeadActivity.objects.order_by('-id')
    else:
        activities = None
    paginator = Paginator(activities, 10)
    activities = paginator.get_page(page)
    return render(request, 'lead_activities.html', {'activities': activities, 'lead_type': lead_type})
