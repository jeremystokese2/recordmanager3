from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db import IntegrityError
from django.core.exceptions import ValidationError  # Add this import
from django.http import FileResponse
from . import settings
import os
from .models import RecordType, Stage, CoreField, CustomField, Role
import re
from . import export
from django.contrib.auth.decorators import login_required, user_passes_test
import tempfile
import shutil
from django.http import JsonResponse
import json
from django.http import HttpResponse
from .export import export_record_fields
from azure.data.tables import TableServiceClient
from azure.core.exceptions import AzureError
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_protect
from datetime import datetime
from .utils import validate_record_type
from .utils import test_validate_record_type_from_json
from .utils import test_validate_record_fields_from_json
import csv
import io
import logging

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
    show_inactive = request.GET.get('show_inactive') == 'on'
    
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
    record_type_obj = get_object_or_404(RecordType, name=record_type)
    custom_field = get_object_or_404(CustomField, record_type=record_type_obj, name=field_name)
    
    if request.method == 'POST':
        if 'delete' in request.POST:
            # Delete the field
            custom_field.delete()
            messages.success(request, f'Field "{field_name}" deleted successfully.')
            return redirect('record_fields', record_type=record_type)
        else:
            # Update the field
            display_name = request.POST.get('display_name')
            field_type = request.POST.get('field_type')
            description = request.POST.get('description', '')
            order = request.POST.get('order', custom_field.order)
            show_in_header = request.POST.get('show_in_header') == 'on'
            is_mandatory = request.POST.get('is_mandatory') == 'on'
            visible_on_create = request.POST.get('visible_on_create') == 'on'
            is_active = request.POST.get('is_active') == 'on'  # Add this line
            term_set = request.POST.get('term_set', '').strip()
            
            try:
                order = int(order)
            except (ValueError, TypeError):
                order = custom_field.order

            if display_name and field_type:
                try:
                    custom_field.display_name = display_name
                    custom_field.field_type = field_type
                    custom_field.description = description
                    custom_field.order = order
                    custom_field.show_in_header = show_in_header
                    custom_field.is_mandatory = is_mandatory
                    custom_field.visible_on_create = visible_on_create
                    custom_field.is_active = is_active  # Add this line
                    custom_field.term_set = term_set
                    
                    custom_field.full_clean()  # Validate the field
                    custom_field.save()
                    
                    messages.success(request, f'Field "{field_name}" updated successfully.')
                    return redirect('record_fields', record_type=record_type)
                except ValidationError as e:
                    messages.error(request, '; '.join(e.messages))
            else:
                messages.error(request, 'Please enter valid field details.')
    
    return render(request, 'edit_custom_field.html', {
        'record_type': record_type,
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
    error_data = None  # Changed from error_message
    
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
        'error_data': error_data
    })

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
    # If coming from record_fields page, get the single record type
    single_record_type = request.GET.get('record_type')
    if single_record_type:
        selected_types = [single_record_type]
    else:
        # Otherwise get selected types from the home page
        selected_types = request.GET.getlist('types[]')
    
    # Create a temporary file
    with tempfile.NamedTemporaryFile(delete=False, suffix='.json') as tmp_file:
        filename = tmp_file.name
        
        # Generate the export data with selected types
        export_data = export.export_record_types(selected_types if selected_types else None)
        
        # Copy the export data to the temporary file
        shutil.copy2(export_data, filename)
        
        # Delete the original export file
        os.remove(export_data)
        
        # Create the response with the temporary file
        response = FileResponse(
            open(filename, 'rb'),
            content_type='application/json',
            as_attachment=True,
            filename='record_types_export.json'
        )
        
        # Schedule the temporary file for deletion after the response is sent
        response._resource_closers.append(lambda: os.remove(filename))
        
        return response

def export_fields(request, record_type):
    """Export record fields as JSON"""
    record_type_obj = get_object_or_404(RecordType, name=record_type)
    fields = CustomField.objects.filter(record_type=record_type_obj)
    roles = Role.objects.filter(record_type=record_type_obj)
    core_fields = CoreField.objects.filter(record_type=record_type_obj)
    
    # Combine all fields for export
    export_data = export_record_fields(record_type_obj, fields, roles, core_fields)  # Pass record_type_obj instead of just record_type
    
    # Convert to JSON
    json_data = json.dumps(export_data, indent=2)
    
    # Create the response
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

def parse_csv_to_json(csv_file, file_type):
    """
    Convert CSV to JSON format matching our expected structure
    """
    logger = logging.getLogger(__name__)
    logger.info(f"Starting CSV parsing for {file_type}")
    
    try:
        # Reset file pointer to beginning
        csv_file.seek(0)
        
        # Read the file content and decode it
        content = csv_file.read()
        if isinstance(content, bytes):
            content = content.decode('utf-8-sig')  # Handle BOM if present
        
        # Log the first part of content to verify it's not empty
        logger.info(f"File content length: {len(content)}")
        logger.info(f"First 200 chars: {content[:200]}")
        
        # Split into lines and find first non-empty line
        lines = [line.strip() for line in content.splitlines() if line.strip()]
        if not lines:
            logger.error("No non-empty lines found in file")
            raise ValueError("CSV file appears to be empty")
            
        logger.info(f"Number of non-empty lines: {len(lines)}")
        logger.info(f"First line: {lines[0]}")
        
        # Reset file pointer for CSV reader
        csv_file.seek(0)
        
        # Create CSV reader
        reader = csv.DictReader(
            (line for line in csv_file.read().decode('utf-8-sig').splitlines() if line.strip()),
            delimiter=',',
            quotechar='"',
            skipinitialspace=True
        )
        
        # Log field names detected
        field_names = reader.fieldnames
        if not field_names:
            logger.error("No headers detected in CSV file")
            raise ValueError("No headers detected in CSV file")
        logger.info(f"CSV headers found: {field_names}")
        
        records = []
        for row_num, row in enumerate(reader, 1):
            try:
                # Clean up the row data
                processed_row = {}
                for key, value in row.items():
                    if key and not key.endswith('@type'):  # Skip type annotation fields
                        # Handle empty values and 'null' strings
                        if not value or value.lower() == 'null':
                            processed_row[key] = None
                        else:
                            # Convert boolean strings
                            if value.lower() == 'true':
                                processed_row[key] = True
                            elif value.lower() == 'false':
                                processed_row[key] = False
                            else:
                                processed_row[key] = value.strip()
                
                logger.debug(f"Processed row {row_num}: {processed_row}")
                
                # Validate required fields
                if file_type == 'record_types':
                    if 'RowKey' not in processed_row:
                        error_msg = f"Row {row_num}: Missing required 'RowKey' column"
                        logger.error(error_msg)
                        raise ValueError(error_msg)
                        
                elif file_type == 'record_fields':
                    required_fields = ['RowKey', 'PartitionKey']
                    missing_fields = [f for f in required_fields if f not in processed_row]
                    if missing_fields:
                        error_msg = f"Row {row_num}: Missing required fields: {missing_fields}"
                        logger.error(error_msg)
                        raise ValueError(error_msg)
                
                records.append(processed_row)
                
            except Exception as e:
                logger.error(f"Error processing row {row_num}: {str(e)}")
                raise ValueError(f"Error in row {row_num}: {str(e)}")
        
        logger.info(f"Successfully parsed {len(records)} records from CSV")
        return records
        
    except UnicodeDecodeError as e:
        error_msg = f"Failed to decode CSV file: {str(e)}"
        logger.error(error_msg)
        raise ValueError(error_msg)
    except csv.Error as e:
        error_msg = f"CSV parsing error: {str(e)}"
        logger.error(error_msg)
        raise ValueError(error_msg)
    except Exception as e:
        error_msg = f"Unexpected error parsing CSV: {str(e)}"
        logger.error(error_msg)
        raise ValueError(error_msg)

def test_validation(request):
    """View to test both RecordType and RecordFields validation"""
    logger = logging.getLogger(__name__)
    
    if request.method == 'POST':
        try:
            logger.info("Starting validation process")
            
            # Both files are required
            if 'record_types_file' not in request.FILES or 'record_fields_file' not in request.FILES:
                logger.error("Missing required files")
                messages.error(request, "Both Record Types and Record Fields files are required")
                return render(request, 'test_validation.html')
            
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