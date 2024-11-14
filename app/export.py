import json
from typing import List, Dict, Any
from django.core.serializers.json import DjangoJSONEncoder
from app.models import RecordType
from collections import OrderedDict

def export_record_types(selected_types: List[str] = None) -> str:
    """
    Export record types in a format compatible with Azure Table Storage.
    Args:
        selected_types: Optional list of record type names to export. If None, exports all.
    Returns the filename of the exported JSON file.
    """
    if selected_types:
        record_types = RecordType.objects.filter(name__in=selected_types)
    else:
        record_types = RecordType.objects.all()
        
    export_data = []

    for record in record_types:
        # Convert stages to StagesJson format
        stages_json = json.dumps([{
            "Name": stage.name,
            "Order": stage.order
        } for stage in record.stages.all().order_by('order')])

        # Use OrderedDict to maintain field order
        record_data = OrderedDict([
            ("odata.type", "briefconnectabcsa.RecordTypes"),
            ("odata.id", f"https://briefconnectabcsa.table.core.windows.net/RecordTypes(PartitionKey='V1',RowKey='{record.name}')"),
            ("odata.editLink", f"RecordTypes(PartitionKey='V1',RowKey='{record.name}')"),
            ("PartitionKey", "V1"),
            ("RowKey", f"{record.name} ({record.prefix})"),
            ("Category", record.category),
            ("Color", record.colour),
            ("IsActive", record.is_enabled),
            ("IsCorrespondenceType", record.enable_correspondence),
            ("Order", record.order),
            ("Prefix", record.prefix),
            ("StagesJson", stages_json)
        ])
        
        export_data.append(record_data)

    # Write to file
    output_file = 'record_types_export.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(export_data, f, cls=DjangoJSONEncoder, indent=2)

    return output_file

def export_record_fields(record_type_obj, custom_fields, roles, core_fields):
    """Export record fields to JSON format"""
    export_data = []
    
    # Handle core fields
    for field in core_fields:
        # Map field types according to VALID_FIELD_TYPES
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
        
        # Get the numeric field type
        field_type_num = field_type_map.get(field.get_field_type_display(), 1)  # Default to 1 (text) if not found
        
        field_data = {
            "PartitionKey": record_type_obj.name,
            "RowKey": field.name,
            "DisplayName": field.display_name,
            "Description": field.description or "",
            "FieldType": field_type_num,  # Use numeric value
            "FiledType": field_type_num,  # Use numeric value
            "IsActive": field.is_active,
            "IsRequired": field.is_mandatory,
            "IsNotRequiredOnCreation": not field.visible_on_create,
            "NotEditable": not field.is_active,
            "Order": field.order,
            "ShowInHeader": False,
            "WizardPosition": 0,
            "DataSourceName": field.term_set or "",
            "SysCategory": "core"
        }
        
        # Special handling for specific core fields that need term sets
        if field.name == 'ABCRequestFrom':
            field_data["DataSourceName"] = "Request From"
        elif field.name == 'ABCTimeframe':
            field_data["DataSourceName"] = "Timeframe"
        elif field.name == 'ABCDecisionCategory':
            field_data["DataSourceName"] = "Decision Category"
            
        export_data.append(field_data)
    
    # Handle custom fields
    for field in custom_fields:
        field_data = {
            "PartitionKey": record_type_obj.name,
            "RowKey": field.name,
            "DisplayName": field.display_name,
            "Description": field.description or "",
            "FieldType": field.field_type,
            "FiledType": field.field_type,
            "IsActive": field.is_active,
            "IsRequired": field.is_mandatory,
            "IsNotRequiredOnCreation": not field.visible_on_create,
            "NotEditable": not field.is_active,
            "Order": field.order,
            "ShowInHeader": field.show_in_header,
            "WizardPosition": field.wizard_position,
            "DataSourceName": field.term_set or "",
            "SysCategory": "custom"
        }
        export_data.append(field_data)
    
    # Handle roles
    for role in roles:
        not_required_on_create = True
        if role.name in ['ABCInitiator', 'ABCDecisionMaker']:
            not_required_on_create = False
            
        field_data = {
            "PartitionKey": record_type_obj.name,
            "RowKey": role.name,
            "DisplayName": role.display_name,
            "Description": role.description or "",
            "FieldType": 8 if role.allow_multiple else 4,
            "FiledType": 8 if role.allow_multiple else 4,
            "IsActive": role.is_active,
            "IsRequired": role.is_mandatory,
            "IsNotRequiredOnCreation": not_required_on_create,
            "NotEditable": False,
            "Order": role.order,
            "ShowInHeader": False,
            "Stages": role.stage.name
        }
        export_data.append(field_data)
    
    return export_data

if __name__ == "__main__":
    filename = export_record_types()
    print(f"Record types exported to {filename}")
