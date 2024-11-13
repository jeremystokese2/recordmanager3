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
            ("RowKey", record.name),
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
        field_data = {
            "odata.type": "briefconnectabcsa.RecordFields",
            "PartitionKey": record_type_obj.name,
            "RowKey": field.name,
            "DisplayName": field.display_name,
            "Description": "",
            "FieldType": 1,  # Core fields are typically text type
            "FiledType": 1,
            "IsActive": True,
            "IsRequired": True,
            "IsNotRequiredOnCreation": False,
            "NotEditable": False,
            "Order": 0,
            "ShowInHeader": False
        }
        export_data.append(field_data)
    
    # Handle custom fields
    for field in custom_fields:
        field_type = {
            'text': 1,
            'textarea': 2,
            'date': 5,
            'datetime': 7,
            'time': 6,
            'dropdown_single': 2,
            'dropdown_multi': 3,
            'radio': 10,
            'combobox_single': 2,
            'combobox_multi': 3,
        }.get(field.field_type, 1)
        
        field_data = {
            "odata.type": "briefconnectabcsa.RecordFields",
            "PartitionKey": record_type_obj.name,
            "RowKey": field.name,
            "DisplayName": field.display_name,
            "Description": field.description or "",
            "FieldType": field_type,
            "FiledType": field_type,
            "IsActive": field.is_active,
            "IsRequired": field.is_mandatory,
            "IsNotRequiredOnCreation": not field.visible_on_create,
            "NotEditable": False,
            "Order": field.order,
            "ShowInHeader": field.show_in_header,
            "WizardPosition": field.wizard_position,
        }
        
        if field.field_type in ['dropdown_single', 'dropdown_multi', 'radio', 'combobox_single', 'combobox_multi']:
            field_data["DataSourceName"] = field.term_set
            
        export_data.append(field_data)
    
    # Handle roles
    for role in roles:
        field_data = {
            "odata.type": "briefconnectabcsa.RecordFields",
            "PartitionKey": record_type_obj.name,
            "RowKey": role.name,
            "DisplayName": role.display_name,
            "Description": role.description or "",
            "FieldType": 8 if role.allow_multiple else 4,
            "FiledType": 8 if role.allow_multiple else 4,
            "IsActive": role.is_active,
            "IsRequired": role.is_mandatory,  # Changed this line
            "IsNotRequiredOnCreation": False,
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
