import csv
import logging
import json

logger = logging.getLogger(__name__)

def parse_csv_to_json(csv_file, file_type):
    """Convert CSV to JSON format matching our expected structure"""
    logger.info(f"Starting CSV parsing for {file_type}")
    
    try:
        # Reset file pointer to beginning
        csv_file.seek(0)
        
        # Read the file content and decode it
        content = csv_file.read()
        if isinstance(content, bytes):
            content = content.decode('utf-8-sig')  # Handle BOM if present
        
        # Log the first part of content to verify it's not empty
        logger.info(f"File content length: {len(content)}")
        logger.info(f"First 200 chars: {content[:200]}")
        
        # Split into lines and find first non-empty line
        lines = [line.strip() for line in content.splitlines() if line.strip()]
        if not lines:
            logger.error("No non-empty lines found in file")
            raise ValueError("CSV file appears to be empty")
            
        logger.info(f"Number of non-empty lines: {len(lines)}")
        logger.info(f"First line: {lines[0]}")
        
        # Reset file pointer for CSV reader
        csv_file.seek(0)
        
        # Create CSV reader
        reader = csv.DictReader(
            (line for line in csv_file.read().decode('utf-8-sig').splitlines() if line.strip()),
            delimiter=',',
            quotechar='"',
            skipinitialspace=True
        )
        
        # Log field names detected
        field_names = reader.fieldnames
        if not field_names:
            logger.error("No headers detected in CSV file")
            raise ValueError("No headers detected in CSV file")
        logger.info(f"CSV headers found: {field_names}")
        
        records = []
        for row_num, row in enumerate(reader, 1):
            try:
                # Clean up the row data
                processed_row = {}
                for key, value in row.items():
                    if key and not key.endswith('@type'):  # Skip type annotation fields
                        # Handle empty values and 'null' strings
                        if not value or value.lower() == 'null':
                            processed_row[key] = None
                        else:
                            # Convert boolean strings
                            if value.lower() == 'true':
                                processed_row[key] = True
                            elif value.lower() == 'false':
                                processed_row[key] = False
                            else:
                                processed_row[key] = value.strip()
                
                logger.debug(f"Processed row {row_num}: {processed_row}")
                
                # Validate required fields
                if file_type == 'record_types':
                    if 'RowKey' not in processed_row:
                        error_msg = f"Row {row_num}: Missing required 'RowKey' column"
                        logger.error(error_msg)
                        raise ValueError(error_msg)
                        
                elif file_type == 'record_fields':
                    required_fields = ['RowKey', 'PartitionKey']
                    missing_fields = [f for f in required_fields if f not in processed_row]
                    if missing_fields:
                        error_msg = f"Row {row_num}: Missing required fields: {missing_fields}"
                        logger.error(error_msg)
                        raise ValueError(error_msg)
                
                records.append(processed_row)
                
            except Exception as e:
                logger.error(f"Error processing row {row_num}: {str(e)}")
                raise ValueError(f"Error in row {row_num}: {str(e)}")
        
        logger.info(f"Successfully parsed {len(records)} records from CSV")
        return records
        
    except UnicodeDecodeError as e:
        error_msg = f"Failed to decode CSV file: {str(e)}"
        logger.error(error_msg)
        raise ValueError(error_msg)
    except csv.Error as e:
        error_msg = f"CSV parsing error: {str(e)}"
        logger.error(error_msg)
        raise ValueError(error_msg)
    except Exception as e:
        error_msg = f"Unexpected error parsing CSV: {str(e)}"
        logger.error(error_msg)
        raise ValueError(error_msg)