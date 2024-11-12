import json
import logging
from .constants import REQUIRED_STAGES, STAGE_NAME_MAX_LENGTH

logger = logging.getLogger(__name__)

def validate_stages(stages_json, record_name):
    """Validates stages data from JSON according to Stage model constraints."""
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
            
            # Validate order
            try:
                order_int = int(order)
                if order_int < 0:
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
        
        # Validate stage sequence
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