# ISO 4217 codes. Display names/symbols use the browser Intl API, no exchange rates.
CURRENCIES = '''AED AFN ALL AMD ANG AOA ARS AUD AWG AZN BAM BBD BDT BGN BHD BIF BMD BND BOB BRL BSD BTN BWP BYN BZD CAD CDF CHF CLP CNY COP CRC CUP CVE CZK DJF DKK DOP DZD EGP ERN ETB EUR FJD FKP GBP GEL GHS GIP GMD GNF GTQ GYD HKD HNL HTG HUF IDR ILS INR IQD IRR ISK JMD JOD JPY KES KGS KHR KMF KPW KRW KWD KYD KZT LAK LBP LKR LRD LSL LYD MAD MDL MGA MKD MMK MNT MOP MRU MUR MVR MWK MXN MYR MZN NAD NGN NIO NOK NPR NZD OMR PAB PEN PGK PHP PKR PLN PYG QAR RON RSD RUB RWF SAR SBD SCR SDG SEK SGD SHP SLE SOS SRD SSP STN SVC SYP SZL THB TJS TMT TND TOP TRY TTD TWD TZS UAH UGX USD UYU UZS VED VES VND VUV WST XAF XCD XOF XPF YER ZAR ZMW ZWG'''.split()
PREFERRED = ['JOD','SAR','USD']

def currency_digits(code):
    return 0 if code in ['BIF','CLP','DJF','GNF','ISK','JPY','KMF','KRW','PYG','RWF','UGX','VND','VUV','XAF','XOF','XPF'] else 3 if code in ['JOD','BHD','KWD','OMR','TND','IQD','LYD'] else 2

def validate_amount(amount):
    from decimal import Decimal
    from django.core.exceptions import ValidationError
    from .models import StoreSettings
    code=StoreSettings.get().currency
    quantum=Decimal(1).scaleb(-currency_digits(code))
    if amount != amount.quantize(quantum):
        raise ValidationError(f'العملة {code} تدعم {currency_digits(code)} أرقام بعد الفاصلة. حدّث السعر ليتوافق معها.')
