from django import template

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