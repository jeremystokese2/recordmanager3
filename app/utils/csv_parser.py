import csv
import logging
import json
import pandas as pd
from io import StringIO

logger = logging.getLogger(__name__)

def parse_csv_to_json(csv_file, file_type):
    """Parse CSV file to JSON format."""
    try:
        # If csv_file is InMemoryUploadedFile, read its content
        if hasattr(csv_file, 'read'):
            # Save the current position
            pos = csv_file.tell()
            # Reset to beginning of file
            csv_file.seek(0)
            # Read the content
            content = csv_file.read()
            # Reset position back
            csv_file.seek(pos)
            
            # If content is bytes, decode to string
            if isinstance(content, bytes):
                content = content.decode('utf-8')
                
            # Create StringIO object from content
            csv_data = StringIO(content)
        else:
            csv_data = csv_file

        # Read CSV into DataFrame with explicit encoding
        df = pd.read_csv(csv_data, encoding='utf-8')
        
        if df.empty:
            raise ValueError("CSV file is empty")
            
        logger.info(f"Successfully read CSV with columns: {df.columns.tolist()}")
        
        # Convert DataFrame to list of dictionaries
        records = df.to_dict('records')
        
        if file_type == 'record_fields':
            # Filter out records where RowKey ends with _0
            records = [record for record in records 
                      if record.get('RowKey') and 
                      not str(record['RowKey']).endswith('_0')]
            logger.info(f"Filtered to {len(records)} records after removing _0 suffix entries")
            
        # Convert to JSON format
        return records
        
    except pd.errors.EmptyDataError:
        logger.error("CSV file is empty or has no parseable data")
        raise ValueError("CSV file is empty or has no parseable data")
    except Exception as e:
        logger.error(f"Error parsing CSV file: {str(e)}")
        raise ValueError(f"Error parsing CSV file: {str(e)}")