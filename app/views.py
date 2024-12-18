from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db import IntegrityError
from django.core.exceptions import ValidationError
from django.http import FileResponse, HttpResponse, JsonResponse
from . import settings
import os
from .models import RecordType, Stage, CoreField, CustomField, Role
import re
from . import export
from django.contrib.auth.decorators import login_required, user_passes_test
import tempfile
import shutil
import json
from .export import export_record_fields
from azure.data.tables import TableServiceClient
from azure.core.exceptions import AzureError
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_protect
from datetime import datetime
import logging
import csv
from io import StringIO

from .utils.record_type_validator import (
    test_validate_record_type_from_json,
    validate_record_type
)
from .utils.record_field_validator import test_validate_record_fields_from_json
from .utils.csv_parser import parse_csv_to_json
from .utils.constants import (
    CORE_FIELDS,
    IGNORED_SP_FIELDS,
    IGNORED_STATE_FIELDS
)
from .forms import CustomFieldForm, RoleForm

logger = logging.getLogger('django.request')

def index(request):
    logger.info(f"Index view accessed - GET params: {request.GET}")
    try:
        show_disabled = request.GET.get('show_disabled') == 'on'
        record_types = RecordType.objects.all()
        
        if not show_disabled:
            record_types = record_types.filter(is_enabled=True)
        
        # Group record types by category
        categories = {}
        for record_type in record_types:
            if record_type.category not in categories:
                categories[record_type.category] = []
            categories[record_type.category].append(record_type)
        
        logger.info(f"Found {len(record_types)} record types")
        
        return render(request, 'index.html', {
            'categories': categories,
            'show_disabled': show_disabled
        })
    except Exception as e:
        logger.error(f"Error in index view: {str(e)}", exc_info=True)
        raise
    
    logger.debug("View execution completed")
    return response

def create_record_type(request):
    if request.method == 'POST':
        record_type = request.POST.get('record_type')
        prefix = request.POST.get('prefix', '').upper()
        description = request.POST.get('description', '')
        colour = request.POST.get('colour', '#000000')
        category = request.POST.get('category', '').strip()
        order = request.POST.get('order', 0)
        enable_correspondence = request.POST.get('enable_correspondence') == 'on'
        correspondence_mandatory = request.POST.get('correspondence_mandatory') == 'on'
        
        try:
            order = int(order)
        except (ValueError, TypeError):
            order = 0
        
        # Validate category (alphabetical chars and spaces only)
        if not re.match(r'^[A-Za-z\s]{1,50}$', category):
            messages.error(request, 'Category must contain only letters and spaces (max 50 characters).')
            return redirect('index')

        if record_type and prefix and len(prefix) <= 4 and len(description) <= 250:
            try:
                new_record_type = RecordType.objects.create(
                    name=record_type,
                    prefix=prefix,
                    description=description,
                    colour=colour.replace('#', ''),
                    category=category,
                    order=order,
                    enable_correspondence=enable_correspondence,
                    correspondence_mandatory=correspondence_mandatory
                )
                
                # Map string field types to their corresponding integer values
                field_type_map = {
                    'text': 1,
                    'dropdown_single': 2,
                    'dropdown_multi': 3,
                    'single_user': 4,
                    'date': 5,
                    'time': 6,
                    'datetime': 7,
                    'multi_user': 8,
                    'textarea': 9,
                    'radio': 10
                }
                
                # Create default stages
                default_stages = [
                    'Initiate',
                    'Prepare and Review',
                    'Recommend',
                    'Make Decision',
                    'Implement and Close',
                    'Closed'
                ]
                stages = {}
                for i, stage_name in enumerate(default_stages):
                    stages[stage_name] = Stage.objects.create(
                        record_type=new_record_type, 
                        name=stage_name, 
                        order=i
                    )
                
                # Create default core fields with correct field_type mapping
                CoreField.objects.create(
                    record_type=new_record_type,
                    name='Title',
                    display_name='Title',
                    field_type=field_type_map['text']
                )
                
                # Add the new Topic field
                CoreField.objects.create(
                    record_type=new_record_type,
                    name='ABCTopicSummary',
                    display_name='Topic',
                    field_type=field_type_map['text'],
                    is_active=False,  # Hidden by default
                    is_mandatory=False,  # Not required
                    visible_on_create=False  # Synced with is_active
                )
                
                # Add the new Request From field
                CoreField.objects.create(
                    record_type=new_record_type,
                    name='ABCRequestFrom',
                    display_name='Requested by',
                    field_type=field_type_map['radio'],
                    term_set='Request From',
                    is_active=False,
                    is_mandatory=False,
                    visible_on_create=False
                )
                
                # Add the new Date Requested field
                CoreField.objects.create(
                    record_type=new_record_type,
                    name='ABCDateRequested',
                    display_name='Date requested',
                    field_type=field_type_map['date'],
                    is_active=False,  # Hidden by default
                    is_mandatory=False,  # Not required
                    visible_on_create=False  # Synced with is_active
                )
                
                # Add the new Timeframe field
                CoreField.objects.create(
                    record_type=new_record_type,
                    name='ABCTimeframe',
                    display_name='Timeframe',
                    field_type=field_type_map['radio'],
                    description="Due dates populate automatically based on the timeframe you select. They can be edited anytime.",
                    term_set='Timeframe',
                    is_active=False,
                    is_mandatory=False,
                    visible_on_create=False
                )
                
                # Add the Decision Category field
                CoreField.objects.create(
                    record_type=new_record_type,
                    name='ABCDecisionCategory',
                    display_name='Decision Category',
                    field_type=field_type_map['dropdown_single'],
                    description="Select based on who the Decision Maker is.",
                    term_set='Decision Category',
                    is_active=False,
                    is_mandatory=False,
                    visible_on_create=False
                )
                
                # Add ABCOrgLevel1
                CoreField.objects.create(
                    record_type=new_record_type,
                    name='ABCOrgLevel1',
                    display_name='Organisation',
                    field_type=field_type_map['dropdown_single'],
                    description="Select the organisation that will prepare the record.",
                    is_active=False,
                    is_mandatory=True,
                    visible_on_create=True
                )
                
                # Add ABCOrgLevel2
                CoreField.objects.create(
                    record_type=new_record_type,
                    name='ABCOrgLevel2',
                    display_name='Organisation level 1',
                    field_type=field_type_map['dropdown_single'],
                    description="Select the relevant group or division (e.g. Economic Policy and State Productivity).",
                    is_active=False,
                    is_mandatory=True,
                    visible_on_create=True
                )
                
                # Add ABCOrgLevel3
                CoreField.objects.create(
                    record_type=new_record_type,
                    name='ABCOrgLevel3',
                    display_name='Organisation level 2',
                    field_type=field_type_map['dropdown_single'],
                    description="Select the relevant branch (e.g. Cabinet Office).",
                    is_active=False,
                    is_mandatory=False,
                    visible_on_create=False
                )
                
                # Add ABCOrgLevel4
                CoreField.objects.create(
                    record_type=new_record_type,
                    name='ABCOrgLevel4',
                    display_name='Organisation level 3',
                    field_type=field_type_map['dropdown_single'],
                    description="Select the relevant team (e.g. People and Culture).",
                    is_active=False,
                    is_mandatory=False,
                    visible_on_create=False
                )
                
                # Create default roles
                default_roles = [
                    {
                        'name': 'ABCInitiator',
                        'display_name': 'Initiator',
                        'stage': 'Initiate',
                        'description': 'Mandatory role who initiates records and sends it to an Allocator or Accountable Executive Officer for action. Anyone can initiate a record.',
                        'is_mandatory': True
                    },
                    {
                        'name': 'ABCLeadAuthor',
                        'display_name': 'Lead Author',
                        'stage': 'Prepare and Review',
                        'description': 'Mandatory role who prepares the record\'s content and coordinates input from Collaborators and Liaisons. They\'re subject matter experts, such as a Policy Officer or Project Manager.',
                        'is_mandatory': True
                    },
                    {
                        'name': 'ABCRecommendRecommender',
                        'display_name': 'Recommender',
                        'stage': 'Recommend',
                        'description': 'Mandatory role who recommends if the record should proceed. For Ministerial records the Recommender is the relevant Deputy Secretary. For all other records it is the relevant line executive.',
                        'is_mandatory': True
                    },
                    {
                        'name': 'ABCDecisionMaker',
                        'display_name': 'Decision Maker',
                        'stage': 'Make Decision',
                        'description': 'Mandatory role who makes the final decision on the record.',
                        'is_mandatory': True
                    },
                    {
                        'name': 'ABCCompleter',
                        'display_name': 'Completer',
                        'stage': 'Implement and Close',
                        'description': 'Mandatory role who marks the record as closed. Usually a person from the responsible branch, such as an Executive Assistant or Lead Author.',
                        'is_mandatory': True
                    }
                ]
                
                for i, role_data in enumerate(default_roles):
                    Role.objects.create(
                        record_type=new_record_type,
                        name=role_data['name'],
                        display_name=role_data['display_name'],
                        description=role_data['description'],
                        stage=stages[role_data['stage']],
                        order=i,
                        is_mandatory=role_data['is_mandatory']
                    )

                messages.success(request, f'Record type "{record_type}" created successfully!')
                return redirect('record_fields', record_type=record_type)
            except IntegrityError as e:
                if 'unique constraint' in str(e).lower():
                    if 'name' in str(e).lower():
                        messages.error(request, f'A record type with the name "{record_type}" already exists.')
                    elif 'prefix' in str(e).lower():
                        messages.error(request, f'A record type with the prefix "{prefix}" already exists.')
                    else:
                        messages.error(request, 'A record type with this name or prefix already exists.')
                else:
                    messages.error(request, 'An error occurred while creating the record type.')
        else:
            messages.error(request, 'Please enter valid record type details.')
    
    return render(request, 'create_record_type.html')

def record_fields(request, record_type):
    logger.info(f"Record fields view accessed for type: {record_type}")
    record_type_obj = get_object_or_404(RecordType, name=record_type)
    stages = record_type_obj.stages.all().order_by('order')
    show_inactive = request.GET.get('show_inactive') == 'on'
    
    logger.info(f"Show inactive: {show_inactive}")
    
    # Group roles by stage
    roles_by_stage = {}
    for stage in stages:
        roles_by_stage[stage] = stage.roles.all().order_by('name')
    
    return render(request, 'record_fields.html', {
        'record_type': record_type_obj,
        'custom_fields': record_type_obj.custom_fields.all(),
        'stages': stages,
        'core_fields': record_type_obj.core_fields.all(),
        'roles_by_stage': roles_by_stage,
        'show_inactive': show_inactive
    })

def new_custom_field(request, record_type):
    record_type_obj = get_object_or_404(RecordType, name=record_type)
    
    if request.method == 'POST':
        post_data = request.POST.copy()
        post_data['name'] = post_data.get('field_name')
        form = CustomFieldForm(post_data, record_type=record_type_obj)
        
        if form.is_valid():
            try:
                custom_field = form.save(commit=False)
                custom_field.record_type = record_type_obj
                custom_field.full_clean()
                custom_field.save()
                messages.success(request, f'Field "{form.cleaned_data["display_name"]}" created successfully!')
                return redirect('record_fields', record_type=record_type)
            except ValidationError as e:
                messages.error(request, str(e))
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
    else:
        form = CustomFieldForm(record_type=record_type_obj, initial={'wizard_position': 0})

    return render(request, 'new_custom_field.html', {
        'form': form,
        'record_type': record_type,
        'field_types': CustomField.FIELD_TYPES
    })

def edit_custom_field(request, record_type, field_name):
    record_type_obj = get_object_or_404(RecordType, name=record_type)
    custom_field = get_object_or_404(CustomField, record_type=record_type_obj, name=field_name)
    
    if request.method == 'POST':
        if 'delete' in request.POST:
            custom_field.delete()
            messages.success(request, f'Field "{field_name}" deleted successfully.')
            return redirect('record_fields', record_type=record_type)
        
        form = CustomFieldForm(request.POST, instance=custom_field, record_type=record_type_obj)
        if form.is_valid():
            try:
                form.save()
                messages.success(request, f'Field "{form.cleaned_data["display_name"]}" updated successfully.')
                return redirect('record_fields', record_type=record_type)
            except ValidationError as e:
                messages.error(request, str(e))
    else:
        form = CustomFieldForm(instance=custom_field, record_type=record_type_obj)
    
    return render(request, 'edit_custom_field.html', {
        'form': form,
        'record_type': record_type_obj,
        'field': custom_field,
        'field_types': CustomField.FIELD_TYPES
    })

def edit_record_type(request, record_type):
    record_type_obj = get_object_or_404(RecordType, name=record_type)
    
    if request.method == 'POST':
        new_record_type = request.POST.get('record_type')
        new_prefix = request.POST.get('prefix', '').upper()
        new_description = request.POST.get('description', '')
        new_colour = request.POST.get('colour', '#000000')
        new_category = request.POST.get('category', '').strip()
        new_order = request.POST.get('order', record_type_obj.order)
        is_enabled = request.POST.get('is_enabled') == 'on'
        
        try:
            new_order = int(new_order)
        except (ValueError, TypeError):
            new_order = record_type_obj.order
            
        # Validate category
        if not re.match(r'^[A-Za-z\s]{1,50}$', new_category):
            messages.error(request, 'Category must contain only letters and spaces (max 50 characters).')
            return render(request, 'edit_record_type.html', {'record_type': record_type_obj})

        if new_record_type and new_prefix and len(new_prefix) <= 4 and len(new_description) <= 250:
            record_type_obj.name = new_record_type
            record_type_obj.prefix = new_prefix
            record_type_obj.description = new_description
            record_type_obj.colour = new_colour
            record_type_obj.category = new_category
            record_type_obj.order = new_order
            record_type_obj.is_enabled = is_enabled
            record_type_obj.save()
            
            messages.success(request, f'Record type updated successfully!')
            return redirect('record_fields', record_type=new_record_type)
        else:
            messages.error(request, 'Please enter valid record type details.')
    
    return render(request, 'edit_record_type.html', {'record_type': record_type_obj})

def edit_stages(request, record_type):
    record_type_obj = get_object_or_404(RecordType, name=record_type)
    error_data = None
    
    # Get validation rules from Stage model
    stage_name_max_length = Stage._meta.get_field('name').max_length
    stage_name_pattern = Stage.get_name_pattern()
    stage_name_regex = Stage.get_name_regex()
    
    if request.method == 'POST':
        new_stages_data = request.POST.getlist('stages')
        existing_stages = list(Stage.objects.filter(record_type=record_type_obj).order_by('order'))
        
        # If number of stages has changed, check for roles on stages that would be deleted
        if len(new_stages_data) < len(existing_stages):
            for stage in existing_stages:
                if stage.name not in new_stages_data and stage.roles.exists():
                    # Get all roles for this stage
                    roles = stage.roles.all()
                    error_data = {
                        'stage': stage,
                        'roles': roles
                    }
                    break
        
        if not error_data:
            # Update existing stages
            for index, (stage, new_name) in enumerate(zip(existing_stages, new_stages_data)):
                if stage.name != new_name.strip():
                    stage.name = new_name.strip()
                if stage.order != index:
                    stage.order = index
                stage.save()
            
            # Add any new stages
            for index, new_name in enumerate(new_stages_data[len(existing_stages):], start=len(existing_stages)):
                if new_name.strip():
                    Stage.objects.create(
                        record_type=record_type_obj,
                        name=new_name.strip(),
                        order=index
                    )
            
            messages.success(request, 'Stages updated successfully!')
            return redirect('record_fields', record_type=record_type)
    
    stages = Stage.objects.filter(record_type=record_type_obj).order_by('order')
    return render(request, 'edit_stages.html', {
        'record_type': record_type_obj,
        'stages': stages,
        'error_data': error_data,
        'stage_name_max_length': stage_name_max_length,
        'stage_name_pattern': stage_name_pattern,
        'stage_name_regex': stage_name_regex,
    })

def edit_core_field(request, record_type, field_name):
    record_type_obj = get_object_or_404(RecordType, name=record_type)
    core_field = get_object_or_404(CoreField, record_type=record_type_obj, name=field_name)
    
    if request.method == 'POST':
        display_name = request.POST.get('display_name')
        description = request.POST.get('description')
        
        if display_name:
            core_field.display_name = display_name
            
            # Handle description for all editable fields
            if field_name in ['title', 'ABCTopicSummary', 'ABCRequestFrom', 'ABCDateRequested', 
                            'ABCTimeframe', 'ABCDecisionCategory', 'ABCOrgLevel1', 'ABCOrgLevel2',
                            'ABCOrgLevel3', 'ABCOrgLevel4']:
                core_field.description = description
                    
            # Handle additional fields for Topic, Request From, Date Requested, Timeframe, Decision Category, and Org Level 3/4
            if field_name in ['ABCTopicSummary', 'ABCRequestFrom', 'ABCDateRequested', 'ABCTimeframe', 
                            'ABCDecisionCategory', 'ABCOrgLevel3', 'ABCOrgLevel4']:
                is_active = request.POST.get('is_active') == 'on'
                is_mandatory = request.POST.get('is_mandatory') == 'on'
                
                # If mandatory is true, force active to be true
                if is_mandatory and not is_active:
                    is_active = True
                    messages.info(request, 'Field has been set to active because it is required.')
                
                core_field.is_active = is_active
                core_field.visible_on_create = is_active  # Sync with is_active
                core_field.is_mandatory = is_mandatory
                
                # Handle term_set for fields that need it
                if field_name in ['ABCRequestFrom', 'ABCTimeframe', 'ABCDecisionCategory']:
                    term_set = request.POST.get('term_set')
                    if term_set:
                        core_field.term_set = term_set
            
            core_field.save()
            messages.success(request, f'Core field "{field_name}" updated successfully.')
            return redirect('record_fields', record_type=record_type)
        else:
            messages.error(request, 'Please enter a valid display name.')
    
    return render(request, 'edit_core_field.html', {
        'record_type': record_type_obj,
        'field': core_field,
        'is_title_field': field_name == 'title'
    })

def delete_record_type(request, record_type):
    record_type_obj = get_object_or_404(RecordType, name=record_type)
    
    if request.method == 'POST':
        record_type_obj.delete()
        messages.success(request, f'Record type "{record_type}" has been deleted successfully.')
        return redirect('index')
    
    return render(request, 'delete_record_type.html', {'record_type': record_type_obj})

def add_role(request, record_type):
    record_type_obj = get_object_or_404(RecordType, name=record_type)
    stages = record_type_obj.stages.exclude(name='Closed')
    
    if request.method == 'POST':
        form = RoleForm(request.POST, record_type=record_type_obj)
        if form.is_valid():
            try:
                role = form.save(commit=False)
                role.record_type = record_type_obj
                role.save()
                messages.success(request, f'Role "{form.cleaned_data["display_name"]}" created successfully!')
                return redirect('record_fields', record_type=record_type)
            except ValidationError as e:
                messages.error(request, str(e))
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
    else:
        form = RoleForm(record_type=record_type_obj)

    return render(request, 'add_role.html', {
        'form': form,
        'record_type': record_type_obj,
        'stages': stages
    })

def edit_role(request, record_type, role_id):
    record_type_obj = get_object_or_404(RecordType, name=record_type)
    role = get_object_or_404(Role, id=role_id, record_type=record_type_obj)
    stages = record_type_obj.stages.exclude(name='Closed')
    
    if request.method == 'POST':
        if 'delete' in request.POST:
            role.delete()
            messages.success(request, f'Role "{role.display_name}" deleted successfully!')
            return redirect('record_fields', record_type=record_type)
        
        display_name = request.POST.get('display_name')
        stage_id = request.POST.get('stage')
        order = request.POST.get('order', role.order)
        description = request.POST.get('description', '')
        is_active = request.POST.get('is_active') == 'on'
        is_mandatory = request.POST.get('is_mandatory') == 'on'
        allow_multiple = request.POST.get('allow_multiple') == 'on'
        
        try:
            order = int(order)
        except (ValueError, TypeError):
            order = role.order
        
        if display_name and stage_id:
            try:
                stage = Stage.objects.get(id=stage_id, record_type=record_type_obj)
                if stage.name == 'Closed':
                    messages.error(request, 'Roles cannot be assigned to the Closed stage.')
                    return render(request, 'edit_role.html', {
                        'record_type': record_type_obj,
                        'role': role,
                        'stages': stages
                    })
                
                role.display_name = display_name
                role.stage = stage
                role.order = order
                role.description = description
                role.is_active = is_active
                role.is_mandatory = is_mandatory
                role.allow_multiple = allow_multiple
                role.save()
                
                messages.success(request, f'Role "{display_name}" updated successfully!')
                return redirect('record_fields', record_type=record_type)
            except Stage.DoesNotExist:
                messages.error(request, 'Invalid stage selected.')
        else:
            messages.error(request, 'Please fill in all fields.')
    
    return render(request, 'edit_role.html', {
        'record_type': record_type_obj,
        'role': role,
        'stages': stages
    })

def export_record_types(request):
    """View to handle record type export"""
    single_record_type = request.GET.get('record_type')
    export_format = request.GET.get('format', 'json')  # Default to JSON
    
    if single_record_type:
        selected_types = [single_record_type]
    else:
        selected_types = request.GET.getlist('types[]')
    
    if export_format == 'csv':
        # Create CSV response
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="record_types_export.csv"'
        
        writer = csv.writer(response)
        # Write headers
        writer.writerow(['PartitionKey', 'RowKey', 'Category', 'Color', 'IsActive', 
                        'IsCorrespondenceType', 'Order', 'Prefix', 'StagesJson'])
        
        # Get record types data
        record_types = RecordType.objects.filter(name__in=selected_types) if selected_types else RecordType.objects.all()
        
        # Write data rows
        for record in record_types:
            stages_json = json.dumps([{
                "Name": stage.name,
                "Order": stage.order
            } for stage in record.stages.all().order_by('order')])
            
            writer.writerow([
                'V1',
                f"{record.name} ({record.prefix})",
                record.category,
                record.colour,
                record.is_enabled,
                record.enable_correspondence,
                record.order,
                record.prefix,
                stages_json
            ])
        
        return response
    else:
        # Original JSON export logic
        with tempfile.NamedTemporaryFile(delete=False, suffix='.json') as tmp_file:
            filename = tmp_file.name
            export_data = export.export_record_types(selected_types if selected_types else None)
            shutil.copy2(export_data, filename)
            os.remove(export_data)
            
            response = FileResponse(
                open(filename, 'rb'),
                content_type='application/json',
                as_attachment=True,
                filename='record_types_export.json'
            )
            response._resource_closers.append(lambda: os.remove(filename))
            return response

def export_fields(request, record_type):
    """Export record fields as JSON or CSV"""
    record_type_obj = get_object_or_404(RecordType, name=record_type)
    fields = CustomField.objects.filter(record_type=record_type_obj)
    roles = Role.objects.filter(record_type=record_type_obj)
    core_fields = CoreField.objects.filter(record_type=record_type_obj)
    export_format = request.GET.get('format', 'json')  # Default to JSON
    
    if export_format == 'csv':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{record_type.lower().replace(" ", "_")}_fields.csv"'
        
        writer = csv.writer(response)
        # Add SysCategory to headers
        writer.writerow([
            'PartitionKey', 
            'RowKey', 
            'DisplayName', 
            'Description', 
            'FieldType',
            'FiledType',
            'IsActive',
            'IsRequired',
            'IsNotRequiredOnCreation',
            'NotEditable',
            'Order',
            'ShowInHeader',
            'WizardPosition',
            'DataSourceName',
            'Stages',
            'SysCategory'  # Added SysCategory
        ])
        
        # Get export data
        export_data = export_record_fields(record_type_obj, fields, roles, core_fields)
        
        # Write data rows
        for field in export_data:
            writer.writerow([
                f"{field.get('PartitionKey', '')} ({record_type_obj.prefix})",
                field.get('RowKey', ''),
                field.get('DisplayName', ''),
                field.get('Description', ''),
                field.get('FieldType', ''),
                field.get('FiledType', ''),
                field.get('IsActive', ''),
                field.get('IsRequired', ''),
                field.get('IsNotRequiredOnCreation', ''),
                field.get('NotEditable', ''),
                field.get('Order', ''),
                field.get('ShowInHeader', ''),
                field.get('WizardPosition', ''),
                field.get('DataSourceName', ''),
                field.get('Stages', ''),
                field.get('SysCategory', '')  # Added SysCategory
            ])
        
        return response
    else:
        # Original JSON export logic remains the same since export_record_fields will now include SysCategory
        export_data = export_record_fields(record_type_obj, fields, roles, core_fields)
        json_data = json.dumps(export_data, indent=2)
        
        response = HttpResponse(json_data, content_type='application/json')
        response['Content-Disposition'] = f'attachment; filename="{record_type.lower().replace(" ", "_")}_fields.json"'
        
        return response

def get_azure_table_service():
    """Helper function to get Azure Table Service client"""
    conn_str = settings.AZURE_STORAGE_CONNECTION_STRING
    if not conn_str:
        raise ValueError("Azure Storage connection string not configured")
    return TableServiceClient.from_connection_string(conn_str)

def handle_azure_request(func):
    """Decorator to handle Azure-related errors"""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except AzureError as e:
            return None, f"Error accessing Azure Storage: {str(e)}"
        except Exception as e:
            return None, f"Unexpected error: {str(e)}"
    return wrapper

@handle_azure_request
def get_table_list():
    """Get list of all Azure tables"""
    table_service = get_azure_table_service()
    return [table.name for table in table_service.list_tables()], None

@handle_azure_request
def get_table_data(table_name):
    """Get data from specified Azure table"""
    table_service = get_azure_table_service()
    table_client = table_service.get_table_client(table_name)
    
    entities = table_client.list_entities()
    data = []
    columns = set(['PartitionKey', 'RowKey', 'Timestamp'])
    
    for entity in entities:
        columns.update(entity.keys())
        data.append(dict(entity))
        
    return {
        'data': data,
        'columns': sorted(list(columns))
    }, None

def list_tables(request):
    """View to list all Azure tables"""
    tables, error_message = get_table_list()
    return render(request, 'tables/list_tables.html', {
        'tables': tables,
        'error_message': error_message
    })

def view_table_data(request, table_name):
    """View to display data from a specific Azure table"""
    result, error_message = get_table_data(table_name)
    
    context = {
        'table_name': table_name,
        'data': result.get('data', []) if result else [],
        'columns': result.get('columns', []) if result else [],
        'error_message': error_message
    }
    
    return render(request, 'tables/view_table.html', context)

@csrf_protect
@require_POST
def export_table_data(request, table_name):
    try:
        if not request.body:
            return HttpResponse(
                json.dumps({'error': 'No data received'}),
                status=400,
                content_type='application/json'
            )

        data = json.loads(request.body)
        records = data.get('records', [])
        
        if not records:
            return HttpResponse(
                json.dumps({'error': 'No records selected'}),
                status=400,
                content_type='application/json'
            )

        # Create the response with just the records array
        response = HttpResponse(
            json.dumps(records, indent=2),
            content_type='application/json'
        )
        response['Content-Disposition'] = f'attachment; filename="{table_name}_export.json"'
        return response
        
    except json.JSONDecodeError:
        return HttpResponse(
            json.dumps({'error': 'Invalid JSON data'}),
            status=400,
            content_type='application/json'
        )
    except Exception as e:
        return HttpResponse(
            json.dumps({'error': str(e)}),
            status=400,
            content_type='application/json'
        )

def test_validation(request):
    """View to test both RecordType and RecordFields validation"""
    logger.info(f"Test validation view accessed - Method: {request.method}")
    
    if request.method == 'POST':
        try:
            logger.info("Processing validation files")
            
            # Both files are required
            if 'record_types_file' not in request.FILES or 'record_fields_file' not in request.FILES:
                logger.warning("Missing required files")
                messages.error(request, "Both Record Types and Record Fields files are required")
                return render(request, 'test_validation.html')
            
            # Log file information
            logger.info(f"Record Types file: {request.FILES['record_types_file'].name}")
            logger.info(f"Record Fields file: {request.FILES['record_fields_file'].name}")
            
            record_type_results = []
            field_results = []
            record_types = []
            
            # Process Record Types file
            record_types_file = request.FILES['record_types_file']
            file_extension = record_types_file.name.split('.')[-1].lower()
            logger.info(f"Processing Record Types file: {record_types_file.name} ({file_extension})")
            
            with tempfile.NamedTemporaryFile(delete=False, suffix=f'.{file_extension}') as tmp_file:
                for chunk in record_types_file.chunks():
                    tmp_file.write(chunk)
                types_file_path = tmp_file.name
                logger.info(f"Created temporary file for Record Types: {types_file_path}")
            
            # Convert CSV to JSON if necessary
            if file_extension == 'csv':
                try:
                    logger.info("Converting Record Types CSV to JSON")
                    record_types_data = parse_csv_to_json(record_types_file, 'record_types')
                    # Write the converted JSON to the temp file
                    with open(types_file_path, 'w') as json_file:
                        json.dump(record_types_data, json_file)
                    logger.info("Successfully converted Record Types CSV to JSON")
                except ValueError as e:
                    logger.error(f"CSV conversion error: {str(e)}")
                    messages.error(request, f"Error in Record Types CSV: {str(e)}")
                    return render(request, 'test_validation.html')
            
            # Validate Record Types and collect valid record type names
            types_success, record_type_results = test_validate_record_type_from_json(types_file_path)
            logger.info(f"Record Types validation complete. Success: {types_success}")
            
            # Extract valid record type names
            with open(types_file_path, 'r') as file:
                types_data = json.load(file)
                record_types = [rt.get('RowKey') for rt in types_data]
            
            # Clean up temporary file
            os.unlink(types_file_path)
            
            # Process Record Fields file
            record_fields_file = request.FILES['record_fields_file']
            file_extension = record_fields_file.name.split('.')[-1].lower()
            logger.info(f"Processing Record Fields file: {record_fields_file.name} ({file_extension})")
            
            with tempfile.NamedTemporaryFile(delete=False, suffix=f'.{file_extension}') as tmp_file:
                for chunk in record_fields_file.chunks():
                    tmp_file.write(chunk)
                fields_file_path = tmp_file.name
                logger.info(f"Created temporary file for Record Fields: {fields_file_path}")
            
            # Convert CSV to JSON if necessary
            all_fields = None
            if file_extension == 'csv':
                try:
                    logger.info("Converting Record Fields CSV to JSON")
                    all_fields = parse_csv_to_json(record_fields_file, 'record_fields')
                    # Write the converted JSON to the temp file
                    with open(fields_file_path, 'w') as json_file:
                        json.dump(all_fields, json_file)
                    logger.info("Successfully converted Record Fields CSV to JSON")
                except ValueError as e:
                    logger.error(f"CSV conversion error: {str(e)}")
                    messages.error(request, f"Error in Record Fields CSV: {str(e)}")
                    return render(request, 'test_validation.html')
            
            # Read all fields for duplicate checking if not already loaded
            if all_fields is None:
                with open(fields_file_path, 'r') as file:
                    all_fields = json.load(file)
            
            # Validate Record Fields with record types list
            fields_success, field_results = test_validate_record_fields_from_json(
                fields_file_path,
                record_types=record_types,
                all_fields=all_fields
            )
            logger.info(f"Record Fields validation complete. Success: {fields_success}")
            
            # Clean up temporary file
            os.unlink(fields_file_path)
            
            # Determine overall success
            overall_success = types_success and fields_success
            logger.info(f"Overall validation complete. Success: {overall_success}")
            
            return render(request, 'test_validation.html', {
                'results': True,
                'success': overall_success,
                'record_type_results': record_type_results,
                'field_results': field_results
            })
            
        except Exception as e:
            logger.exception("Unexpected error in test_validation view")
            messages.error(request, f"Error processing files: {str(e)}")
            return render(request, 'test_validation.html')
    
    return render(request, 'test_validation.html')

def delete_record_types(request):
    if request.method == 'POST':
        record_type_names = request.POST.getlist('types[]')
        if record_type_names:
            for record_type_name in record_type_names:
                record_type_obj = get_object_or_404(RecordType, name=record_type_name)
                record_type_obj.delete()
                messages.success(request, f'Record type "{record_type_name}" has been deleted successfully.')
        else:
            messages.error(request, 'No record types selected for deletion.')
        return redirect('index')