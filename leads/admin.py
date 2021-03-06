from django.contrib import admin
from django.db import models
from django.forms import Textarea

from leads.models import LeadTag, LeadStatusCategory, LeadActivityCategory, TenantLead, HouseOwnerLead, \
    TenantLeadPermanentAddress, TenantLeadPreferredLocationAddress, TenantLeadActivity, HouseOwnerLeadPermanentAddress, \
    HouseOwnerLeadHouseAddress, HouseOwnerLeadActivity, LeadSourceCategory, TenantLeadSource, HouseOwnerLeadSource


@admin.register(LeadSourceCategory)
class LeadSourceCategoryAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'active')


@admin.register(LeadTag)
class LeadTagAdmin(admin.ModelAdmin):
    list_display = ('id', 'name')


@admin.register(LeadStatusCategory)
class LeadStatusCategoryAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'get_color_display')
    readonly_fields = ('get_color_display',)
    ordering = ('id',)


@admin.register(LeadActivityCategory)
class LeadActivityCategoryAdmin(admin.ModelAdmin):
    list_display = ('id', 'name')


class TenantLeadSourceInline(admin.StackedInline):
    model = TenantLeadSource


class TenantLeadPermanentAddressInline(admin.StackedInline):
    model = TenantLeadPermanentAddress


class TenantLeadPreferredLocationAddressInline(admin.StackedInline):
    model = TenantLeadPreferredLocationAddress


class TenantLeadActivityTabularInline(admin.TabularInline):
    model = TenantLeadActivity
    fields = ('category', 'handled_by', 'created_at', 'updated_at', 'pre_status', 'post_status', 'remarks',
              'acknowledged_by_affiliate')
    readonly_fields = ('created_at', 'updated_at')
    extra = 0

    formfield_overrides = {
        models.TextField: {'widget': Textarea(attrs={'rows': 3, 'cols': 40})},
    }


@admin.register(TenantLead)
class TenantLeadAdmin(admin.ModelAdmin):
    list_display = ('id', 'zoho_id', 'name', 'phone_no', 'created_by', 'created_at', 'updated_at', 'source', 'status',
                    'referral_id')
    search_fields = ('name', 'phone_no')
    list_filter = ('source__category', 'status')
    inlines = (
        TenantLeadSourceInline,
        TenantLeadPermanentAddressInline,
        TenantLeadPreferredLocationAddressInline,
        TenantLeadActivityTabularInline,
    )

    def get_inline_instances(self, request, obj=None):
        # Return no inlines when obj is being created
        if not obj:
            return []
        else:
            return super(TenantLeadAdmin, self).get_inline_instances(request, obj)


class HouseOwnerLeadSourceInline(admin.StackedInline):
    model = HouseOwnerLeadSource


class HouseOwnerLeadPermanentAddressInline(admin.StackedInline):
    model = HouseOwnerLeadPermanentAddress


class HouseOwnerLeadHouseAddressInline(admin.StackedInline):
    model = HouseOwnerLeadHouseAddress


class HouseOwnerLeadActivityTabularInline(admin.TabularInline):
    model = HouseOwnerLeadActivity
    fields = ('category', 'handled_by', 'created_at', 'updated_at', 'pre_status', 'post_status', 'remarks')
    readonly_fields = ('created_at', 'updated_at')
    extra = 0

    formfield_overrides = {
        models.TextField: {'widget': Textarea(attrs={'rows': 3, 'cols': 40})},
    }


@admin.register(HouseOwnerLead)
class HouseOwnerLeadAdmin(admin.ModelAdmin):
    list_display = ('id', 'zoho_id', 'name', 'phone_no', 'created_by', 'created_at', 'updated_at', 'source', 'status',
                    'referral_id')

    inlines = (
        HouseOwnerLeadSourceInline,
        HouseOwnerLeadPermanentAddressInline,
        HouseOwnerLeadHouseAddressInline,
        HouseOwnerLeadActivityTabularInline,
    )

    def get_inline_instances(self, request, obj=None):
        # Return no inlines when obj is being created
        if not obj:
            return []
        else:
            return super(HouseOwnerLeadAdmin, self).get_inline_instances(request, obj)
