# Record Type Field Mapping
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

# Record Field Mapping
RECORD_FIELD_MAPPING = {
    'name': 'RowKey',
    'display_name': 'DisplayName', 
    'field_type': 'FieldType',
    'description': 'Description',
    'order': 'Order',
    'is_active': 'IsActive',
    'is_mandatory': 'IsRequired',
    'stage': 'Stages',
    'show_in_header': 'ShowInHeader'
}

# Validation Constants
SKIP_VALIDATION_MESSAGE = "Record is inactive (IsActive=False) - skipping validation"
STAGE_NAME_MAX_LENGTH = 50
REQUIRED_STAGES = ['Initiate', 'Closed']

# Field Types
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

DATASOURCE_REQUIRED_TYPES = {2, 3, 10}
ROLE_FIELD_TYPES = {4, 8}
VALID_SYS_CATEGORIES = {'', 'core', 'custom'}
VALID_WIZARD_POSITIONS = {0, 1}

# Ignored Fields
IGNORED_STATE_FIELDS = {
    'ABCAssignedTo', 'ABCAutoResponseTemplates', 'ABCCancelled', 'ABCClosedDate',
}

IGNORED_SP_FIELDS = {
    'DocumentSetDescription', 'FileLeafRef', 'FolderChildCount', 'ItemChildCount'
} 