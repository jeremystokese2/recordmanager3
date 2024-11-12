import logging
import json
import re
from django.core.exceptions import ValidationError
from .constants import RECORD_TYPE_FIELD_MAPPING, SKIP_VALIDATION_MESSAGE
from .stage_validator import validate_stages

logger = logging.getLogger(__name__)

def map_json_to_record_type(json_data, field_mapping=RECORD_TYPE_FIELD_MAPPING):
    """Maps JSON data to RecordType fields using a configurable mapping."""
    mapped_data = {}
    
    for model_field, json_field in field_mapping.items():
        value = json_data.get(json_field)
        
        if model_field in ['is_enabled', 'enable_correspondence']:
            value = str(value).lower() == 'true' if value else False
            
        if value is None and model_field in ['description', 'colour', 'order']:
            value = '' if model_field == 'description' else (
                '#000000' if model_field == 'colour' else 0
            )
            
        mapped_data[model_field] = value
    
    return mapped_data

def validate_record_type(record_type_obj):
    """Validates a RecordType object according to creation rules."""
    validation_results = []
    
    try:
        # Check IsActive status first
        is_active = getattr(record_type_obj, 'is_enabled', True)  # Default to True if not set
        if not is_active:
            return [{
                'field': 'IsActive',
                'status': 'INFO',
                'message': SKIP_VALIDATION_MESSAGE
            }]
        
        # Name validation
        if not record_type_obj.name:
            validation_results.append({
                'field': 'Name',
                'status': 'FAILED',
                'message': "Record type name is required"
            })
        else:
            validation_results.append({
                'field': 'Name',
                'status': 'SUCCESS',
                'message': "Name is valid"
            })
            
        # Prefix validation
        prefix_valid = True
        if not record_type_obj.prefix:
            validation_results.append({
                'field': 'Prefix',
                'status': 'FAILED',
                'message': "Prefix is required"
            })
            prefix_valid = False
        if record_type_obj.prefix and len(record_type_obj.prefix) > 4:
            validation_results.append({
                'field': 'Prefix',
                'status': 'FAILED',
                'message': "Prefix must be 4 characters or less"
            })
            prefix_valid = False
        if prefix_valid and record_type_obj.prefix:
            validation_results.append({
                'field': 'Prefix',
                'status': 'SUCCESS',
                'message': "Prefix is valid and correct length"
            })
            
        # Description validation
        if hasattr(record_type_obj, 'description'):
            if len(record_type_obj.description) > 250:
                validation_results.append({
                    'field': 'Description',
                    'status': 'FAILED',
                    'message': "Description must be 250 characters or less"
                })
            else:
                validation_results.append({
                    'field': 'Description',
                    'status': 'SUCCESS',
                    'message': "Description length is valid"
                })
            
        # Category validation
        if not record_type_obj.category:
            validation_results.append({
                'field': 'Category',
                'status': 'FAILED',
                'message': "Category is required"
            })
        elif not re.match(r'^[A-Za-z\s]{1,50}$', record_type_obj.category):
            validation_results.append({
                'field': 'Category',
                'status': 'FAILED',
                'message': "Category must contain only letters and spaces (max 50 characters)"
            })
        else:
            validation_results.append({
                'field': 'Category',
                'status': 'SUCCESS',
                'message': "Category format is valid"
            })
            
        # Order validation
        try:
            int(record_type_obj.order)
            validation_results.append({
                'field': 'Order',
                'status': 'SUCCESS',
                'message': "Order is a valid number"
            })
        except (ValueError, TypeError):
            validation_results.append({
                'field': 'Order',
                'status': 'FAILED',
                'message': "Order must be a valid number"
            })
            
        # Add stage validation
        if hasattr(record_type_obj, 'StagesJson'):
            stage_validations = validate_stages(
                record_type_obj.StagesJson,
                record_type_obj.name
            )
            validation_results.extend(stage_validations)
            
        # Log validation results
        logger.info(f"Completed validation for RecordType '{record_type_obj.name}'")
        return validation_results
            
    except Exception as e:
        error_msg = f"Unexpected error validating RecordType: {str(e)}"
        logger.error(error_msg)
        return [{
            'field': 'System',
            'status': 'ERROR',
            'message': error_msg
        }]

def test_validate_record_type_from_json(json_file_path, field_mapping=None):
    """Test function to validate RecordType data from a JSON file."""
    logger.info(f"Testing RecordType validation with file: {json_file_path}")
    validation_results = []
    
    try:
        # Read JSON file
        with open(json_file_path, 'r') as file:
            records = json.load(file)
            
        mapping = field_mapping or RECORD_TYPE_FIELD_MAPPING
        overall_success = True
            
        for record in records:
            try:
                # Check IsActive status first
                is_active = str(record.get('IsActive', 'true')).lower() == 'true'
                record_name = record.get('RowKey', 'Unknown')
                
                if not is_active:
                    validation_results.append({
                        'record': record_name,
                        'status': 'INFO',
                        'is_active': is_active,
                        'details': [{
                            'field': 'IsActive',
                            'status': 'INFO',
                            'message': SKIP_VALIDATION_MESSAGE
                        }]
                    })
                    continue
                
                # Map JSON to record type object
                mapped_data = map_json_to_record_type(record, mapping)
                validation_checks = validate_record_type(mapped_data)
                
                has_failures = any(check['status'] == 'FAILED' for check in validation_checks)
                
                validation_results.append({
                    'record': mapped_data['name'],
                    'status': 'FAILED' if has_failures else 'SUCCESS',
                    'is_active': is_active,
                    'details': validation_checks
                })
                
                if has_failures:
                    overall_success = False
                    
            except Exception as e:
                overall_success = False
                validation_results.append({
                    'record': record.get('RowKey', 'Unknown'),
                    'status': 'ERROR',
                    'details': [{
                        'field': 'System',
                        'status': 'ERROR',
                        'message': str(e)
                    }]
                })
                logger.error(f"Error processing record: {str(e)}")
                
        return overall_success, validation_results
        
    except json.JSONDecodeError as je:
        error_msg = f"Invalid JSON file: {str(je)}"
        logger.error(error_msg)
        return False, [{
            'record': 'File Error',
            'status': 'ERROR',
            'details': [{
                'field': 'JSON',
                'status': 'ERROR',
                'message': str(je)
            }]
        }]
        
    except Exception as e:
        error_msg = f"Error reading file: {str(e)}"
        logger.error(error_msg)
        return False, [{
            'record': 'System Error',
            'status': 'ERROR',
            'details': [{
                'field': 'System',
                'status': 'ERROR',
                'message': str(e)
            }]
        }]