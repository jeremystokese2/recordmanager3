import logging
import json
import re
from django.core.exceptions import ValidationError
from .constants import (
    RECORD_TYPE_FIELD_MAPPING, 
    SKIP_VALIDATION_MESSAGE,
    IGNORED_STATE_FIELDS,
    IGNORED_SP_FIELDS
)
from .stage_validator import validate_stages
from django.conf import settings

logger = logging.getLogger(__name__)

def map_json_to_record_type(json_data, field_mapping=RECORD_TYPE_FIELD_MAPPING):
    """Maps JSON data to RecordType fields using a configurable mapping."""
    mapped_data = {}
    
    if settings.DEBUG:
        logger.debug(f"Starting mapping with input data: {json_data}")
        logger.debug(f"Using field mapping: {field_mapping}")
    
    for model_field, json_field in field_mapping.items():
        value = json_data.get(json_field)
        
        if settings.DEBUG:
            logger.debug(f"Processing field mapping: {json_field} -> {model_field}")
            logger.debug(f"Initial value: {value} (type: {type(value)})")
        
        if model_field == 'name' and value is None:
            value = json_data.get('RowKey')
            if settings.DEBUG:
                logger.debug(f"Name fallback to RowKey: {value}")
            
        # Handle boolean fields from CSV/JSON
        if model_field in ['is_enabled', 'enable_correspondence']:
            if settings.DEBUG:
                logger.debug(f"Processing boolean field: {model_field}")
                logger.debug(f"JSON field name: {json_field}")
                logger.debug(f"Raw value in JSON: {json_data.get(json_field)}")
            
            # First check the mapped field name (IsActive)
            if json_field in json_data:
                raw_value = str(json_data[json_field]).lower()
                value = raw_value == 'true'
                if settings.DEBUG:
                    logger.debug(f"Boolean conversion: {raw_value} -> {value}")
            else:
                value = False
                if settings.DEBUG:
                    logger.debug(f"Field {json_field} not found, defaulting to False")
            
        if model_field == 'colour' and value is None:
            value = json_data.get('Color', '#000000')
            if settings.DEBUG:
                logger.debug(f"Color fallback: {value}")
            
        if value is None and model_field in ['description', 'colour', 'order']:
            value = '' if model_field == 'description' else (
                '#000000' if model_field == 'colour' else 0
            )
            if settings.DEBUG:
                logger.debug(f"Default value set for {model_field}: {value}")
            
        mapped_data[model_field] = value
        
        if settings.DEBUG:
            logger.debug(f"Final mapped value for {model_field}: {value} (type: {type(value)})")
    
    if settings.DEBUG:
        logger.debug(f"Final mapped data: {mapped_data}")
    
    return mapped_data

def validate_record_type(record_type_obj):
    """Validates a RecordType object according to creation rules."""
    validation_results = []
    
    if settings.DEBUG:
        logger.debug(f"Starting validation for record type: {record_type_obj}")
    
    try:
        # Check IsActive status first
        is_active = record_type_obj.get('is_enabled', True)
        
        if settings.DEBUG:
            logger.debug(f"Checking is_enabled status: {is_active} (type: {type(is_active)})")
            logger.debug(f"Raw record_type_obj: {record_type_obj}")
        
        if not is_active:
            if settings.DEBUG:
                logger.debug("Record marked as inactive, skipping further validation")
            return [{
                'field': 'IsActive',
                'status': 'INFO',
                'message': SKIP_VALIDATION_MESSAGE
            }]
        
        # Name validation
        name = record_type_obj.get('name')
        if not name:
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
        prefix = record_type_obj.get('prefix')
        prefix_valid = True
        if not prefix:
            validation_results.append({
                'field': 'Prefix',
                'status': 'FAILED',
                'message': "Prefix is required"
            })
            prefix_valid = False
        if prefix and len(prefix) > 4:
            validation_results.append({
                'field': 'Prefix',
                'status': 'FAILED',
                'message': "Prefix must be 4 characters or less"
            })
            prefix_valid = False
        if prefix_valid and prefix:
            validation_results.append({
                'field': 'Prefix',
                'status': 'SUCCESS',
                'message': "Prefix is valid and correct length"
            })
            
        # Description validation
        description = record_type_obj.get('description', '')
        if len(description) > 250:
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
        category = record_type_obj.get('category')
        if not category:
            validation_results.append({
                'field': 'Category',
                'status': 'FAILED',
                'message': "Category is required"
            })
        elif not re.match(r'^[A-Za-z\s]{1,50}$', category):
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
        order = record_type_obj.get('order', 0)
        try:
            int(order)
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
        stages_json = record_type_obj.get('StagesJson')
        if stages_json:
            stage_validations = validate_stages(
                stages_json,
                name
            )
            validation_results.extend(stage_validations)
            
        # Log validation results
        logger.info(f"Completed validation for RecordType '{name}'")
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
            
        # Filter out ignored fields before processing
        filtered_records = [
            record for record in records 
            if record.get('RowKey') not in IGNORED_STATE_FIELDS 
            and record.get('RowKey') not in IGNORED_SP_FIELDS
        ]
        
        logger.info(f"Filtered {len(records) - len(filtered_records)} ignored fields")
        
        mapping = field_mapping or RECORD_TYPE_FIELD_MAPPING
        overall_success = True
            
        for record in filtered_records:
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