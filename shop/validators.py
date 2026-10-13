import re
from django.core.exceptions import ValidationError
from PIL import Image

def hex_color(value):
    if not re.fullmatch(r'#[0-9a-fA-F]{6}',value):
        raise ValidationError('استخدم لونًا بصيغة #123ABC')

def image_upload(file):
    if file.name.rsplit('.',1)[-1].lower() not in {'jpg','jpeg','png','webp'}:
        raise ValidationError('امتداد الصورة يجب أن يكون JPEG أو PNG أو WEBP')
    if file.size > 5*1024*1024:
        raise ValidationError('الحد الأقصى للصورة 5 MB')
    try:
        file.seek(0)
        im = Image.open(file)
        if im.format not in {'JPEG','PNG','WEBP'} or im.width*im.height > 25_000_000:
            raise ValueError()
        im.verify()
        file.seek(0)
    except Exception:
        raise ValidationError('استخدم صورة JPEG أو PNG أو WEBP صالحة فقط.')
