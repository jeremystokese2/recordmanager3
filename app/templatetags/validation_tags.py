from django import template
from app.utils.constants import CORE_FIELDS

register = template.Library()

@register.filter
def get_validation_stats(results):
    """
    Calculate validation statistics from results list
    """
    stats = {
        'success': 0,
        'failed': 0,
        'error': 0,
        'info': 0,
        'warning': 0
    }
    
    for result in results:
        status = result.get('status', '').upper()
        if status == 'SUCCESS':
            stats['success'] += 1
        elif status == 'FAILED':
            stats['failed'] += 1
        elif status == 'ERROR':
            stats['error'] += 1
        elif status == 'INFO':
            stats['info'] += 1
        elif status == 'WARNING':
            stats['warning'] += 1
            
        # Also check details for additional statuses
        for detail in result.get('details', []):
            detail_status = detail.get('status', '').upper()
            if detail_status == 'WARNING':
                stats['warning'] += 1
            elif detail_status == 'INFO':
                stats['info'] += 1
    
    return stats 

@register.filter 
def is_core_field(field_name):
    """Check if a field is a core field"""
    return field_name in CORE_FIELDS

@register.filter
def get_field_badges(field_name, is_active):
    """Generate badge HTML for field status indicators"""
    badges = []
    
    # Add active/inactive badge
    if is_active:
        badges.append('<span class="badge bg-success">Active</span>')
    else:
        badges.append('<span class="badge bg-secondary">Inactive</span>')
        
    # Core field badge is now handled separately in the template
    return ' '.join(badges) 

@register.filter
def is_system_mandatory(field_name):
    """Check if a field is system mandatory"""
    SYSTEM_MANDATORY_FIELDS = {'Title', 'ABCOrgLevel1', 'ABCOrgLevel2'}
    return field_name in SYSTEM_MANDATORY_FIELDS