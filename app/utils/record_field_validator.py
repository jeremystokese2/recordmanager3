import logging
import re
from .constants import (
    RECORD_FIELD_MAPPING, 
    VALID_FIELD_TYPES,
    DATASOURCE_REQUIRED_TYPES,
    ROLE_FIELD_TYPES,
    SKIP_VALIDATION_MESSAGE
)
import json

logger = logging.getLogger(__name__)

def map_json_to_record_field(json_data, field_mapping=RECORD_FIELD_MAPPING):
    """Maps JSON data to RecordField format using configurable mapping."""
    mapped_data = {}
    
    for model_field, json_field in field_mapping.items():
        value = json_data.get(json_field)
        
        if model_field in ['is_active', 'is_mandatory', 'show_in_header']:
            value = str(value).lower() == 'true' if value else False
            
        mapped_data[model_field] = value
        
    return mapped_data

def validate_record_field(field_data, record_types, all_fields):
    """Validates a single record field according to rules."""
    validation_results = []
    field_name = field_data.get('RowKey', 'Unknown Field')
    
    try:
        logger.info(f"Starting validation for field: {field_name}")
        
        # Check IsActive status first
        is_active = str(field_data.get('IsActive', 'true')).lower() == 'true'
        if not is_active:
            logger.info(f"Field {field_name} is inactive - skipping validation")
            return [{
                'field': 'IsActive',
                'status': 'INFO',
                'message': SKIP_VALIDATION_MESSAGE
            }]
            
        partition_key = field_data.get('PartitionKey', '')
        
        # 1. PartitionKey validation
        logger.info(f"Validating PartitionKey for {field_name}")
        if not partition_key:
            validation_results.append({
                'field': 'PartitionKey',
                'status': 'FAILED',
                'message': "PartitionKey is required"
            })
        elif partition_key not in record_types:
            validation_results.append({
                'field': 'PartitionKey',
                'status': 'FAILED',
                'message': f"PartitionKey '{partition_key}' does not match any Record Type"
            })
        else:
            validation_results.append({
                'field': 'PartitionKey',
                'status': 'SUCCESS',
                'message': f"Valid Record Type: {partition_key}"
            })
            
        # 2. Unique RowKey + PartitionKey combination
        logger.info(f"Checking uniqueness for {field_name}")
        if any(f != field_data and 
               f.get('PartitionKey') == partition_key and 
               f.get('RowKey') == field_name 
               for f in all_fields):
            validation_results.append({
                'field': 'Unique Key',
                'status': 'FAILED',
                'message': f"Combination of PartitionKey '{partition_key}' and RowKey '{field_name}' is not unique"
            })
        else:
            validation_results.append({
                'field': 'Unique Key',
                'status': 'SUCCESS',
                'message': "Field key is unique"
            })
            
        # 3. RowKey format validation
        logger.info(f"Validating RowKey format for {field_name}")
        if not re.match(r'^[A-Za-z0-9]+$', field_name):
            validation_results.append({
                'field': 'RowKey Format',
                'status': 'FAILED',
                'message': "RowKey must contain only alphanumeric characters (no spaces)"
            })
        else:
            validation_results.append({
                'field': 'RowKey Format',
                'status': 'SUCCESS',
                'message': "RowKey format is valid"
            })
            
        # Get both field type values
        field_type = field_data.get('FieldType')
        filed_type = field_data.get('FiledType')  # Handle legacy typo
        
        # 4. Field Types validation
        logger.info(f"Validating field types for {field_name}")
        if field_type is not None and filed_type is not None:
            if field_type == filed_type:
                validation_results.append({
                    'field': 'FiledType',
                    'status': 'INFO',
                    'message': f"FiledType present and matches FieldType (value: {field_type})"
                })
            else:
                validation_results.append({
                    'field': 'Field Types',
                    'status': 'FAILED',
                    'message': f"FieldType ({field_type}) does not match FiledType ({filed_type})"
                })
        elif filed_type is not None:
            validation_results.append({
                'field': 'FiledType',
                'status': 'INFO',
                'message': f"FiledType present with value: {filed_type}"
            })
            
        # 5. DataSourceName validation
        logger.info(f"Validating DataSourceName for {field_name}")
        datasource_name = field_data.get('DataSourceName')
        if field_type and int(field_type) in DATASOURCE_REQUIRED_TYPES:
            if not datasource_name:
                validation_results.append({
                    'field': 'DataSourceName',
                    'status': 'FAILED',
                    'message': f"DataSourceName is required for field type {VALID_FIELD_TYPES.get(int(field_type))}"
                })
            else:
                validation_results.append({
                    'field': 'DataSourceName',
                    'status': 'INFO',
                    'message': f"Term set must exactly match: {datasource_name}"
                })
                
        # 6. Display name validation
        logger.info(f"Validating display name for {field_name}")
        display_name = field_data.get('DisplayName')
        if not display_name:
            validation_results.append({
                'field': 'Display Name',
                'status': 'FAILED',
                'message': "Display name is required"
            })
        else:
            validation_results.append({
                'field': 'Display Name',
                'status': 'SUCCESS',
                'message': "Display name is valid"
            })
            
        # 7. Field type validation
        logger.info(f"Validating field type values for {field_name}")
        if field_type is not None:
            try:
                field_type_int = int(field_type)
                if field_type_int not in VALID_FIELD_TYPES:
                    validation_results.append({
                        'field': 'FieldType',
                        'status': 'FAILED',
                        'message': f"Invalid field type: {field_type}. Must be one of {list(VALID_FIELD_TYPES.keys())}"
                    })
                else:
                    validation_results.append({
                        'field': 'FieldType',
                        'status': 'SUCCESS',
                        'message': f"Valid field type: {VALID_FIELD_TYPES[field_type_int]}"
                    })
            except (ValueError, TypeError):
                validation_results.append({
                    'field': 'FieldType',
                    'status': 'FAILED',
                    'message': "FieldType must be a valid integer"
                })
                
        # Additional validations...
        
    except Exception as e:
        logger.error(f"Error validating field {field_name}: {str(e)}")
        validation_results.append({
            'field': 'System',
            'status': 'ERROR',
            'message': f"Unexpected error: {str(e)}"
        })
        
    logger.info(f"Completed validation for field: {field_name}")
    return validation_results

def test_validate_record_fields_from_json(json_file_path, record_types=None, all_fields=None):
    """Test function to validate RecordFields data from a JSON file."""
    logger.info(f"Testing RecordFields validation with file: {json_file_path}")
    validation_results = []
    
    try:
        # Read JSON file if all_fields not provided
        if all_fields is None:
            with open(json_file_path, 'r') as file:
                all_fields = json.load(file)
                
        overall_success = True
            
        for field in all_fields:
            try:
                # Check IsActive status first
                is_active = str(field.get('IsActive', 'true')).lower() == 'true'
                field_name = field.get('RowKey', 'Unknown Field')
                
                if not is_active:
                    validation_results.append({
                        'record': field_name,
                        'status': 'INFO',
                        'is_active': is_active,
                        'partition_key': field.get('PartitionKey', ''),
                        'details': [{
                            'field': 'IsActive',
                            'status': 'INFO',
                            'message': SKIP_VALIDATION_MESSAGE
                        }]
                    })
                    continue
                
                # Proceed with normal validation for active fields
                field_validations = validate_record_field(
                    field,
                    record_types=record_types or [],
                    all_fields=all_fields
                )
                
                has_failures = any(check['status'] == 'FAILED' for check in field_validations)
                
                validation_results.append({
                    'record': field_name,
                    'status': 'FAILED' if has_failures else 'SUCCESS',
                    'is_active': is_active,
                    'partition_key': field.get('PartitionKey', ''),
                    'details': field_validations
                })
                
                if has_failures:
                    overall_success = False
                    
            except Exception as e:
                overall_success = False
                validation_results.append({
                    'record': field.get('RowKey', 'Unknown Field'),
                    'status': 'ERROR',
                    'details': [{
                        'field': 'System',
                        'status': 'ERROR',
                        'message': str(e)
                    }]
                })
                logger.error(f"Error processing field: {str(e)}")
                
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