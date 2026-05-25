from datetime import datetime

def format_field(value, length, data_type):
    if value is None:
        value = ''
    if data_type == 'N':
        if isinstance(value, (int, float)):
            value = str(int(value))
        return value.rjust(length, '0')
    else:
        if data_type == 'D' and value:
            if isinstance(value, datetime):
                value = value.strftime('%Y%m%d')
            else:
                value = str(value).replace('-', '')
        return str(value).ljust(length, ' ')[:length]

def generate_metro2_file(header_data, disputes, output_path):
    today = datetime.now()
    
    # Header segment
    header = (
        format_field('01', 2, 'AN') +
        format_field(header_data.get('bank_name', ''), 30, 'AN') +
        format_field(header_data.get('preparer_name', ''), 30, 'AN') +
        format_field(today, 8, 'D') +
        format_field(today.strftime('%H%M%S'), 6, 'N') +
        format_field(header_data.get('file_id', 'DISPUTE'), 20, 'AN') +
        format_field(len(disputes), 7, 'N')
    )
    
    lines = [header]
    
    for d in disputes:
        # Full Metro 2 Base Segment
        detail = (
            format_field('11', 2, 'AN') +                                           # Record type
            format_field(d.get('metro2_id', '3'), 1, 'N') +                         # Metro 2 ID (bank provides)
            format_field(d.get('portfolio_type', '10'), 2, 'AN') +                  # Portfolio type
            format_field(d.get('account_type', '4'), 1, 'AN') +                     # Account type
            format_field(d.get('account_number', ''), 30, 'AN') +                   # Account number
            format_field(d.get('customer_name', ''), 30, 'AN') +                    # Customer name
            format_field(d.get('ssn', ''), 9, 'N') +                                # SSN
            format_field(d.get('date_of_birth', ''), 8, 'D') +                      # DOB
            format_field(d.get('address', ''), 32, 'AN') +                          # Street address
            format_field(d.get('city', ''), 20, 'AN') +                             # City
            format_field(d.get('state', ''), 2, 'AN') +                             # State
            format_field(d.get('zip', ''), 9, 'N') +                                # ZIP
            format_field(d.get('date_opened', ''), 8, 'D') +                        # Date opened
            format_field(d.get('date_closed', ''), 8, 'D') +                        # Date closed
            format_field(d.get('last_payment_date', ''), 8, 'D') +                  # Last payment date
            format_field(d.get('credit_limit', 0), 9, 'N') +                        # Credit limit
            format_field(d.get('current_balance', 0), 9, 'N') +                     # Current balance
            format_field(d.get('amount_past_due', 0), 9, 'N') +                     # Amount past due
            format_field(d.get('scheduled_payment', 0), 9, 'N') +                   # Scheduled payment
            format_field(d.get('payment_rating', '0'), 1, 'N') +                    # Payment rating (0-9)
            format_field(d.get('payment_history_24', '0' * 24), 24, 'AN') +         # 24 month history
            format_field(d.get('date_of_first_delinq', ''), 8, 'D') +               # Date first delinquent
            format_field(d.get('compliance_code', 'XD'), 2, 'AN') +                 # Compliance code (XD = dispute)
            format_field(d.get('dispute_effective_date', today), 8, 'D')            # Dispute effective date
        )
        lines.append(detail)
    
    trailer = (
        format_field('99', 2, 'AN') +
        format_field(len(lines) + 1, 7, 'N')
    )
    lines.append(trailer)
    
    with open(output_path, 'w') as f:
        f.write('\n'.join(lines))
    
    print(f"Written to {output_path}")
