from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db import IntegrityError
from django.core.exceptions import ValidationError  # Add this import
from .models import RecordType, Stage, CoreField, CustomField, Role
import re

def index(request):
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
    
    return render(request, 'index.html', {
        'categories': categories,
        'show_disabled': show_disabled
    })

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
                    colour=colour,
                    category=category,
                    order=order,
                    enable_correspondence=enable_correspondence,
                    correspondence_mandatory=correspondence_mandatory
                )
                
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
                
                # Create default core fields
                CoreField.objects.create(
                    record_type=new_record_type,
                    name='title',
                    display_name='Title',
                    field_type='text'
                )
                
                # Create default roles
                default_roles = [
                    {
                        'name': 'Initiator',
                        'display_name': 'Initiator',
                        'stage': 'Initiate',
                        'description': 'Creates and submits the record'
                    },
                    {
                        'name': 'Reviewer',
                        'display_name': 'Reviewer',
                        'stage': 'Prepare and Review',
                        'description': 'Reviews the record details'
                    },
                    {
                        'name': 'Recommender',
                        'display_name': 'Recommender',
                        'stage': 'Recommend',
                        'description': 'Makes recommendations'
                    },
                    {
                        'name': 'Decider',
                        'display_name': 'Decision Maker',
                        'stage': 'Make Decision',
                        'description': 'Makes the final decision'
                    },
                    {
                        'name': 'Completer',
                        'display_name': 'Completer',
                        'stage': 'Implement and Close',
                        'description': 'Implements the decision and closes the record'
                    }
                ]
                
                for i, role_data in enumerate(default_roles):
                    Role.objects.create(
                        record_type=new_record_type,
                        name=role_data['name'],
                        display_name=role_data['display_name'],
                        description=role_data['description'],
                        stage=stages[role_data['stage']],
                        order=i
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
    record_type_obj = get_object_or_404(RecordType, name=record_type)
    stages = record_type_obj.stages.all().order_by('order')
    
    # Group roles by stage
    roles_by_stage = {}
    for stage in stages:
        roles_by_stage[stage] = stage.roles.all().order_by('order', 'name')
    
    return render(request, 'record_fields.html', {
        'record_type': record_type_obj,
        'custom_fields': record_type_obj.custom_fields.all(),
        'stages': stages,
        'core_fields': record_type_obj.core_fields.all(),
        'roles_by_stage': roles_by_stage
    })

def new_custom_field(request, record_type):
    record_type_obj = get_object_or_404(RecordType, name=record_type)
    
    if request.method == 'POST':
        try:
            field_name = request.POST.get('field_name')
            display_name = request.POST.get('display_name')
            field_type = request.POST.get('field_type')
            description = request.POST.get('description', '')
            order = request.POST.get('order', 0)
            show_in_header = request.POST.get('show_in_header') == 'on'
            is_mandatory = request.POST.get('is_mandatory') == 'on'
            visible_on_create = request.POST.get('visible_on_create') == 'on'
            term_set = request.POST.get('term_set', '').strip()

            try:
                order = int(order)
            except (ValueError, TypeError):
                order = 0

            custom_field = CustomField(
                record_type=record_type_obj,
                name=field_name,
                display_name=display_name,
                field_type=field_type,
                description=description,
                order=order,
                show_in_header=show_in_header,
                is_mandatory=is_mandatory,
                visible_on_create=visible_on_create,
                term_set=term_set
            )
            
            custom_field.full_clean()  # This will run validators
            custom_field.save()
            
            messages.success(request, f'Custom field "{field_name}" added successfully!')
            return redirect('record_fields', record_type=record_type)
            
        except ValidationError as e:
            messages.error(request, '; '.join(e.messages))
        except Exception as e:
            messages.error(request, str(e))
    
    return render(request, 'new_custom_field.html', {
        'record_type': record_type,
        'field_types': CustomField.FIELD_TYPES
    })

def edit_custom_field(request, record_type, field_name):
    custom_fields = request.session.get('custom_fields', {}).get(record_type, [])
    field = next((f for f in custom_fields if f['name'] == field_name), None)
    
    if field is None:
        messages.error(request, f'Field "{field_name}" not found.')
        return redirect('record_fields', record_type=record_type)
    
    if request.method == 'POST':
        if 'delete' in request.POST:
            # Delete the field
            custom_fields = [f for f in custom_fields if f['name'] != field_name]
            request.session['custom_fields'][record_type] = custom_fields
            request.session.modified = True
            messages.success(request, f'Field "{field_name}" deleted successfully.')
            return redirect('record_fields', record_type=record_type)
        else:
            # Update the field
            new_field_name = request.POST.get('field_name')
            new_field_type = request.POST.get('field_type')
            if new_field_name and new_field_type:
                field['name'] = new_field_name
                field['type'] = new_field_type
                request.session.modified = True
                messages.success(request, f'Field "{field_name}" updated successfully.')
                return redirect('record_fields', record_type=record_type)
            else:
                messages.error(request, 'Please enter valid field details.')
    
    return render(request, 'edit_custom_field.html', {'record_type': record_type, 'field': field})

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
    stages = record_type_obj.stages.all().order_by('order')
    
    if request.method == 'POST':
        new_stages = request.POST.getlist('stages')
        if len(new_stages) >= 2 and new_stages[0] == 'Initiate' and new_stages[-1] == 'Closed':
            # Validate stage names
            stage_pattern = re.compile(r'^[A-Za-z\s]{1,50}$')
            if all(stage_pattern.match(stage) for stage in new_stages):
                # Check if any deleted stage has assigned roles
                deleted_stages = set(stages.values_list('name', flat=True)) - set(new_stages)
                affected_stages = {}
                
                for stage in deleted_stages:
                    core_roles = CoreRole.objects.filter(record_type=record_type_obj, stage__name=stage)
                    custom_roles = CustomRole.objects.filter(record_type=record_type_obj, stage__name=stage)
                    if core_roles.exists() or custom_roles.exists():
                        affected_stages[stage] = list(core_roles.values_list('name', flat=True)) + list(custom_roles.values_list('name', flat=True))
                
                if affected_stages:
                    error_message = "Cannot delete the following stages due to assigned roles:\n"
                    for stage, roles in affected_stages.items():
                        error_message += f"- {stage}: {', '.join(roles)}\n"
                    messages.error(request, error_message)
                else:
                    # Update stages
                    Stage.objects.filter(record_type=record_type_obj).delete()
                    for i, stage_name in enumerate(new_stages):
                        Stage.objects.create(record_type=record_type_obj, name=stage_name, order=i)
                    messages.success(request, 'Stages updated successfully.')
                    return redirect('record_fields', record_type=record_type)
            else:
                messages.error(request, 'Invalid stage name. Use only alphabetical characters and spaces, maximum 50 characters.')
        else:
            messages.error(request, 'Invalid stages. Ensure "Initiate" is first and "Closed" is last.')
    
    return render(request, 'edit_stages.html', {'record_type': record_type_obj, 'stages': stages})

def edit_core_field(request, record_type, field_name):
    record_type_obj = get_object_or_404(RecordType, name=record_type)
    core_field = get_object_or_404(CoreField, record_type=record_type_obj, name=field_name)
    
    if request.method == 'POST':
        new_display_name = request.POST.get('display_name')
        if new_display_name:
            core_field.display_name = new_display_name
            core_field.save()
            messages.success(request, f'Core field "{field_name}" display name updated successfully.')
            return redirect('record_fields', record_type=record_type)
        else:
            messages.error(request, 'Please enter a valid display name.')
    
    return render(request, 'edit_core_field.html', {
        'record_type': record_type_obj,
        'field': core_field
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
        name = request.POST.get('name')
        display_name = request.POST.get('display_name')
        description = request.POST.get('description', '')
        stage_id = request.POST.get('stage')
        order = request.POST.get('order', 0)
        allow_multiple = request.POST.get('allow_multiple') == 'on'
        
        try:
            order = int(order)
        except (ValueError, TypeError):
            order = 0
        
        if name and display_name and stage_id:
            try:
                stage = Stage.objects.get(id=stage_id, record_type=record_type_obj)
                if stage.name == 'Closed':
                    messages.error(request, 'Roles cannot be assigned to the Closed stage.')
                    return render(request, 'add_role.html', {
                        'record_type': record_type_obj,
                        'stages': stages
                    })
                
                Role.objects.create(
                    record_type=record_type_obj,
                    name=name,
                    display_name=display_name,
                    description=description,
                    stage=stage,
                    order=order,
                    allow_multiple=allow_multiple
                )
                messages.success(request, f'Role "{display_name}" created successfully!')
                return redirect('record_fields', record_type=record_type)
            except IntegrityError:
                messages.error(request, f'A role with the name "{name}" already exists for this record type.')
            except Stage.DoesNotExist:
                messages.error(request, 'Invalid stage selected.')
        else:
            messages.error(request, 'Please fill in all required fields.')
    
    return render(request, 'add_role.html', {
        'record_type': record_type_obj,
        'stages': stages
    })

def edit_role(request, record_type, role_id):
    record_type_obj = get_object_or_404(RecordType, name=record_type)
    role = get_object_or_404(Role, id=role_id, record_type=record_type_obj)
    # Exclude Closed stage from available stages
    stages = record_type_obj.stages.exclude(name='Closed')
    
    if request.method == 'POST':
        if 'delete' in request.POST:
            role.delete()
            messages.success(request, f'Role "{role.display_name}" deleted successfully!')
            return redirect('record_fields', record_type=record_type)
        
        display_name = request.POST.get('display_name')
        stage_id = request.POST.get('stage')
        order = request.POST.get('order', role.order)
        
        try:
            order = int(order)
        except (ValueError, TypeError):
            order = role.order
        
        if display_name and stage_id:
            try:
                stage = Stage.objects.get(id=stage_id, record_type=record_type_obj)
                # Double check that we're not assigning to Closed stage
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

