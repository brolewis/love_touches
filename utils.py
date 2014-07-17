import phonenumbers


def format_phone(dct, split=False):
    if 'country_code' in dct and 'phone' in dct:
        num_obj = phonenumbers.parse('+{country_code} {phone}'.format(**dct))
        number = phonenumbers.format_number_for_mobile_dialing(num_obj, 'us',
                                                               True)
        return number[1:].split(' ', 1) if split else number
    else:
        return ('', '') if split else ''
