import re
import logging
import json
from django.core.exceptions import ValidationError
from .models import RecordType

# Configure logging to stream to stdout
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)

logger = logging.getLogger(__name__)

# Define the mapping between JSON fields and RecordType model fields
RECORD_TYPE_FIELD_MAPPING = {
    'name': 'RowKey',
    'prefix': 'Prefix',
    'description': 'Description',
    'category': 'Category',
    'colour': 'Color',
    'order': 'Order',
    'is_enabled': 'IsActive',
    'enable_correspondence': 'IsCorrespondenceType'
}

def map_json_to_record_type(json_data, field_mapping=RECORD_TYPE_FIELD_MAPPING):
    """
    Maps JSON data to RecordType fields using a configurable mapping.
    Handles StagesJson separately from model fields.
    """
    mapped_data = {}
    
    # Map the regular fields
    for model_field, json_field in field_mapping.items():
        value = json_data.get(json_field)
        
        # Handle boolean fields
        if model_field in ['is_enabled', 'enable_correspondence']:
            value = str(value).lower() == 'true' if value else False
            
        # Handle missing optional fields
        if value is None and model_field in ['description', 'colour', 'order']:
            value = '' if model_field == 'description' else (
                '#000000' if model_field == 'colour' else 0
            )
            
        mapped_data[model_field] = value
    
    # Create RecordType instance
    record_type = RecordType(**mapped_data)
    
    # Add StagesJson as an attribute (not a model field)
    stages_json = json_data.get('StagesJson')
    if stages_json:
        setattr(record_type, 'StagesJson', stages_json)
    
    return record_type

# Add to existing constants at the top
SKIP_VALIDATION_MESSAGE = "Record is inactive (IsActive=False) - skipping validation"

def validate_record_type(record_type_obj):
    """
    Validates a RecordType object according to creation rules.
    """
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
        elif RecordType.objects.exclude(id=record_type_obj.id).filter(name=record_type_obj.name).exists():
            validation_results.append({
                'field': 'Name',
                'status': 'FAILED',
                'message': f"Record type with name '{record_type_obj.name}' already exists"
            })
        else:
            validation_results.append({
                'field': 'Name',
                'status': 'SUCCESS',
                'message': "Name is valid and unique"
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
        if record_type_obj.prefix and RecordType.objects.exclude(id=record_type_obj.id).filter(prefix=record_type_obj.prefix).exists():
            validation_results.append({
                'field': 'Prefix',
                'status': 'FAILED',
                'message': f"Record type with prefix '{record_type_obj.prefix}' already exists"
            })
            prefix_valid = False
        if prefix_valid and record_type_obj.prefix:
            validation_results.append({
                'field': 'Prefix',
                'status': 'SUCCESS',
                'message': "Prefix is valid, unique, and correct length"
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
    """
    Test function to validate RecordType data from a JSON file.
    """
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
                
                # Proceed with normal validation for active records
                test_record = map_json_to_record_type(record, mapping)
                validation_checks = validate_record_type(test_record)
                
                has_failures = any(check['status'] == 'FAILED' for check in validation_checks)
                
                validation_results.append({
                    'record': test_record.name,
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

# Add these constants at the top with the other constants
IGNORED_STATE_FIELDS = {
    'ABCAssignedTo', 'ABCAutoResponseTemplates', 'ABCCancelled', 'ABCClosedDate', 
    'ABCCreatedByUser', 'ABCDocumentOrdering', 'ABCDueDateCurrentTask', 'ABCLinkedAgendaId',
    'ABCLinkedMeetingId', 'ABCModifiedByUser', 'ABCNoFurtherAction', 'ABCOnHold',
    'ABCOverrideDefaultAccess', 'ABCRecommendations', 'ABCRecordId', 'ABCRelatedRecords',
    'ABCSignatureRequired', 'ABCStage', 'ABCStageName', 'ABCStage_0', 'ABCSuperseded',
    'ABCSupersededBy', 'ABCSupersededFrom', 'ABCTaskMappings', 'ABCTasks', 'ABCTasks_0',
    'ABCViewAccessUsers', 'ABCWithdrawn', 'ContentType'
}

IGNORED_SP_FIELDS = {
    'DocumentSetDescription', 'FileLeafRef', 'FolderChildCount', 'ItemChildCount'
}

ROLE_FIELD_TYPES = {4, 8}  # 4 = single user role, 8 = multi-user role

# Add this constant with the other mappings
RECORD_FIELD_MAPPING = {
    'name': 'RowKey',
    'display_name': 'DisplayName',
    'field_type': 'FieldType',  # Map to FieldType instead of Type
    'description': 'Description',
    'order': 'Order',
    'is_active': 'IsActive',
    'is_mandatory': 'IsRequired',
    'stage': 'Stages',
    'show_in_header': 'ShowInHeader'
}

def map_json_to_record_field(json_data, field_mapping=RECORD_FIELD_MAPPING):
    """
    Maps JSON data to RecordField format using configurable mapping.
    """
    mapped_data = {}
    
    for model_field, json_field in field_mapping.items():
        value = json_data.get(json_field)
        
        # Handle boolean fields
        if model_field in ['is_active', 'is_mandatory', 'show_in_header']:
            value = str(value).lower() == 'true' if value else False
            
        mapped_data[model_field] = value
        
    return mapped_data

# Add these constants
VALID_FIELD_TYPES = {
    1: 'text input',
    2: 'single select dropdown',
    3: 'multi select dropdown',
    4: 'single user role',
    5: 'date only',
    6: 'time only',
    7: 'date and time',
    8: 'multi user role',
    9: 'text area',
    10: 'radio'
}

DATASOURCE_REQUIRED_TYPES = {2, 3, 10}  # Field types that require datasource
ROLE_FIELD_TYPES = {4, 8}  # Already defined above
VALID_SYS_CATEGORIES = {'', 'core', 'custom'}
VALID_WIZARD_POSITIONS = {0, 1}

def validate_record_field(field_data, record_types, all_fields):
    """
    Validates a single record field according to rules.
    
    Args:
        field_data: Dict containing field data
        record_types: List of valid record type names
        all_fields: List of all fields for duplicate checking
    """
    validation_results = []
    logger = logging.getLogger(__name__)
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
        filed_type = field_data.get('FiledType')
        
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
                
        # 8. FiledType validation if present
        if filed_type is not None:
            try:
                filed_type_int = int(filed_type)
                if filed_type_int not in VALID_FIELD_TYPES:
                    validation_results.append({
                        'field': 'FiledType',
                        'status': 'FAILED',
                        'message': f"Invalid filed type: {filed_type}. Must be one of {list(VALID_FIELD_TYPES.keys())}"
                    })
            except (ValueError, TypeError):
                validation_results.append({
                    'field': 'FiledType',
                    'status': 'FAILED',
                    'message': "FiledType must be a valid integer"
                })

        # 9. IsNotRequiredOnCreation validation
        logger.info(f"Validating creation requirements for {field_name}")
        is_not_required = str(field_data.get('IsNotRequiredOnCreation', '')).lower() == 'true'
        if is_not_required and field_type and int(field_type) not in ROLE_FIELD_TYPES:
            validation_results.append({
                'field': 'IsNotRequiredOnCreation',
                'status': 'INFO',
                'message': f"IsNotRequiredOnCreation is set to <code>{field_data.get('IsNotRequiredOnCreation')}</code> but field is not a role field"
            })
            
        # 10. NotEditable validation
        not_editable = str(field_data.get('NotEditable', '')).lower() == 'true'
        if not_editable:
            validation_results.append({
                'field': 'NotEditable',
                'status': 'INFO',
                'message': "Field is not editable"
            })
            
        # 11. IsRequired and NotEditable validation
        is_required = str(field_data.get('IsRequired', '')).lower() == 'true'
        if is_required and not_editable:
            validation_results.append({
                'field': 'Required/Editable',
                'status': 'FAILED',
                'message': "Field cannot be both required and not editable"
            })
                
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
    """
    Test function to validate RecordFields data from a JSON file.
    
    Args:
        json_file_path: Path to JSON file containing RecordFields data
        record_types: List of valid record type names
        all_fields: List of all fields for duplicate checking
        
    Returns:
        tuple: (bool, list) - (success status, list of validation results)
    """
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

# Add to the existing constants
REQUIRED_STAGES = ['Initiate', 'Closed']
STAGE_NAME_MAX_LENGTH = 50  # Update the constant to match the model

def validate_stages(stages_json, record_name):
    """
    Validates stages data from JSON according to Stage model constraints.
    
    Args:
        stages_json: JSON string containing stages data
        record_name: Name of the record type (for logging)
        
    Returns:
        list: List of validation results
    """
    validation_results = []
    
    try:
        # Parse stages JSON
        if not stages_json:
            return [{
                'field': 'Stages',
                'status': 'FAILED',
                'message': "Stages data is required"
            }]
            
        stages = json.loads(stages_json)
        
        if not isinstance(stages, list):
            return [{
                'field': 'Stages',
                'status': 'FAILED',
                'message': "Stages must be a list"
            }]
            
        # Check if stages list is empty
        if not stages:
            return [{
                'field': 'Stages',
                'status': 'FAILED',
                'message': "At least one stage is required"
            }]
            
        # Validate stage names and order
        stage_names = set()
        orders = set()
        
        for stage in stages:
            name = stage.get('Name', '')
            order = stage.get('Order')
            
            # Validate stage name according to model constraints
            if not name:
                validation_results.append({
                    'field': 'Stage Name',
                    'status': 'FAILED',
                    'message': "Stage name is required"
                })
            elif len(name) > STAGE_NAME_MAX_LENGTH:
                validation_results.append({
                    'field': f"Stage '{name}'",
                    'status': 'FAILED',
                    'message': f"Stage name exceeds maximum length of {STAGE_NAME_MAX_LENGTH} characters"
                })
            elif name in stage_names:
                validation_results.append({
                    'field': f"Stage '{name}'",
                    'status': 'FAILED',
                    'message': "Duplicate stage name"
                })
            else:
                stage_names.add(name)
                validation_results.append({
                    'field': f"Stage '{name}'",
                    'status': 'SUCCESS',
                    'message': f"Stage name is valid (within {STAGE_NAME_MAX_LENGTH} chars)"
                })
            
            # Validate order according to model field type (IntegerField)
            try:
                order_int = int(order)
                if order_int < 0:  # Assuming we want non-negative order values
                    validation_results.append({
                        'field': f"Stage '{name}' Order",
                        'status': 'FAILED',
                        'message': "Stage order must be a non-negative number"
                    })
                elif order_int in orders:
                    validation_results.append({
                        'field': f"Stage '{name}' Order",
                        'status': 'FAILED',
                        'message': f"Duplicate order number: {order_int}"
                    })
                else:
                    orders.add(order_int)
                    validation_results.append({
                        'field': f"Stage '{name}' Order",
                        'status': 'SUCCESS',
                        'message': f"Stage order {order_int} is valid"
                    })
            except (ValueError, TypeError):
                validation_results.append({
                    'field': f"Stage '{name}' Order",
                    'status': 'FAILED',
                    'message': "Stage order must be a valid integer"
                })
        
        # Check required stages
        for required_stage in REQUIRED_STAGES:
            if required_stage not in stage_names:
                validation_results.append({
                    'field': 'Required Stages',
                    'status': 'FAILED',
                    'message': f"Required stage '{required_stage}' is missing"
                })
            else:
                validation_results.append({
                    'field': f"Required Stage '{required_stage}'",
                    'status': 'SUCCESS',
                    'message': "Required stage is present"
                })
        
        # Validate stage sequence for both Initiate and Closed
        if 'Initiate' in stage_names:
            initiate_order = next(
                (int(s['Order']) for s in stages if s['Name'] == 'Initiate'),
                None
            )
            if initiate_order is not None and initiate_order != min(orders):
                validation_results.append({
                    'field': 'Stage Sequence',
                    'status': 'FAILED',
                    'message': "'Initiate' stage must be the first stage (lowest order number)"
                })
            else:
                validation_results.append({
                    'field': 'Stage Sequence',
                    'status': 'SUCCESS',
                    'message': "'Initiate' stage is correctly positioned as the first stage"
                })
                
        if 'Closed' in stage_names:
            closed_order = next(
                (int(s['Order']) for s in stages if s['Name'] == 'Closed'),
                None
            )
            if closed_order is not None and closed_order != max(orders):
                validation_results.append({
                    'field': 'Stage Sequence',
                    'status': 'FAILED',
                    'message': "'Closed' stage must be the last stage (highest order number)"
                })
            else:
                validation_results.append({
                    'field': 'Stage Sequence',
                    'status': 'SUCCESS',
                    'message': "'Closed' stage is correctly positioned as the last stage"
                })
                
        # Additional validation for stage sequence
        if 'Initiate' in stage_names and 'Closed' in stage_names:
            validation_results.append({
                'field': 'Stage Sequence',
                'status': 'SUCCESS',
                'message': "Both required stages are present and in correct sequence"
            })
                
    except json.JSONDecodeError:
        validation_results.append({
            'field': 'Stages JSON',
            'status': 'FAILED',
            'message': "Invalid stages JSON format"
        })
    except Exception as e:
        validation_results.append({
            'field': 'Stages',
            'status': 'ERROR',
            'message': f"Error validating stages: {str(e)}"
        })
        
    return validation_results

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
        content = csv_file.read().decode('utf-8-sig')  # Handle BOM if present
        
        # Create CSV reader
        reader = csv.DictReader(
            content.splitlines(),
            delimiter=',',
            quotechar='"',
            skipinitialspace=True
        )
        
        records = []
        for row_num, row in enumerate(reader, 1):
            try:
                # Clean up the row data
                processed_row = {}
                for key, value in row.items():
                    # Skip type annotation fields and empty keys
                    if not key or key.endswith('@type'):
                        continue
                        
                    # Handle None values and empty strings - updated check
                    if value is None or not isinstance(value, str) or not value.strip():
                        processed_row[key] = None
                        continue
                        
                    # Clean the value
                    cleaned_value = value.strip()
                    
                    # Convert boolean strings
                    if cleaned_value.lower() == 'true':
                        processed_row[key] = True
                    elif cleaned_value.lower() == 'false':
                        processed_row[key] = False
                    # Convert numeric strings for specific fields
                    elif key in ['FieldType', 'FiledType', 'Order', 'WizardPosition']:
                        try:
                            processed_row[key] = int(cleaned_value)
                        except (ValueError, TypeError):
                            processed_row[key] = None
                    else:
                        processed_row[key] = cleaned_value
                
                # Add the processed row if it has required fields
                if file_type == 'record_fields':
                    if 'PartitionKey' in processed_row and 'RowKey' in processed_row:
                        records.append(processed_row)
                    else:
                        logger.warning(f"Row {row_num} missing required fields PartitionKey or RowKey")
                else:
                    records.append(processed_row)
                
            except Exception as e:
                logger.error(f"Error processing row {row_num}: {str(e)}")
                logger.error(f"Row data: {row}")
                raise ValueError(f"Error in row {row_num}: {str(e)}")
        
        logger.info(f"Successfully parsed {len(records)} records")
        if len(records) == 0:
            logger.warning("No valid records found in CSV")
            
        return records
        
    except Exception as e:
        logger.error(f"Error parsing CSV: {str(e)}")
        raise ValueError(f"Error parsing CSV: {str(e)}")